"""Navegador automatizado (Playwright) para portales dinámicos.

Se usa solo cuando el HTTP simple no basta (formularios JSF, paginación con
estado). Restringido a los dominios autorizados; no elude CAPTCHAs ni
controles técnicos.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from .http import USER_AGENT, Respuesta, dominio_autorizado

PLAYWRIGHT_HABILITADO = os.getenv("PLAYWRIGHT_HABILITADO", "1") not in ("0", "false", "False")
TIMEOUT_NAV_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "45000"))


class Navegador:
    """Un único navegador compartido; cada operación abre su propio contexto."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._cerrojo = asyncio.Lock()

    async def disponible(self) -> bool:
        if not PLAYWRIGHT_HABILITADO:
            return False
        try:
            await self._asegurar()
            return self._browser is not None
        except Exception:
            return False

    async def _asegurar(self) -> None:
        async with self._cerrojo:
            if self._browser is not None:
                return
            from playwright.async_api import async_playwright

            self._pw = await async_playwright().start()
            ruta = os.getenv("PLAYWRIGHT_CHROMIUM_PATH")
            kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if ruta:
                kwargs["executable_path"] = ruta
            self._browser = await self._pw.chromium.launch(**kwargs)

    async def cerrar(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._pw = None

    @asynccontextmanager
    async def pagina(self) -> AsyncIterator:
        await self._asegurar()
        contexto = await self._browser.new_context(user_agent=USER_AGENT, locale="es-CO")

        # Bloquear cualquier petición fuera de los dominios autorizados.
        async def _filtro(route):
            if dominio_autorizado(route.request.url):
                await route.continue_()
            else:
                await route.abort()

        await contexto.route("**/*", _filtro)
        pagina = await contexto.new_page()
        pagina.set_default_timeout(TIMEOUT_NAV_MS)
        try:
            yield pagina
        finally:
            await contexto.close()

    async def obtener_html(self, url: str, esperar_selector: Optional[str] = None) -> Respuesta:
        """Carga una URL con el navegador y devuelve el HTML renderizado."""
        if not dominio_autorizado(url):
            return Respuesta(estado="bloqueada", url_inicial=url, detalle="dominio fuera de la lista autorizada")
        inicio = datetime.now(timezone.utc)
        try:
            async with self.pagina() as p:
                resp = await p.goto(url, wait_until="domcontentloaded")
                if esperar_selector:
                    await p.wait_for_selector(esperar_selector)
                html = await p.content()
                codigo = resp.status if resp else None
        except Exception as e:  # playwright lanza TimeoutError y errores propios
            nombre = e.__class__.__name__
            estado = "timeout" if "Timeout" in nombre else "portal_no_disponible"
            return Respuesta(estado=estado, url_inicial=url, detalle=f"{nombre}: {str(e)[:200]}")
        lat = int((datetime.now(timezone.utc) - inicio).total_seconds() * 1000)
        estado = "ok" if codigo is None or codigo < 400 else ("bloqueada" if codigo in (401, 403, 429) else "portal_no_disponible")
        return Respuesta(estado=estado, url_inicial=url, url_final=url, codigo=codigo,
                         contenido=html.encode("utf-8"), tipo="text/html", latencia_ms=lat)


    async def inspeccionar(self, url: str, esperar_ms: int = 4000, patron_enlaces: Optional[str] = None,
                           clic_texto: Optional[str] = None) -> dict:
        """Describe una página renderizada: URL final, título, campos de formulario,
        botones, enlaces (filtrados por patrón) e iframes. Herramienta de
        mantenimiento para ajustar selectores cuando un portal cambia."""
        if not dominio_autorizado(url):
            return {"estado": "bloqueada", "detalle": "dominio fuera de la lista autorizada"}
        try:
            async with self.pagina() as p:
                resp = await p.goto(url, wait_until="domcontentloaded")
                if clic_texto:
                    try:
                        await p.get_by_text(clic_texto, exact=False).first.click(timeout=8000)
                    except Exception as e:  # se informa, no se aborta
                        clic_error = f"{e.__class__.__name__}: {str(e)[:120]}"
                    else:
                        clic_error = None
                else:
                    clic_error = None
                try:
                    await p.wait_for_load_state("networkidle", timeout=esperar_ms)
                except Exception:
                    pass
                await p.wait_for_timeout(min(esperar_ms, 3000))
                datos = await p.evaluate(
                    """(patron) => {
                        const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
                        const campos = [...document.querySelectorAll('input,select,textarea')].slice(0,80).map(e => ({
                            tag: e.tagName.toLowerCase(), id: e.id || null, name: e.name || null, type: e.type || null,
                            placeholder: e.placeholder || null, visible: vis(e),
                            etiqueta: (e.labels && e.labels[0] ? e.labels[0].innerText : '').trim().slice(0,60) || null,
                            opciones: e.tagName === 'SELECT' ? [...e.options].slice(0,25).map(o => o.text.trim()) : undefined }));
                        const botones = [...document.querySelectorAll('button,input[type=submit],input[type=button],a.ui-button,[role=button]')].slice(0,60).map(e => ({
                            tag: e.tagName.toLowerCase(), id: e.id || null, texto: (e.innerText || e.value || '').trim().slice(0,60), visible: vis(e) }));
                        const re = patron ? new RegExp(patron, 'i') : null;
                        const enlaces = [...document.querySelectorAll('a[href]')].map(a => ({ texto: (a.innerText||'').trim().slice(0,80), href: a.href }))
                            .filter(a => !re || re.test(a.href) || re.test(a.texto)).slice(0,80);
                        const iframes = [...document.querySelectorAll('iframe')].map(f => f.src).slice(0,10);
                        return { titulo: document.title, campos, botones, enlaces, iframes,
                                 texto_inicio: (document.body.innerText||'').replace(/\s+/g,' ').slice(0,600),
                                 caracteres_texto: (document.body.innerText||'').length };
                    }""", patron_enlaces)
                datos.update({"estado": "ok", "url_inicial": url, "url_final": p.url,
                              "codigo_http": resp.status if resp else None, "clic_error": clic_error})
                return datos
        except Exception as e:
            nombre = e.__class__.__name__
            return {"estado": "timeout" if "Timeout" in nombre else "portal_no_disponible",
                    "url_inicial": url, "detalle": f"{nombre}: {str(e)[:300]}"}
