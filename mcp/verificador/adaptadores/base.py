"""Interfaz común de los adaptadores por corporación.

Cada adaptador sabe (a) construir la URL directa de una providencia cuando
el portal tiene un patrón estable, (b) buscar candidatos en el buscador de
la relatoría, (c) recuperar el documento oficial y (d) informar su salud.
La estrategia es siempre HTTP primero y navegador después.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..cache import sha256
from ..http import ClienteHTTP, Respuesta
from ..modelos import Candidato, Corporacion, DocumentoOficial, EstadoPortal
from ..navegador import Navegador
from ..texto import html_a_texto, pdf_a_texto


class Adaptador:
    corporacion: Corporacion
    nombre: str

    def __init__(self, http: ClienteHTTP, navegador: Navegador, portal: dict[str, str]) -> None:
        self.http = http
        self.nav = navegador
        self.portal = portal
        self.nombre = portal["nombre"]

    # --- a) URL directa ---------------------------------------------------
    def url_directa(self, identificador: str) -> Optional[str]:
        return None

    # --- b) búsqueda ------------------------------------------------------
    async def buscar(self, consulta: str, desde: Optional[int] = None, hasta: Optional[int] = None,
                     max_resultados: int = 20) -> tuple[list[Candidato], Respuesta]:
        raise NotImplementedError

    # --- c) recuperación --------------------------------------------------
    async def recuperar(self, url: str, identificador: str, forzar_navegador: bool = False) -> tuple[Optional[DocumentoOficial], Respuesta]:
        """HTTP → navegador. Devuelve el documento y la respuesta técnica."""
        resp = None
        if not forzar_navegador:
            resp = await self.http.obtener(url)
            if resp.estado == "ok" and self._contenido_util(resp):
                return self._a_documento(resp, identificador, "http"), resp
        if await self.nav.disponible():
            resp_nav = await self.nav.obtener_html(url)
            if resp_nav.estado == "ok" and self._contenido_util(resp_nav):
                return self._a_documento(resp_nav, identificador, "playwright"), resp_nav
            return None, resp_nav if resp is None or resp.estado == "ok" else resp
        if resp is None:
            resp = Respuesta(estado="portal_no_disponible", url_inicial=url, detalle="navegador no disponible")
        elif resp.estado == "ok":
            resp.estado = "parcial"
            resp.detalle = "la respuesta no contiene el texto de la providencia (posible página dinámica) y el navegador no está disponible"
        return None, resp

    def _contenido_util(self, resp: Respuesta) -> bool:
        if resp.es_pdf:
            return len(resp.contenido) > 1000
        texto, _ = html_a_texto(resp.texto)
        return len(texto) > 800

    def _a_documento(self, resp: Respuesta, identificador: str, canal: str) -> DocumentoOficial:
        if resp.es_pdf:
            texto, meta = pdf_a_texto(resp.contenido)
            tipo = "pdf"
        else:
            texto, meta = html_a_texto(resp.texto)
            tipo = "html"
        return DocumentoOficial(
            corporacion=self.corporacion, identificador=identificador,
            url_oficial=resp.url_final or resp.url_inicial, texto=texto, sha256=sha256(resp.contenido),
            consultada_en=resp.consultada_en, canal=canal, tipo_contenido=tipo, metadatos=meta,
        )

    # --- d) salud ---------------------------------------------------------
    async def salud(self) -> EstadoPortal:
        url = self.portal["relatoria"]
        resp = await self.http.obtener(url)
        return EstadoPortal(corporacion=self.corporacion, url=url, estado=resp.estado, codigo_http=resp.codigo,
                            latencia_ms=resp.latencia_ms, detalle=resp.detalle,
                            comprobado_en=datetime.now(timezone.utc))
