"""Adaptador del Consejo de Estado (SAMAI / Biblioteca Digital).

El buscador de jurisprudencia de SAMAI es una aplicación dinámica; se usa el
navegador con búsqueda por texto. La consulta de procesos es otra cosa y no
se usa aquí.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..comparar import canonizar_identificador, identificadores_en_texto, parsear_fecha
from ..http import Respuesta
from ..modelos import Candidato, Corporacion
from ..texto import limpiar_texto
from .base import Adaptador


class ConsejoEstado(Adaptador):
    corporacion = Corporacion.CONSEJO_ESTADO

    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        url = self.portal["buscador"]
        if not await self.nav.disponible():
            resp = await self.http.obtener(url)
            if resp.estado == "ok":
                resp.estado = "parcial"
                resp.detalle = "el portal exige navegador y Playwright no está disponible"
            return [], resp
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(url, wait_until="domcontentloaded")
                campo = p.locator("input[type='search'], input[type='text'], textarea").first
                await campo.fill(consulta)
                await campo.press("Enter")
                await p.wait_for_timeout(4000)
                html = await p.content()
                candidatos = self._extraer(html, p.url, desde, hasta)[:max_resultados]
                return candidatos, Respuesta(estado="ok" if candidatos else "sin_resultados", url_inicial=url,
                                             url_final=p.url, codigo=r.status if r else None,
                                             contenido=html.encode(), tipo="text/html")
        except Exception as e:
            nombre = e.__class__.__name__
            return [], Respuesta(estado="timeout" if "Timeout" in nombre else "portal_no_disponible",
                                 url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    def _extraer(self, html, base, desde, hasta):
        soup = BeautifulSoup(html, "lxml")
        salida: list[Candidato] = []
        vistos: set[str] = set()
        for a in soup.find_all("a", href=True):
            contenedor = a.find_parent(["li", "tr", "article", "div"]) or a
            texto = limpiar_texto(contenedor.get_text(" "))
            idents = identificadores_en_texto(texto)
            if not idents:
                continue
            ident = sorted(idents)[0]
            if ident in vistos:
                continue
            fecha = None
            for m in re.finditer(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}", texto):
                fecha = parsear_fecha(m.group(0))
                if fecha:
                    break
            if fecha and ((desde and fecha.year < desde) or (hasta and fecha.year > hasta)):
                continue
            vistos.add(ident)
            salida.append(Candidato(corporacion=self.corporacion, identificador=canonizar_identificador(ident),
                                    url_oficial=urljoin(base, a["href"]), fecha=fecha,
                                    fragmento_descubrimiento=texto[:400], canales=["playwright"]))
        return salida
