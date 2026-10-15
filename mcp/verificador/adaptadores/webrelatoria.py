"""Adaptador para las relatorías de la Rama Judicial (aplicación WebRelatoria).

La CNDJ, la Corte Suprema y el buscador «tradicional» del Consejo de Estado
publican su jurisprudencia en la misma aplicación JSF/PrimeFaces
(`WebRelatoria`): formulario con estado de sesión, paginación y botones por
fila. El HTTP simple no basta: la búsqueda se hace con el navegador.

Comportamiento comprobado en vivo (octubre de 2026, CNDJ):
- Los campos están dentro del panel plegable «Criterios de búsqueda». Solo
  «Tema» tiene id estable (searchForm:temaInput); «Texto Completo» y los
  demás llevan ids generados (searchForm:j_idtNN) que cambian entre
  despliegues, por lo que se localizan por su rótulo.
- Las filas de resultado son `tr[data-rk]` dentro de `tbody[id$='jurisTable_data']`
  y describen la providencia en un `span[id$=':descrip']` con FECHA, PONENTE,
  DEMANDANTE, DEMANDADO y DESCRIPTOR-RESTRICTOR. No muestran el radicado:
  este aparece en la «titulación» (botón con icono `tituIcon`, que llena el
  diálogo `[id$='dialogInfoPanel']`).
- Cada fila tiene además un botón Word (`wordIcon`) y uno HTML (`htmlIcon`)
  que entregan el documento. Como el portal no expone una URL estable por
  providencia, el adaptador codifica en el fragmento de la URL la consulta y
  la clave de fila (`#wr?consulta=…&rk=…`) y la reproduce al leer.
- Sin resultados, el portal abre el diálogo `[id$='dialogMessPanel']` con
  «No se encontraron resultados, verifique los términos de consulta».
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Optional
from urllib.parse import parse_qs, quote, unquote

from bs4 import BeautifulSoup

from ..comparar import canonizar_identificador, identificadores_en_texto, parsear_fecha
from ..http import Respuesta
from ..modelos import Candidato, Corporacion
from ..portales import SELECTORES_WEBRELATORIA as SEL
from ..texto import html_a_texto, limpiar_texto
from .base import Adaptador

SEL_FILAS = "tbody[id$='jurisTable_data'] tr[data-rk]"
SEL_TITULACION = "[id$='dialogInfoPanel']"
SEL_SALIDA_TITULACION = "[id$='addInfoOutput'], [id$='dialogInfoPanel'] .ui-dialog-content"
MAX_TITULACIONES = int(os.getenv("WR_MAX_TITULACIONES", "3"))
_CAMPOS = ("FECHA", "PONENTE", "SALVAMENTO DE VOTO", "DEMANDANTE", "DEMANDADO", "DESCRIPTOR-RESTRICTOR",
           "DESCRIPTOR", "RESTRICTOR", "RADICADO", "RADICACIÓN", "RADICACION", "PROCESO", "PROVIDENCIA",
           "TIPO", "SALA", "DECISIÓN", "DECISION", "SECCIÓN", "SECCION", "NÚMERO", "NUMERO", "TEMA")


def _formatear_consulta(consulta: str) -> str:
    """El portal (Oracle Text) interpreta varias palabras sin comillas como
    operadores; las frases van entre comillas, las palabras sueltas no."""
    c = consulta.strip().strip('"').strip()
    c = re.sub(r"\s+", " ", c)
    if " " in c:
        return f'"{c}"'
    return c


def _campos_descripcion(texto: str) -> dict[str, str]:
    """Convierte «FECHA : 27/04/2022 PONENTE : NOMBRE …» en un diccionario."""
    patron = "|".join(re.escape(c) for c in sorted(_CAMPOS, key=len, reverse=True))
    partes = re.split(rf"\b({patron})\s*:\s*", texto)
    salida: dict[str, str] = {}
    for i in range(1, len(partes) - 1, 2):
        clave = partes[i].upper()
        valor = re.sub(r"\s+", " ", partes[i + 1]).strip(" |·")
        if valor and clave not in salida:
            salida[clave] = valor
    return salida


class WebRelatoria(Adaptador):
    corporacion: Corporacion

    # ----------------------------------------------------------- utilidades
    async def _expandir_criterios(self, p) -> bool:
        """Despliega el panel «Criterios de búsqueda» si los campos están ocultos."""
        tema = p.locator(SEL["campo_texto_respaldo"]).first
        try:
            if await tema.count() and await tema.is_visible():
                return True
            toggler = p.locator(".ui-panel-titlebar-toggler, [id$='_toggler']").first
            if await toggler.count():
                await toggler.click(timeout=3000)
            else:
                await p.get_by_text(SEL["panel_criterios"], exact=False).first.click(timeout=4000)
            for _ in range(6):
                if await tema.count() and await tema.is_visible():
                    return True
                await p.wait_for_timeout(500)
        except Exception:
            pass
        return False

    async def _campo_texto(self, p, preferido: str = "texto_completo") -> tuple[Optional[object], str]:
        """Localiza el campo «Texto Completo» por su rótulo; si no existe, «Tema»."""
        intentos = [
            ("texto_completo", SEL["campo_texto"]),
            ("texto_completo", "xpath=//*[contains(normalize-space(.), 'Texto Completo') and not(.//*[contains(normalize-space(.), 'Texto Completo')])]/following::input[@type='text'][1]"),
            ("tema", SEL["campo_texto_respaldo"]),
        ]
        if preferido == "tema":
            intentos = [i for i in intentos if i[0] == "tema"] + [i for i in intentos if i[0] != "tema"]
        for nombre, selector in intentos:
            try:
                loc = p.locator(selector).first
                if await loc.count():
                    return loc, nombre
            except Exception:
                continue
        return None, "ninguno"

    async def _escribir(self, campo, valor: str) -> str:
        try:
            await campo.click(timeout=3000)
            await campo.fill(valor, timeout=5000)
        except Exception:
            await campo.evaluate(
                "(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles:true}));"
                " e.dispatchEvent(new Event('change', {bubbles:true})); }", valor)
        try:
            return await campo.input_value(timeout=2000)
        except Exception:
            return ""

    async def _marcar_sentencia(self, p) -> str:
        """Marca el tipo «Sentencia» (por su rótulo, no por posición: en el Consejo
        de Estado la primera casilla es «Auto»)."""
        try:
            rotulo = p.locator("label", has_text=re.compile(r"^\s*Sentencia\s*$")).first
            if await rotulo.count() == 0:
                return "sin casilla"
            destino = await rotulo.get_attribute("for")
            casilla = p.locator(f"[id='{destino}']").first if destino else None
            if casilla is not None and await casilla.count() and await casilla.is_checked():
                return "ya marcada"
            await rotulo.click(timeout=3000)
            await p.wait_for_timeout(300)
            if casilla is not None and await casilla.count():
                return "marcada" if await casilla.is_checked() else "no se pudo marcar"
            return "clic en rótulo"
        except Exception as e:
            return f"error: {e.__class__.__name__}"

    async def _pagina_siguiente(self, p) -> bool:
        """Pasa a la página siguiente si el botón existe, está visible y habilitado."""
        try:
            siguiente = p.locator(SEL["siguiente_pagina"]).first
            if await siguiente.count() == 0 or not await siguiente.is_visible() or not await siguiente.is_enabled():
                return False
            await siguiente.click(timeout=3000)
            await p.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    async def _clic_buscar(self, p) -> None:
        await p.locator(SEL["boton_buscar"]).first.click(timeout=5000)

    async def _esperar_resultados(self, p, segundos: int = 20) -> tuple[str, str]:
        """Devuelve ('filas'|'aviso'|'tiempo', mensaje del portal)."""
        filas = p.locator(SEL_FILAS)
        aviso = p.locator(SEL["mensaje_portal"])
        for _ in range(segundos):
            if await filas.count() > 0:
                return "filas", ""
            try:
                if await aviso.count():
                    msg = (await aviso.first.inner_text()).strip()
                    if msg:
                        return "aviso", re.sub(r"^\s*Mensaje\s*", "", msg)[:200]
            except Exception:
                pass
            await p.wait_for_timeout(1000)
        return "tiempo", ""

    # Formas de diligenciar el formulario, en orden de preferencia. El portal no
    # documenta su sintaxis; la primera que devuelva filas se recuerda para las
    # consultas siguientes de la misma instancia.
    ESTRATEGIAS = (
        ("texto_completo", "frase"),     # "ilicitud sustancial"
        ("texto_completo", "libre"),     # ilicitud sustancial
        ("texto_completo", "palabra"),   # sustancial (la palabra más larga)
        ("tema", "libre"),               # índice temático
    )
    _estrategia_util: Optional[tuple[str, str]] = None

    @staticmethod
    def _valor_para(consulta: str, forma: str) -> str:
        base = re.sub(r"\s+", " ", consulta.strip().strip('"').strip())
        if forma == "frase":
            return _formatear_consulta(base)
        if forma == "palabra":
            palabras = [w for w in re.findall(r"[\wáéíóúñÁÉÍÓÚÑ]+", base) if len(w) > 3]
            return max(palabras, key=len) if palabras else base
        return base

    async def _ejecutar_busqueda(self, p, consulta: str, estrategia: Optional[tuple[str, str]] = None) -> tuple[str, str, dict]:
        """Diligencia el formulario y lanza la búsqueda. Devuelve (estado, mensaje, diagnóstico)."""
        campo_pref, forma = estrategia or self._estrategia_util or self.ESTRATEGIAS[0]
        diag: dict[str, str] = {}
        diag["panel"] = "desplegado" if await self._expandir_criterios(p) else "oculto"
        campo, nombre = await self._campo_texto(p, campo_pref)
        diag["campo"] = nombre
        if campo is None:
            return "sin_campo", "no se encontró el campo de texto del formulario", diag
        diag["valor"] = await self._escribir(campo, self._valor_para(consulta, forma))
        diag["sentencia"] = await self._marcar_sentencia(p)
        await self._clic_buscar(p)
        estado, msg = await self._esperar_resultados(p)
        await p.wait_for_timeout(800)
        if estado == "filas":
            self._estrategia_util = (nombre, forma)
        return estado, msg, diag

    async def _buscar_con_cascada(self, p, url: str, consulta: str, inicio: float) -> tuple[str, str, dict]:
        """Prueba las estrategias hasta que una devuelva filas o se agote el tiempo."""
        orden = list(self.ESTRATEGIAS)
        if self._estrategia_util in orden:
            orden.remove(self._estrategia_util)
            orden.insert(0, self._estrategia_util)
        intentos: list[str] = []
        estado, msg, diag = "tiempo", "", {}
        for i, est in enumerate(orden):
            if i and asyncio.get_event_loop().time() - inicio > 24:
                diag["intentos"] = "; ".join(intentos) + "; (sin tiempo para más)"
                return estado, msg, diag
            if i:
                await p.goto(url, wait_until="domcontentloaded")
            estado, msg, diag = await self._ejecutar_busqueda(p, consulta, est)
            intentos.append(f"{est[0]}/{est[1]}→{estado}")
            if estado == "filas" or estado == "sin_campo":
                break
        diag["intentos"] = "; ".join(intentos)
        return estado, msg, diag

    @staticmethod
    def _diag_texto(diag: dict) -> str:
        return " · ".join(f"{k}={v!r}" if k == "valor" else f"{k}={v}" for k, v in diag.items())

    def _url_fila(self, consulta: str, rk: str) -> str:
        return f"{self.portal['buscador']}#wr?consulta={quote(consulta)}&rk={quote(rk)}"

    # -------------------------------------------------------------- búsqueda
    async def buscar(self, consulta, desde=None, hasta=None, max_resultados=20):
        url = self.portal["buscador"]
        if not await self.nav.disponible():
            resp = await self.http.obtener(url)
            if resp.estado == "ok":
                resp.estado = "parcial"
                resp.detalle = "el portal exige navegador (formulario JSF) y Playwright no está disponible"
            return [], resp
        inicio = asyncio.get_event_loop().time()
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(url, wait_until="domcontentloaded")
                estado, msg, diag = await self._buscar_con_cascada(p, url, consulta, inicio)
                codigo = r.status if r else None
                if estado != "filas":
                    html = await p.content()
                    if estado == "aviso":
                        detalle = f"el portal respondió: {msg}"
                    elif estado == "tiempo":
                        detalle = "no aparecieron filas de resultado ni aviso del portal en 20 s"
                    else:
                        detalle = msg
                    return [], Respuesta(estado="sin_resultados" if estado == "aviso" else "parcial",
                                         url_inicial=url, url_final=p.url, codigo=codigo,
                                         contenido=html.encode(), tipo="text/html",
                                         detalle=f"{detalle} · {self._diag_texto(diag)}")
                candidatos: list[Candidato] = []
                paginas = 0
                html = ""
                while len(candidatos) < max_resultados and paginas < 5:
                    html = await p.content()
                    for c in self._extraer(html, consulta, desde, hasta):
                        if all(c.identificador != x.identificador for x in candidatos):
                            candidatos.append(c)
                    if len(candidatos) >= max_resultados or asyncio.get_event_loop().time() - inicio > 25:
                        break
                    if not await self._pagina_siguiente(p):
                        break
                    paginas += 1
                # Titulación (radicado y tesis) de las primeras filas, si queda tiempo.
                titulados = 0
                for c in candidatos[:MAX_TITULACIONES]:
                    if asyncio.get_event_loop().time() - inicio > 28:
                        break
                    if await self._titular(p, c):
                        titulados += 1
                total = len(candidatos)
                resp = Respuesta(estado="ok" if candidatos else "sin_resultados", url_inicial=url, url_final=p.url,
                                 codigo=codigo, contenido=html.encode(), tipo="text/html",
                                 detalle=f"{total} fila(s) en {paginas + 1} página(s); titulación leída en {titulados} · {self._diag_texto(diag)}")
                return candidatos[:max_resultados], resp
        except Exception as e:
            nombre = e.__class__.__name__
            estado = "timeout" if "Timeout" in nombre else "portal_no_disponible"
            return [], Respuesta(estado=estado, url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    def _extraer(self, html: str, consulta: str, desde: Optional[int], hasta: Optional[int]) -> list[Candidato]:
        soup = BeautifulSoup(html, "lxml")
        salida: list[Candidato] = []
        filas = soup.select(SEL_FILAS) or [
            f for f in soup.select(SEL["filas_resultado"]) if "ui-datatable-empty-message" not in (f.get("class") or [])
        ]
        for fila in filas:
            rk = fila.get("data-rk") or fila.get("data-ri")
            descrip = fila.select_one("span[id$=':descrip']") or fila
            texto = re.sub(r"\s+", " ", limpiar_texto(descrip.get_text(" ")))
            if len(texto) < 15:
                continue
            campos = _campos_descripcion(texto)
            idents = identificadores_en_texto(texto)
            ident = sorted(idents)[0] if idents else (f"fila-{rk}" if rk else None)
            if not ident:
                continue
            fecha = parsear_fecha(campos.get("FECHA", "")) if campos.get("FECHA") else None
            if not fecha:
                for m in re.finditer(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+\d{4}", texto):
                    fecha = parsear_fecha(m.group(0))
                    if fecha:
                        break
            if fecha and ((desde and fecha.year < desde) or (hasta and fecha.year > hasta)):
                continue
            ponente = campos.get("PONENTE") or None
            if not ponente:
                mp = re.search(r"(?:ponente|m\.?\s?p\.?)\s*[:.]?\s*([A-ZÁÉÍÓÚÑ][^|\n]{5,60})", texto, re.I)
                ponente = mp.group(1).strip() if mp else None
            # Fragmento sin nombres de partes: solo lo que describe la providencia.
            descriptor = campos.get("DESCRIPTOR-RESTRICTOR") or campos.get("DESCRIPTOR") or campos.get("TEMA")
            partes = [x for x in (campos.get("PROVIDENCIA"), campos.get("TIPO"), campos.get("SALA")) if x]
            fragmento = " · ".join(x for x in [f"DESCRIPTOR: {descriptor}" if descriptor else None] + partes if x) or texto[:300]
            salida.append(Candidato(corporacion=self.corporacion, identificador=canonizar_identificador(ident),
                                    url_oficial=self._url_fila(consulta, rk) if rk else None,
                                    titulo=descriptor[:200] if descriptor else None, fecha=fecha, ponente=ponente,
                                    sala=campos.get("SALA") or campos.get("SECCIÓN") or campos.get("SECCION"),
                                    fragmento_descubrimiento=fragmento[:400], canales=["playwright"]))
        return salida

    async def _titular(self, p, c: Candidato) -> bool:
        """Abre la titulación de la fila (botón tituIcon) para obtener radicado y tesis."""
        rk = self._rk_de(c.url_oficial)
        if not rk:
            return False
        try:
            fila = p.locator(f"tr[data-rk='{rk}']").first
            boton = fila.locator("button:has(.tituIcon)").first
            if await boton.count() == 0:
                return False
            await boton.click(timeout=3000)
            salida = p.locator(SEL_SALIDA_TITULACION).first
            texto = ""
            for _ in range(8):
                try:
                    texto = limpiar_texto(await salida.inner_text(timeout=1000)) if await salida.count() else ""
                except Exception:
                    texto = ""
                if len(texto) > 20:
                    break
                await p.wait_for_timeout(700)
            if len(texto) > 20:
                idents = identificadores_en_texto(texto)
                if idents and c.identificador.startswith("fila-"):
                    c.identificador = sorted(idents)[0]
                c.fragmento_descubrimiento = ((c.fragmento_descubrimiento or "") + " · TITULACIÓN: " + texto[:600])[:900]
            # Cerrar el diálogo para seguir con la siguiente fila.
            try:
                await p.keyboard.press("Escape")
                await p.wait_for_timeout(300)
            except Exception:
                pass
            return len(texto) > 20
        except Exception:
            return False

    @staticmethod
    def _rk_de(url: Optional[str]) -> Optional[str]:
        if not url or "#wr?" not in url:
            return None

        q = parse_qs(url.split("#wr?", 1)[1])
        return (q.get("rk") or [None])[0]

    # ---------------------------------------------------------- recuperación
    async def recuperar(self, url: str, identificador: str, forzar_navegador: bool = False):
        """Las filas del portal no tienen URL propia: se reproduce la búsqueda
        codificada en el fragmento y se abre el documento con el botón HTML."""
        if "#wr?" not in url:
            return await super().recuperar(url, identificador, forzar_navegador)
        q = parse_qs(url.split("#wr?", 1)[1])
        consulta = unquote((q.get("consulta") or [""])[0])
        rk = (q.get("rk") or [""])[0]
        base = url.split("#", 1)[0]
        if not consulta or not rk:
            return None, Respuesta(estado="no_hallada", url_inicial=url, detalle="la URL de fila no trae consulta y clave")
        if not await self.nav.disponible():
            return None, Respuesta(estado="portal_no_disponible", url_inicial=url, detalle="navegador no disponible")
        try:
            async with self.nav.pagina() as p:
                r = await p.goto(base, wait_until="domcontentloaded")
                estado, msg, diag = await self._buscar_con_cascada(p, base, consulta, asyncio.get_event_loop().time())
                if estado != "filas":
                    return None, Respuesta(estado="no_hallada", url_inicial=url, url_final=p.url,
                                           detalle=f"al repetir la búsqueda el portal no mostró filas ({msg or estado}) · {self._diag_texto(diag)}")
                fila = p.locator(f"tr[data-rk='{rk}']").first
                paginas = 0
                while await fila.count() == 0 and paginas < 5:
                    if not await self._pagina_siguiente(p):
                        break
                    paginas += 1
                if await fila.count() == 0:
                    return None, Respuesta(estado="no_hallada", url_inicial=url, url_final=p.url,
                                           detalle=f"la fila {rk} ya no aparece entre los resultados de la consulta")
                contenido, tipo, detalle = await self._abrir_documento(p, fila)
                if not contenido:
                    return None, Respuesta(estado="parcial", url_inicial=url, url_final=p.url,
                                           detalle=f"la fila existe pero no se obtuvo el documento: {detalle}")
                resp = Respuesta(estado="ok", url_inicial=url, url_final=url, codigo=r.status if r else None,
                                 contenido=contenido, tipo=tipo, detalle=detalle)
                if not self._contenido_util(resp):
                    resp.estado = "parcial"
                    resp.detalle = f"el documento recibido no tiene texto legible ({tipo}, {len(contenido)} bytes): {detalle}"
                    return None, resp
                return self._a_documento(resp, identificador, "playwright"), resp
        except Exception as e:
            nombre = e.__class__.__name__
            return None, Respuesta(estado="timeout" if "Timeout" in nombre else "portal_no_disponible",
                                   url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")

    async def _abrir_documento(self, p, fila) -> tuple[bytes, str, str]:
        """Pulsa el botón HTML (o Word) de la fila y captura el documento, ya
        llegue como descarga, como ventana nueva o como diálogo en la página."""
        detalle_descarga = "la fila no tiene botones HTML ni Word"
        for icono in ("htmlIcon", "wordIcon"):
            boton = fila.locator(f"button:has(.{icono})").first
            if await boton.count() == 0:
                continue
            # 1) descarga
            try:
                async with p.expect_download(timeout=12000) as dl:
                    await boton.click(timeout=3000)
                descarga = await dl.value
                ruta = await descarga.path()
                datos = open(ruta, "rb").read() if ruta else b""
                nombre = descarga.suggested_filename or ""
                tipo = "application/pdf" if datos[:5] == b"%PDF-" else ("text/html" if nombre.lower().endswith((".htm", ".html")) or b"<html" in datos[:2000].lower() else "application/octet-stream")
                if datos[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                    return b"", "application/msword", f"descarga binaria de Word ({nombre}); no se extrae texto de .doc binario"
                return datos, tipo, f"descarga {icono} ({nombre}, {len(datos)} bytes)"
            except Exception as e:
                detalle_descarga = f"{icono}: sin descarga ({e.__class__.__name__})"
            # 2) ventana nueva
            try:
                paginas_antes = len(p.context.pages)
                await p.wait_for_timeout(1500)
                if len(p.context.pages) > paginas_antes or len(p.context.pages) > 1:
                    nueva = p.context.pages[-1]
                    await nueva.wait_for_load_state("domcontentloaded", timeout=15000)
                    html = await nueva.content()
                    return html.encode(), "text/html", f"ventana nueva {icono} ({nueva.url})"
            except Exception:
                pass
            # 3) diálogo en la misma página
            try:
                dialogo = p.locator("[id$='dialogInfoPanel'], [id$='dialogHtmlPanel'], .ui-dialog:visible").first
                for _ in range(8):
                    if await dialogo.count() and len(await dialogo.inner_text()) > 2000:
                        html = await dialogo.evaluate("e => e.outerHTML")
                        return html.encode(), "text/html", f"diálogo en página ({icono})"
                    await p.wait_for_timeout(800)
            except Exception:
                pass
            try:
                await p.keyboard.press("Escape")
            except Exception:
                pass
        return b"", "", detalle_descarga

    def _contenido_util(self, resp: Respuesta) -> bool:
        if resp.es_pdf:
            return len(resp.contenido) > 1000
        texto, _ = html_a_texto(resp.texto)
        return len(texto) > 800


class CNDJ(WebRelatoria):
    corporacion = Corporacion.CNDJ


class CorteSuprema(WebRelatoria):
    corporacion = Corporacion.CORTE_SUPREMA


class ConsejoEstado(WebRelatoria):
    corporacion = Corporacion.CONSEJO_ESTADO
