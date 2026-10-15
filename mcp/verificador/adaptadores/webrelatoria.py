"""Adaptador para las relatorías de la Rama Judicial (aplicación WebRelatoria).

La CNDJ y la Corte Suprema publican su jurisprudencia en la misma aplicación
JSF (`WebRelatoria`), con formulario, estado de sesión y paginación. El HTTP
simple no basta: la búsqueda se hace con el navegador. Los selectores son
configurables por variable de entorno y se validan con `diagnosticar_portales`.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..comparar import canonizar_identificador, identificadores_en_texto, parsear_fecha
from ..http import Respuesta
from ..modelos import Candidato, Corporacion
from ..portales import SELECTORES_WEBRELATORIA as SEL
from ..texto import limpiar_texto
from .base import Adaptador


class WebRelatoria(Adaptador):
    corporacion: Corporacion

    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        url = self.portal["buscador"]
        if not await self.nav.disponible():
            # Dejar constancia del intento HTTP para el diagnóstico.
            resp = await self.http.obtener(url)
            if resp.estado == "ok":
                resp.estado = "parcial"
                resp.detalle = "el portal exige navegador (formulario JSF) y Playwright no está disponible"
            return [], resp
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(url, wait_until="domcontentloaded")
                campo = p.locator(SEL["campo_texto"]).first
                await campo.fill(consulta)
                await p.locator(SEL["boton_buscar"]).first.click()
                try:
                    await p.wait_for_selector(SEL["filas_resultado"], timeout=25000)
                except Exception:
                    html = await p.content()
                    return [], Respuesta(estado="sin_resultados", url_inicial=url, url_final=p.url,
                                         codigo=r.status if r else None, contenido=html.encode(),
                                         tipo="text/html", detalle="no aparecieron filas de resultado")
                candidatos: list[Candidato] = []
                paginas = 0
                while len(candidatos) < max_resultados and paginas < 5:
                    html = await p.content()
                    nuevos = self._extraer(html, p.url, desde, hasta)
                    for c in nuevos:
                        if all(c.identificador != x.identificador for x in candidatos):
                            candidatos.append(c)
                    siguiente = p.locator(SEL["siguiente_pagina"])
                    if len(candidatos) >= max_resultados or await siguiente.count() == 0:
                        break
                    await siguiente.first.click()
                    await p.wait_for_timeout(1500)
                    paginas += 1
                resp = Respuesta(estado="ok" if candidatos else "sin_resultados", url_inicial=url, url_final=p.url,
                                 codigo=r.status if r else None, contenido=html.encode(), tipo="text/html")
                return candidatos[:max_resultados], resp
        except Exception as e:
            nombre = e.__class__.__name__
            estado = "timeout" if "Timeout" in nombre else "portal_no_disponible"
            return [], Respuesta(estado=estado, url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    def _extraer(self, html: str, base: str, desde: Optional[int], hasta: Optional[int]) -> list[Candidato]:
        soup = BeautifulSoup(html, "lxml")
        salida: list[Candidato] = []
        for fila in soup.select(SEL["filas_resultado"]):
            texto = limpiar_texto(fila.get_text(" "))
            if len(texto) < 15:
                continue
            idents = identificadores_en_texto(texto)
            enlace = fila.select_one(SEL["enlace_documento"])
            href = urljoin(base, enlace["href"]) if enlace and enlace.get("href") else None
            ident = sorted(idents)[0] if idents else (href.rsplit("/", 1)[-1] if href else None)
            if not ident:
                continue
            fecha = None
            for m in re.finditer(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}", texto):
                fecha = parsear_fecha(m.group(0))
                if fecha:
                    break
            if fecha and ((desde and fecha.year < desde) or (hasta and fecha.year > hasta)):
                continue
            ponente = None
            mp = re.search(r"(?:ponente|m\.?\s?p\.?)\s*[:.]?\s*([A-ZÁÉÍÓÚÑ][^|\n]{5,60})", texto, re.I)
            if mp:
                ponente = mp.group(1).strip()
            salida.append(Candidato(corporacion=self.corporacion, identificador=canonizar_identificador(ident),
                                    url_oficial=href, fecha=fecha, ponente=ponente,
                                    fragmento_descubrimiento=texto[:400], canales=["playwright"]))
        return salida


class CNDJ(WebRelatoria):
    corporacion = Corporacion.CNDJ


class CorteSuprema(WebRelatoria):
    corporacion = Corporacion.CORTE_SUPREMA
