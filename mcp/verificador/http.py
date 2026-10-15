"""Cliente HTTP hacia los portales oficiales, con estados técnicos distintos.

Un fallo de red nunca se traduce en «la providencia no existe». Cada
recuperación devuelve un estado: ok, sin_resultados, portal_no_disponible,
bloqueada, timeout.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx

from .modelos import EstadoConsulta

USER_AGENT = os.getenv(
    "MCP_USER_AGENT",
    "redactar2-mcp/0.1 (verificador jurisprudencial de despacho; contacto en variable MCP_CONTACTO)",
)
TIMEOUT_S = float(os.getenv("HTTP_TIMEOUT", "40"))
INTERVALO_POR_DOMINIO_S = float(os.getenv("HTTP_INTERVALO_DOMINIO", "1.0"))

DOMINIOS_AUTORIZADOS = tuple(
    d.strip() for d in os.getenv(
        "DOMINIOS_AUTORIZADOS",
        "corteconstitucional.gov.co,cortesuprema.gov.co,ramajudicial.gov.co,cndj.gov.co,"
        "consejodeestado.gov.co,samai.consejodeestado.gov.co,secretariasenado.gov.co,"
        "suin-juriscol.gov.co,funcionpublica.gov.co",
    ).split(",") if d.strip()
)


def dominio_autorizado(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_AUTORIZADOS)


@dataclass
class Respuesta:
    estado: EstadoConsulta
    url_inicial: str
    url_final: Optional[str] = None
    codigo: Optional[int] = None
    contenido: bytes = b""
    tipo: str = ""
    consultada_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latencia_ms: int = 0
    detalle: Optional[str] = None

    @property
    def texto(self) -> str:
        """Decodifica respetando el charset declarado (cabecera o <meta>); las
        relatorías antiguas sirven ISO-8859-1/Windows-1252 sin cabecera."""
        cabecera = (self.tipo or "").lower()
        inicio = self.contenido[:4000].lower()
        for marca, codec in (("iso-8859-1", "cp1252"), ("windows-1252", "cp1252"), ("latin1", "cp1252"), ("utf-8", "utf-8")):
            if marca.encode() in inicio or marca in cabecera:
                try:
                    return self.contenido.decode(codec)
                except UnicodeDecodeError:
                    break
        try:
            return self.contenido.decode("utf-8")
        except UnicodeDecodeError:
            return self.contenido.decode("cp1252", errors="replace")

    @property
    def es_pdf(self) -> bool:
        return "pdf" in self.tipo.lower() or self.contenido[:5] == b"%PDF-"


class ClienteHTTP:
    """Cliente con límite de una solicitud por segundo por dominio."""

    def __init__(self) -> None:
        self._cliente = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-CO,es;q=0.9"},
            timeout=httpx.Timeout(TIMEOUT_S, connect=15.0),
            follow_redirects=True,
        )
        self._ultimo: dict[str, float] = {}
        self._cerrojos: dict[str, asyncio.Lock] = {}

    async def cerrar(self) -> None:
        await self._cliente.aclose()

    async def _respetar_intervalo(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        cerrojo = self._cerrojos.setdefault(host, asyncio.Lock())
        async with cerrojo:
            espera = INTERVALO_POR_DOMINIO_S - (time.monotonic() - self._ultimo.get(host, 0.0))
            if espera > 0:
                await asyncio.sleep(espera)
            self._ultimo[host] = time.monotonic()

    async def obtener(self, url: str, params: Optional[dict] = None, metodo: str = "GET",
                      datos: Optional[dict] = None) -> Respuesta:
        if not dominio_autorizado(url):
            return Respuesta(estado="bloqueada", url_inicial=url,
                             detalle="dominio fuera de la lista autorizada; no se consulta")
        await self._respetar_intervalo(url)
        inicio = time.monotonic()
        try:
            r = await self._cliente.request(metodo, url, params=params, data=datos)
        except httpx.TimeoutException as e:
            return Respuesta(estado="timeout", url_inicial=url, detalle=f"timeout: {e.__class__.__name__}",
                             latencia_ms=int((time.monotonic() - inicio) * 1000))
        except httpx.HTTPError as e:
            return Respuesta(estado="portal_no_disponible", url_inicial=url, detalle=f"error de red: {e}",
                             latencia_ms=int((time.monotonic() - inicio) * 1000))
        lat = int((time.monotonic() - inicio) * 1000)
        if r.status_code in (401, 403, 429):
            estado: EstadoConsulta = "bloqueada"
        elif r.status_code == 404:
            estado = "sin_resultados"
        elif r.status_code >= 500:
            estado = "portal_no_disponible"
        elif r.status_code >= 400:
            estado = "portal_no_disponible"
        else:
            estado = "ok"
        return Respuesta(estado=estado, url_inicial=url, url_final=str(r.url), codigo=r.status_code,
                         contenido=r.content, tipo=r.headers.get("content-type", ""), latencia_ms=lat,
                         detalle=None if estado == "ok" else f"HTTP {r.status_code}")
