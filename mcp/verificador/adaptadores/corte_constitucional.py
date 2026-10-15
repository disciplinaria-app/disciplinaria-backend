"""Adaptador de la Corte Constitucional.

La relatoría (rediseñada en 2024-2025) devuelve una página «404 Página No
Encontrada» con código HTTP 200 cuando una ruta no existe, de modo que la
URL directa solo se acepta si el texto recuperado muestra el identificador.
La búsqueda temática usa el buscador de la relatoría con el navegador:
selector de modo (#selectBuscador), campo #textoBuscador y botón «Buscar».
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..comparar import canonizar_identificador, _RE_CC
from ..http import Respuesta
from ..modelos import Candidato, Corporacion
from ..portales import SELECTORES_CC as SEL
from ..texto import html_a_texto, limpiar_texto
from .base import Adaptador

_MARCAS_404 = ("página no encontrada", "pagina no encontrada", "page not found")


class CorteConstitucional(Adaptador):
    corporacion = Corporacion.CORTE_CONSTITUCIONAL

    # --- URL directa: varios patrones, en orden -----------------------------
    def urls_directas(self, identificador: str) -> list[str]:
        m = _RE_CC.search(identificador)
        if not m:
            return []
        can = canonizar_identificador(identificador)  # p. ej. SU-107/2024
        tipo, resto = can.split("-", 1)
        num, anio = resto.split("/")
        patrones = [p.strip() for p in self.portal["patrones_sentencia"].split(",") if p.strip()]
        salida = []
        for p in patrones:
            u = p.format(anio=anio, tipo=tipo, num=num, num3=num.zfill(3), aa=anio[-2:])
            if u not in salida:
                salida.append(u)
        return salida

    def url_directa(self, identificador: str) -> Optional[str]:
        urls = self.urls_directas(identificador)
        return urls[0] if urls else None

    def _contenido_util(self, resp: Respuesta) -> bool:
        if resp.es_pdf:
            return len(resp.contenido) > 1000
        texto, _ = html_a_texto(resp.texto)
        inicio = texto[:3000].lower()
        if any(m in inicio for m in _MARCAS_404):
            return False
        return len(texto) > 2500  # el armazón del sitio sin sentencia ronda los 1.300-2.600 caracteres

    # --- búsqueda ------------------------------------------------------------
    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        url = self.portal["buscador"]
        if not await self.nav.disponible():
            resp = await self.http.obtener(url)
            if resp.estado == "ok":
                resp.estado = "parcial"
                resp.detalle = "el buscador exige navegador y Playwright no está disponible"
            return [], resp
        consulta_limpia = consulta.strip().strip('"')
        es_identificador = bool(_RE_CC.fullmatch(consulta_limpia))
        if not es_identificador:
            # El buscador trata la consulta como frase exacta y recomienda frases
            # cortas: se conservan a lo sumo las tres palabras más largas, en su orden.
            palabras = [w for w in consulta_limpia.split() if len(w) > 3]
            if len(palabras) > 3:
                elegidas = sorted(sorted(palabras, key=len, reverse=True)[:3], key=palabras.index)
                consulta_limpia = " ".join(elegidas)
        modo = SEL["modo_numero"] if es_identificador else SEL["modo_texto"]
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(url, wait_until="domcontentloaded")
                await p.locator(SEL["selector_modo"]).first.select_option(label=modo)
                await p.locator(SEL["campo_texto"]).first.fill(consulta_limpia)
                if desde:
                    try:
                        await p.locator("#datePicker1").fill(f"{desde}-01-01")
                    except Exception:
                        pass
                if hasta:
                    try:
                        await p.locator("#datePicker2").fill(f"{hasta}-12-31")
                    except Exception:
                        pass
                await p.locator(SEL["boton_buscar"]).first.click()
                try:
                    await p.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass
                await p.wait_for_timeout(2500)
                html = await p.content()
                candidatos = self._extraer_candidatos(html, p.url, max_resultados)
                estado = "ok" if candidatos else "sin_resultados"
                return candidatos, Respuesta(estado=estado, url_inicial=url, url_final=p.url,
                                             codigo=r.status if r else None, contenido=html.encode(), tipo="text/html",
                                             detalle=None if candidatos else "el buscador no mostró enlaces a providencias")
        except Exception as e:
            nombre = e.__class__.__name__
            return [], Respuesta(estado="timeout" if "Timeout" in nombre else "portal_no_disponible",
                                 url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    def _extraer_candidatos(self, html: str, base: str, limite: int) -> list[Candidato]:
        soup = BeautifulSoup(html, "lxml")
        vistos: set[str] = set()
        salida: list[Candidato] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/relatoria/" not in href or href.rstrip("/").endswith(("/relatoria", "buscador-jurisprudencia", "boletines-jurisprudencia", "temas-interes")):
                continue
            texto = limpiar_texto(a.get_text(" "))
            m = _RE_CC.search(texto) or re.search(r"/relatoria/(\d{4})/([A-Za-z]{1,2})-?(\d{1,4})-(\d{2})", href)
            if not m:
                continue
            if m.re is _RE_CC:
                ident = canonizar_identificador(m.group(0))
            else:
                ident = canonizar_identificador(f"{m.group(2)}-{int(m.group(3))}/{m.group(1)}")
            if ident in vistos:
                continue
            vistos.add(ident)
            padre = a.find_parent(["li", "tr", "div", "p", "article"])
            contexto = limpiar_texto(padre.get_text(" "))[:400] if padre else texto[:400]
            salida.append(Candidato(corporacion=self.corporacion, identificador=ident, url_oficial=urljoin(base, href),
                                    titulo=texto[:200] or None, fragmento_descubrimiento=contexto or None,
                                    canales=["playwright"]))
            if len(salida) >= limite:
                break
        return salida
