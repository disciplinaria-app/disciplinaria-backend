"""redactar2-mcp — servidor MCP (Streamable HTTP) del verificador jurisprudencial.

Arranque local:   python server.py            (escucha en $PORT, por defecto 8080)
Cliente:          POST https://<host>/mcp  con  Authorization: Bearer $MCP_API_KEY
Salud:            GET  https://<host>/health  (sin autenticación)
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from verificador.servicio import Servicio

VERSION = "0.1.0"
API_KEY = os.getenv("MCP_API_KEY", "")

INSTRUCCIONES = (
    "Verificador y buscador jurisprudencial oficial para providencias colombianas (Corte Constitucional, "
    "Corte Suprema de Justicia, Consejo de Estado y Comisión Nacional de Disciplina Judicial). "
    "Recupera, compara y estructura evidencia de los portales oficiales. No redacta ni califica la fuerza "
    "jurídica de un precedente. Reglas de uso: (1) enviar solo identificadores públicos y subreglas abstractas, "
    "nunca nombres de partes, cédulas, radicados de proceso ni párrafos del borrador; (2) un candidato de "
    "buscar_providencia sale siempre con verificado=false y debe pasar por verificar_cita y leer_providencia; "
    "(3) 'no_hallada', 'portal_no_disponible' y 'timeout' no significan que la providencia no exista; "
    "(4) un pasaje con rol 'salvamento' o 'aclaracion' no es ratio de la mayoría."
)

servicio: Optional[Servicio] = None


@asynccontextmanager
async def ciclo_de_vida(_: MCPServer):
    global servicio
    servicio = Servicio()
    try:
        yield {}
    finally:
        await servicio.cerrar()


mcp = MCPServer(name="redactar2-verificador", version=VERSION, instructions=INSTRUCCIONES, lifespan=ciclo_de_vida)


@mcp.tool(description=(
    "Verifica una cita jurisprudencial contra el documento oficial de la corporación. Compara, campo por campo, "
    "identificador (tipo_numero o radicado), ponente, fecha y sala, y devuelve confirmado/discrepante/no_hallado "
    "por campo, la URL oficial abierta, el hash del documento y, si se envía ratio_invocada (subregla abstracta), "
    "el pasaje más cercano con su rol textual (mayoria_motiva, resolutiva, salvamento, aclaracion, argumento_parte, "
    "decision_resenada, desconocido)."
))
async def verificar_cita(corporacion: str, tipo_numero: Optional[str] = None, radicado: Optional[str] = None,
                         sala: Optional[str] = None, ponente: Optional[str] = None, fecha: Optional[str] = None,
                         ratio_invocada: Optional[str] = None, url_oficial: Optional[str] = None) -> dict:
    r = await servicio.verificar_cita(corporacion, tipo_numero, radicado, sala, ponente, fecha, ratio_invocada, url_oficial)
    return r.model_dump(mode="json")


@mcp.tool(description=(
    "Busca providencias candidatas a partir de una subregla jurídica abstracta en el portal oficial de la corporación, "
    "con varias formulaciones (frase exacta, términos nucleares, sinónimos, búsqueda adversa, ventana temporal). "
    "Devuelve candidatos con verificado=false, los canales ejecutados y coverage_status. modo: 'amplio' (por defecto) "
    "o 'rapido'. desde/hasta: años."
))
async def buscar_providencia(tesis: str, corporacion: str, desde: Optional[int] = None, hasta: Optional[int] = None,
                             modo: str = "amplio", max_candidatos: int = 20, sentencia_hito: Optional[str] = None) -> dict:
    r = await servicio.buscar_providencia(tesis, corporacion, desde, hasta, modo, max_candidatos, sentencia_hito)
    return r.model_dump(mode="json")


@mcp.tool(description=(
    "Lee el texto oficial de una providencia por segmentos. Devuelve el segmento pedido, su localizador "
    "(párrafo/página), el rol estimado de la sección y los metadatos del documento (URL, hash, fecha de consulta). "
    "Usar segmento=0,1,2… para recorrer el texto; 'secciones_detectadas' indica cuántos segmentos hay por rol."
))
async def leer_providencia(corporacion: str, identificador: Optional[str] = None, url_oficial: Optional[str] = None,
                           segmento: int = 0, tamano: int = 3500) -> dict:
    r = await servicio.leer_providencia(corporacion, identificador, url_oficial, segmento, tamano)
    return r.model_dump(mode="json")


@mcp.tool(description=(
    "Busca decisiones de los cuatro años anteriores a fecha_corte (AAAA-MM-DD; por defecto hoy) sobre una subregla, "
    "a partir de una sentencia hito. Marca si el fragmento de descubrimiento cita al hito y si contiene señales "
    "textuales de rectificación o distinción. Las señales no son clasificación jurídica: verificar cada decisión."
))
async def actualizar_linea(subregla: str, sentencia_hito: str, corporacion: str, fecha_corte: Optional[str] = None,
                           max_candidatos: int = 20) -> dict:
    return await servicio.actualizar_linea(subregla, sentencia_hito, corporacion, fecha_corte, max_candidatos)


@mcp.tool(description="Consulta el estado de un trabajo largo por trabajo_id (pendiente, terminado, error).")
async def estado_verificacion(trabajo_id: str) -> dict:
    return servicio.estado_verificacion(trabajo_id)


@mcp.tool(description=(
    "Diagnóstico técnico: comprueba qué portales oficiales responden, si el navegador automatizado está disponible "
    "y cuántos documentos hay en el corpus local. Para soporte y pruebas; no devuelve análisis jurídico."
))
async def diagnosticar_portales() -> dict:
    return await servicio.diagnosticar_portales()


# --- Aplicación ASGI con autenticación por llave --------------------------------

class AutenticacionPorLlave(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/"):
            return await call_next(request)
        if not API_KEY:
            return JSONResponse({"error": "MCP_API_KEY no configurada en el servidor"}, status_code=503)
        auth = request.headers.get("authorization", "")
        llave = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
        if not llave or not hmac.compare_digest(llave, API_KEY):
            return JSONResponse({"error": "no autorizado"}, status_code=401)
        return await call_next(request)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request):
    return JSONResponse({"estado": "ok", "servicio": "redactar2-verificador", "version": VERSION})


@mcp.custom_route("/", methods=["GET"])
async def raiz(_: Request):
    return JSONResponse({"servicio": "redactar2-verificador", "version": VERSION, "mcp": "/mcp", "salud": "/health"})


app = mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")
app.add_middleware(AutenticacionPorLlave)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), log_level="info")
