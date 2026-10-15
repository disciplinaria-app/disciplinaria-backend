"""Adaptador de la Corte Constitucional.

La relatoría (rediseñada en 2024-2025) devuelve una página «404 Página No
Encontrada» con código HTTP 200 cuando una ruta no existe, de modo que la
URL directa solo se acepta si el texto recuperado muestra el identificador.
La búsqueda temática usa el buscador de la relatoría con el navegador:
selector de modo (#selectBuscador), campo #textoBuscador y botón «Buscar».
"""
from __future__ import annotations

import asyncio
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
    # El buscador codifica la consulta en la URL:
    #   /relatoria/buscador-jurisprudencia/texto/{desde}/{hasta}/{consulta}/0/0
    # y pinta los resultados en la tabla #tabla-resultado. Trata la consulta como
    # frase exacta y recomienda frases cortas.
    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        from datetime import date
        from urllib.parse import quote

        consulta_limpia = consulta.strip().strip('"')
        es_identificador = bool(_RE_CC.fullmatch(consulta_limpia))
        if not es_identificador:
            palabras = [w for w in consulta_limpia.split() if len(w) > 3]
            if len(palabras) > 3:
                elegidas = sorted(sorted(palabras, key=len, reverse=True)[:3], key=palabras.index)
                consulta_limpia = " ".join(elegidas)
        f_desde = f"{desde}-01-01" if desde else "1992-01-01"
        f_hasta = f"{hasta}-12-31" if hasta else date.today().isoformat()
        url = f"{self.portal['buscador'].rstrip('/')}/texto/{f_desde}/{f_hasta}/{quote(consulta_limpia)}/0/0"
        if not await self.nav.disponible():
            return [], Respuesta(estado="parcial", url_inicial=url, detalle="el buscador exige navegador y Playwright no está disponible")
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(url, wait_until="domcontentloaded")
                # Esperar a que aparezcan filas con enlaces o el aviso de «sin resultados».
                # El buscador muestra «No se encontraron resultados» mientras carga y
                # luego pinta la tabla: solo se acepta el aviso si persiste.
                filas = p.locator("#tabla-resultado a[href*='/relatoria/']")
                aviso = p.get_by_text("No se encontraron resultados", exact=False)
                aviso_seguido = 0
                inicio = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - inicio < 28:
                    if await filas.count() > 0:
                        break
                    try:
                        visible = await aviso.count() > 0 and await aviso.first.is_visible()
                    except Exception:
                        visible = False
                    aviso_seguido = aviso_seguido + 1 if visible else 0
                    if aviso_seguido >= 4 and asyncio.get_event_loop().time() - inicio > 8:
                        break
                    await p.wait_for_timeout(1000)
                await p.wait_for_timeout(1000)
                html = await p.content()
                candidatos = self._extraer_candidatos(html, p.url, max_resultados)
                estado = "ok" if candidatos else "sin_resultados"
                espera = int(asyncio.get_event_loop().time() - inicio)
                n_filas = await p.locator("#tabla-resultado tr").count()
                n_enlaces = await filas.count()
                return candidatos, Respuesta(estado=estado, url_inicial=url, url_final=p.url,
                                             codigo=r.status if r else None, contenido=html.encode(), tipo="text/html",
                                             detalle=None if candidatos else
                                             f"el buscador no mostró providencias para esa frase (espera {espera} s, filas en tabla {n_filas}, enlaces {n_enlaces}, aviso visible {aviso_seguido > 0})")
        except Exception as e:
            nombre = e.__class__.__name__
            return [], Respuesta(estado="timeout" if "Timeout" in nombre else "portal_no_disponible",
                                 url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    def _extraer_candidatos(self, html: str, base: str, limite: int) -> list[Candidato]:
        from ..comparar import parsear_fecha
        soup = BeautifulSoup(html, "lxml")
        vistos: set[str] = set()
        salida: list[Candidato] = []
        tabla = soup.select_one("#tabla-resultado")
        filas = tabla.find_all("tr") if tabla else []
        fuentes = filas if filas else soup.find_all("a", href=True)
        for f in fuentes:
            a = f.find("a", href=True) if filas else f
            if not a:
                continue
            href = a["href"]
            if "/relatoria/" not in href:
                continue
            texto = limpiar_texto(a.get_text(" "))
            m = _RE_CC.search(texto) or re.search(r"/relatoria/(?:Autos/)?(\d{4})/([A-Za-z]{1,2})-?(\d{1,4})-(\d{2})\.htm", href)
            if not m:
                continue
            if m.re is _RE_CC:
                ident = canonizar_identificador(m.group(0))
            else:
                ident = canonizar_identificador(f"{m.group(2)}-{int(m.group(3))}/{m.group(1)}")
            if ident in vistos:
                continue
            vistos.add(ident)
            contexto = limpiar_texto((f if filas else (a.find_parent(["li", "tr", "div", "p", "article"]) or a)).get_text(" "))[:500]
            fecha = None
            mf = re.search(r"Fecha de providencia\s*(\d{4}-\d{2}-\d{2})", contexto)
            if mf:
                fecha = parsear_fecha(mf.group(1))
            tema = None
            mt = re.search(r"Tema:\s*(.+?)(?:\s+Fecha de providencia|$)", contexto)
            if mt:
                tema = mt.group(1).strip()[:200]
            salida.append(Candidato(corporacion=self.corporacion, identificador=ident, url_oficial=urljoin(base, href),
                                    titulo=tema or texto[:200] or None, fecha=fecha,
                                    fragmento_descubrimiento=contexto or None, canales=["playwright"]))
            if len(salida) >= limite:
                break
        return salida
