import asyncio
import io
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from config import ALLOWED_ORIGINS, OPENROUTER_API_KEY
from models.schemas import AnalisisRequest, AnalisisResponse, AplicarRequest
from agents import (
    agente_forma,
    agente_estilo,
    agente_coherencia,
    agente_argumentacion,
    agente_normativo,
    consolidador,
)


# ── Almacenamiento temporal de documentos procesados ─────────────────────────

@dataclass
class _EntryTemp:
    """Entrada en caché para un documento analizado."""
    original_bytes: bytes          # .docx tal como lo subió el usuario
    hallazgos: list                # lista completa de Hallazgo del consolidador
    timestamp: float               # time.monotonic() al momento del análisis
    nombre_stem: str               # nombre base sin extensión para la descarga

_archivos_temp: dict[str, _EntryTemp] = {}
_EXPIRA_SEG = 3600  # 1 hora


def _limpiar_expirados() -> None:
    ahora = time.monotonic()
    expirados = [k for k, v in _archivos_temp.items() if ahora - v.timestamp > _EXPIRA_SEG]
    for k in expirados:
        del _archivos_temp[k]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENROUTER_API_KEY:
        print("ADVERTENCIA: OPENROUTER_API_KEY no está configurada.")
    yield


app = FastAPI(
    title="DISCIPLINAR[IA] API",
    description=(
        "Plataforma de revisión inteligente de documentos jurídicos disciplinarios colombianos. "
        "Analiza fallos, pliegos de cargos, autos de archivo y demás actuaciones mediante "
        "5 agentes IA especializados que operan en paralelo."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {str(exc)}"},
    )


@app.get("/", summary="Estado del servicio")
async def raiz():
    return {
        "servicio": "DISCIPLINAR[IA] API",
        "version": "1.0.0",
        "estado": "activo",
        "descripcion": "Análisis inteligente de documentos disciplinarios colombianos",
    }


@app.get("/health", summary="Health check para Railway")
async def health():
    return {"status": "ok"}


@app.post(
    "/analizar",
    response_model=AnalisisResponse,
    summary="Analizar documento disciplinario",
    description=(
        "Recibe el texto de un documento jurídico disciplinario colombiano y la norma aplicable. "
        "Lanza 5 agentes IA en paralelo (FORMA, ESTILO JUDICIAL, COHERENCIA NARRATIVA, "
        "FONDO ARGUMENTATIVO, NORMATIVO) y retorna un análisis consolidado con puntaje, errores, "
        "fortalezas y recomendaciones."
    ),
)
async def analizar(request: AnalisisRequest) -> AnalisisResponse:
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está configurado. Contacte al administrador.",
        )

    inicio = time.monotonic()

    resultados = await asyncio.gather(
        agente_forma.ejecutar(request.texto, request.norma),
        agente_estilo.ejecutar(request.texto, request.norma),
        agente_coherencia.ejecutar(request.texto, request.norma),
        agente_argumentacion.ejecutar(request.texto, request.norma),
        agente_normativo.ejecutar(request.texto, request.norma),
        return_exceptions=False,
    )

    respuesta = await consolidador.consolidar(list(resultados), request.norma)

    duracion = round(time.monotonic() - inicio, 2)
    respuesta.estadisticas.distribucion_puntajes["_duracion_segundos"] = duracion

    return respuesta


@app.post(
    "/analizar-archivo",
    response_model=AnalisisResponse,
    summary="Analizar .docx y generar documento revisado con control de cambios",
)
async def analizar_archivo(
    archivo: UploadFile = File(...),
    norma: str = Form(...),
) -> AnalisisResponse:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Servicio de IA no configurado.")

    nombre = archivo.filename or "documento.docx"
    if not nombre.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")

    docx_bytes = await archivo.read()
    if len(docx_bytes) < 100:
        raise HTTPException(status_code=400, detail="El archivo está vacío o es inválido.")

    # Extraer texto del .docx
    from docx import Document as _DocxDoc
    try:
        doc_tmp = _DocxDoc(io.BytesIO(docx_bytes))
        texto = "\n".join(p.text for p in doc_tmp.paragraphs if p.text.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el .docx: {exc}")

    if len(texto) < 50:
        raise HTTPException(status_code=400, detail="El documento no contiene suficiente texto.")

    inicio = time.monotonic()

    resultados = await asyncio.gather(
        agente_forma.ejecutar(texto, norma),
        agente_estilo.ejecutar(texto, norma),
        agente_coherencia.ejecutar(texto, norma),
        agente_argumentacion.ejecutar(texto, norma),
        agente_normativo.ejecutar(texto, norma),
        return_exceptions=False,
    )

    respuesta = await consolidador.consolidar(list(resultados), norma)

    # Almacenar original + hallazgos para descarga selectiva posterior
    from pathlib import Path as _Path
    archivo_id = str(uuid.uuid4())
    nombre_stem = _Path(nombre).stem
    _limpiar_expirados()
    _archivos_temp[archivo_id] = _EntryTemp(
        original_bytes=docx_bytes,
        hallazgos=respuesta.hallazgos,
        timestamp=time.monotonic(),
        nombre_stem=nombre_stem,
    )

    duracion = round(time.monotonic() - inicio, 2)
    respuesta.estadisticas.distribucion_puntajes["_duracion_segundos"] = duracion
    respuesta.archivo_id = archivo_id

    return respuesta


@app.get("/descargar/{archivo_id}", summary="Descargar .docx completo con track changes (todos los hallazgos)")
async def descargar_archivo(archivo_id: str) -> Response:
    """Genera el .docx con track changes para TODOS los hallazgos detectados.
    Para aplicar solo los hallazgos aprobados por el revisor, usar POST /aplicar/{archivo_id}.
    """
    _limpiar_expirados()
    if archivo_id not in _archivos_temp:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado (1 hora).")

    entry = _archivos_temp[archivo_id]

    from agents.track_changes import generar_documento_revisado
    try:
        docx_revisado = generar_documento_revisado(entry.original_bytes, entry.hallazgos)
    except Exception:
        docx_revisado = entry.original_bytes

    nombre_descarga = f"{entry.nombre_stem}_DISCIPLINARIA_revisado.docx"
    return Response(
        content=docx_revisado,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nombre_descarga}"'},
    )


@app.post(
    "/aplicar/{archivo_id}",
    summary="Aplicar hallazgos aprobados y descargar .docx corregido",
    description=(
        "Recibe la lista de IDs de hallazgos que el revisor aprobó en la interfaz web. "
        "Aplica solo esas correcciones al .docx original sin track changes — "
        "el archivo descargado tiene el texto ya corregido, listo para usar."
    ),
)
async def aplicar_correcciones(archivo_id: str, body: AplicarRequest) -> Response:
    _limpiar_expirados()
    if archivo_id not in _archivos_temp:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado (1 hora).")

    entry = _archivos_temp[archivo_id]
    ids_set = set(body.hallazgo_ids)
    hallazgos_aceptados = [h for h in entry.hallazgos if h.id in ids_set]

    if not hallazgos_aceptados:
        raise HTTPException(status_code=400, detail="Ningún hallazgo válido en la selección.")

    from agents.track_changes import aplicar_correcciones_zip
    try:
        docx_resultado = aplicar_correcciones_zip(entry.original_bytes, hallazgos_aceptados)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al aplicar correcciones: {exc}")

    nombre_descarga = f"{entry.nombre_stem}_DISCIPLINARIA_corregido.docx"
    return Response(
        content=docx_resultado,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nombre_descarga}"'},
    )


# ── Interfaz web (servida desde /app) ────────────────────────────────────────
# Acceso: http://localhost:8000/app  |  https://disciplinaria.app/app
# El mount va al final para no interceptar las rutas de la API.
import os as _os
if _os.path.isdir("frontend"):
    app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
