"""Adaptador de la Corte Constitucional.

La relatoría publica cada sentencia en una ruta con patrón estable
(/relatoria/{año}/{TIPO}-{num}-{aa}.htm), lo que permite verificar una cita
conocida sin pasar por el buscador. La búsqueda temática usa el buscador de
la relatoría y, si este cambia, cae al navegador.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..comparar import canonizar_identificador, _RE_CC
from ..http import Respuesta
from ..modelos import Candidato, Corporacion
from ..texto import limpiar_texto
from .base import Adaptador


class CorteConstitucional(Adaptador):
    corporacion = Corporacion.CORTE_CONSTITUCIONAL

    def url_directa(self, identificador: str) -> Optional[str]:
        m = _RE_CC.search(identificador)
        if not m:
            return None
        can = canonizar_identificador(identificador)  # p. ej. SU-107/2024
        tipo, resto = can.split("-", 1)
        num, anio = resto.split("/")
        return self.portal["patron_sentencia"].format(anio=anio, tipo=tipo, num=num, aa=anio[-2:])

    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        params = {"q": consulta}
        if desde:
            params["desde"] = str(desde)
        if hasta:
            params["hasta"] = str(hasta)
        resp = await self.http.obtener(self.portal["buscador"], params=params)
        candidatos: list[Candidato] = []
        if resp.estado == "ok":
            candidatos = self._extraer_candidatos(resp.texto, resp.url_final or resp.url_inicial, max_resultados)
            if not candidatos and await self.nav.disponible():
                resp = await self.nav.obtener_html(resp.url_final or resp.url_inicial)
                if resp.estado == "ok":
                    candidatos = self._extraer_candidatos(resp.texto, resp.url_final or resp.url_inicial, max_resultados)
                    for c in candidatos:
                        c.canales = ["playwright"]
            if resp.estado == "ok" and not candidatos:
                resp.estado = "sin_resultados"
        return candidatos, resp

    def _extraer_candidatos(self, html: str, base: str, limite: int) -> list[Candidato]:
        soup = BeautifulSoup(html, "lxml")
        vistos: set[str] = set()
        salida: list[Candidato] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            texto = limpiar_texto(a.get_text(" "))
            m = _RE_CC.search(texto) or _RE_CC.search(href.replace("/", " ").replace("-", " ", 0))
            if not m and not re.search(r"/relatoria/\d{4}/", href):
                continue
            ident = canonizar_identificador(m.group(0)) if m else None
            if not ident:
                mm = re.search(r"/relatoria/(\d{4})/([A-Za-z]{1,2})-?(\d{1,4})-(\d{2})", href)
                if not mm:
                    continue
                ident = canonizar_identificador(f"{mm.group(2)}-{mm.group(3)}/{mm.group(1)}")
            if ident in vistos:
                continue
            vistos.add(ident)
            contexto = limpiar_texto(a.find_parent(["li", "tr", "div", "p"]).get_text(" ")) if a.find_parent(["li", "tr", "div", "p"]) else texto
            salida.append(Candidato(corporacion=self.corporacion, identificador=ident,
                                    url_oficial=urljoin(base, href), titulo=texto[:200] or None,
                                    fragmento_descubrimiento=contexto[:400] or None, canales=["buscador"]))
            if len(salida) >= limite:
                break
        return salida
