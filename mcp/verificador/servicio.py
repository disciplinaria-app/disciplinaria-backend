"""Orquestador: implementa las operaciones que expone el servidor MCP.

Recupera, compara y estructura evidencia. No redacta ni califica la fuerza
jurídica de un precedente; devuelve señales textuales y estados técnicos
para que la skill decida con evidencia a la vista.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from .adaptadores import Adaptador, construir_adaptadores
from .cache import Corpus
from .comparar import (canonizar_identificador, comparar_fecha, comparar_identificador,
                       comparar_ponente, comparar_sala, identificadores_en_texto)
from .consultas import revisar_entrada, variantes
from .http import ClienteHTTP, Respuesta
from .modelos import (Campo, Candidato, Corporacion, DocumentoOficial, EstadoPortal, Pasaje,
                      Procedencia, ResultadoBusqueda, ResultadoLectura, ResultadoVerificacion,
                      Segmento, normalizar_corporacion)
from .navegador import Navegador
from .portales import PORTALES
from .texto import localizar_pasaje, posicion_a_localizador, rol_en_posicion, segmentar

TOPE_CONSULTAS_POR_BUSQUEDA = 8
TIEMPO_SEGURO_S = 50  # por debajo del límite habitual de un cliente MCP


class Servicio:
    def __init__(self, corpus: Optional[Corpus] = None) -> None:
        self.http = ClienteHTTP()
        self.nav = Navegador()
        self.adaptadores: dict[Corporacion, Adaptador] = construir_adaptadores(self.http, self.nav)
        self.corpus = corpus or Corpus()
        self.trabajos: dict[str, dict] = {}

    async def cerrar(self) -> None:
        await self.http.cerrar()
        await self.nav.cerrar()

    # ------------------------------------------------------------------ util
    def _procedencia(self, resp: Respuesta, canal: str) -> Procedencia:
        return Procedencia(url_inicial=resp.url_inicial, url_final=resp.url_final, codigo_http=resp.codigo,
                           consultada_en=resp.consultada_en, canal=canal, estado=resp.estado, detalle=resp.detalle)

    async def _obtener_documento(self, corp: Corporacion, identificador: str, url: Optional[str] = None,
                                 usar_corpus: bool = True) -> tuple[Optional[DocumentoOficial], Respuesta, str]:
        """Corpus → URL directa/HTTP → navegador. Devuelve (doc, respuesta, canal)."""
        adaptador = self.adaptadores[corp]
        if usar_corpus:
            doc = self.corpus.obtener(corp.value, canonizar_identificador(identificador))
            if doc:
                return doc, Respuesta(estado="ok", url_inicial=doc.url_oficial, url_final=doc.url_oficial,
                                      consultada_en=doc.consultada_en, detalle="corpus local"), "corpus"
        can = canonizar_identificador(identificador)
        destinos = [url] if url else adaptador.urls_directas(identificador)
        ultima: Optional[Respuesta] = None
        for destino in destinos:
            doc, resp = await adaptador.recuperar(destino, can)
            ultima = resp
            if doc and (url or can in identificadores_en_texto(doc.metadatos.get("title", "") + "\n" + doc.texto[:6000])):
                self.corpus.guardar(doc)
                return doc, resp, doc.canal
            if resp.estado in ("portal_no_disponible", "timeout", "bloqueada"):
                return None, resp, "http"
        # Sin URL directa válida: localizar por el buscador con el identificador como consulta.
        candidatos, resp = await adaptador.buscar(identificador, max_resultados=5)
        elegido = next((c for c in candidatos if c.identificador == can and c.url_oficial), None)
        if elegido:
            doc, resp2 = await adaptador.recuperar(elegido.url_oficial, can)
            if doc:
                self.corpus.guardar(doc)
                return doc, resp2, doc.canal
            resp = resp2
        directas_negativas = bool(destinos) and ultima is not None and ultima.estado == "sin_resultados"
        if resp.estado in ("ok", "sin_resultados") or (resp.estado == "parcial" and directas_negativas):
            if resp.estado == "parcial":
                resp.detalle = (resp.detalle or "") + " · el buscador no pudo ejecutarse"
            resp.estado = "no_hallada"
            resp.detalle = ("ni las rutas directas ni el buscador oficial devolvieron un documento que muestre el "
                            "identificador; puede que el identificador esté mal escrito o que el portal haya cambiado"
                            + (f" · último intento directo: {ultima.detalle}" if ultima and ultima.detalle else ""))
        return None, resp, "buscador"

    # ------------------------------------------------------------ verificar
    async def verificar_cita(self, corporacion: str, tipo_numero: Optional[str] = None, radicado: Optional[str] = None,
                             sala: Optional[str] = None, ponente: Optional[str] = None, fecha: Optional[str] = None,
                             ratio_invocada: Optional[str] = None, url_oficial: Optional[str] = None) -> ResultadoVerificacion:
        corp = normalizar_corporacion(corporacion)
        identificador = (tipo_numero or radicado or "").strip()
        advertencias: list[str] = []
        if not identificador:
            return ResultadoVerificacion(estado_global="no_hallada", corporacion=corp, campos={},
                                         advertencias=["se requiere tipo_numero o radicado"])
        if ratio_invocada:
            rev = revisar_entrada(ratio_invocada)
            if not rev.aceptada:
                return ResultadoVerificacion(estado_global="bloqueada", corporacion=corp, campos={},
                                             advertencias=["ratio_invocada rechazada por privacidad: " + "; ".join(rev.motivos)])
        doc, resp, canal = await self._obtener_documento(corp, identificador, url_oficial)
        if not doc:
            return ResultadoVerificacion(estado_global=resp.estado if resp.estado != "ok" else "no_hallada",
                                         corporacion=corp, campos={}, procedencia=self._procedencia(resp, canal),
                                         advertencias=[resp.detalle or "no se recuperó el documento oficial"])
        titulo = doc.metadatos.get("title", "")
        campos: dict[str, Campo] = {
            "identificador": comparar_identificador(identificador, doc.texto, titulo),
            "ponente": comparar_ponente(ponente, doc.texto),
            "fecha": comparar_fecha(fecha, doc.texto),
            "sala": comparar_sala(sala, doc.texto),
            "corporacion": Campo(estado="confirmado", valor_suministrado=corporacion, valor_oficial=PORTALES[corp]["nombre"],
                                 evidencia="documento recuperado del portal oficial de la corporación", localizador=doc.url_oficial),
        }
        pasaje = None
        solo_salvamento = False
        if ratio_invocada:
            frag, pos, sim = localizar_pasaje(doc.texto, ratio_invocada)
            rol = rol_en_posicion(segmentar(doc.texto), pos)
            pasaje = Pasaje(texto=frag, rol=rol, localizador=posicion_a_localizador(doc.texto, pos), similitud=round(sim, 3))
            solo_salvamento = rol in ("salvamento", "aclaracion")
            if sim < 0.35:
                advertencias.append("el pasaje más cercano tiene baja similitud con la ratio invocada; leer el documento antes de citar")
            if solo_salvamento:
                advertencias.append("el pasaje localizado está en un voto separado; no es ratio de la mayoría")
            if rol in ("argumento_parte", "decision_resenada"):
                advertencias.append("el pasaje está en una sección de antecedentes o reseña; verificar que no sea un argumento de parte o de instancia")
        if campos["identificador"].estado == "no_hallado":
            advertencias.append("el documento recuperado no muestra el identificador en su encabezado; puede ser una "
                                "página genérica del portal y no la providencia. Leer con leer_providencia antes de citar")
        estados = [c.estado for k, c in campos.items() if k != "corporacion"]
        if any(e == "discrepante" for e in estados):
            global_ = "discrepante"
        elif campos["identificador"].estado == "confirmado" and all(e in ("confirmado", "no_suministrado", "no_aplica") for e in estados):
            global_ = "confirmada"
        else:
            global_ = "parcial"
        return ResultadoVerificacion(estado_global=global_, corporacion=corp, campos=campos, url_oficial=doc.url_oficial,
                                     procedencia=Procedencia(url_inicial=resp.url_inicial, url_final=doc.url_oficial,
                                                             codigo_http=resp.codigo, consultada_en=doc.consultada_en,
                                                             sha256=doc.sha256, canal=canal, estado=resp.estado, detalle=resp.detalle),
                                     pasaje=pasaje, solo_en_salvamento=solo_salvamento, advertencias=advertencias)

    # --------------------------------------------------------------- buscar
    async def buscar_providencia(self, tesis: str, corporacion: str, desde: Optional[int] = None,
                                 hasta: Optional[int] = None, modo: str = "amplio",
                                 max_candidatos: int = 20, sentencia_hito: Optional[str] = None) -> ResultadoBusqueda:
        corp = normalizar_corporacion(corporacion)
        rev = revisar_entrada(tesis)
        if not rev.aceptada:
            return ResultadoBusqueda(estado="bloqueada", candidatos=[], canales_ejecutados=[], coverage_status="insuficiente",
                                     advertencias=["consulta rechazada por privacidad: " + "; ".join(rev.motivos)])
        adaptador = self.adaptadores[corp]
        canales: list[dict] = []
        candidatos: dict[str, Candidato] = {}
        advertencias: list[str] = []

        # Canal 0: corpus local.
        locales = self.corpus.buscar_texto(rev.texto.split()[:8], corporacion=corp.value)
        for d in locales:
            c = Candidato(corporacion=corp, identificador=d.identificador, url_oficial=d.url_oficial,
                          fragmento_descubrimiento=localizar_pasaje(d.texto, rev.texto)[0][:300], canales=["corpus"])
            candidatos[c.identificador] = c
        canales.append({"canal": "corpus", "estado": "ok" if locales else "sin_resultados", "resultados": len(locales)})

        # Canales 1-3: buscador oficial con variantes (HTTP → navegador dentro del adaptador).
        familias = variantes(rev.texto, PORTALES[corp]["nombre"], desde, hasta, sentencia_hito,
                             incluir_adversas=(modo == "amplio"))
        if modo != "amplio":
            familias = familias[:3]
        inicio = asyncio.get_event_loop().time()
        for v in familias[:TOPE_CONSULTAS_POR_BUSQUEDA]:
            if asyncio.get_event_loop().time() - inicio > TIEMPO_SEGURO_S:
                advertencias.append("se alcanzó el tiempo seguro de respuesta; cobertura parcial. Repita con modo='rapido' o con otra subregla")
                break
            encontrados, resp = await adaptador.buscar(v["consulta"], desde, hasta, max_candidatos)
            canales.append({"canal": "buscador", "familia": v["familia"], "consulta": v["consulta"],
                            "estado": resp.estado, "resultados": len(encontrados), "detalle": resp.detalle})
            for c in encontrados:
                if c.identificador not in candidatos:
                    candidatos[c.identificador] = c
                else:
                    for ch in c.canales:
                        if ch not in candidatos[c.identificador].canales:
                            candidatos[c.identificador].canales.append(ch)
            if resp.estado in ("portal_no_disponible", "timeout", "bloqueada"):
                advertencias.append(f"portal {PORTALES[corp]['nombre']}: {resp.estado} ({resp.detalle})")
                break

        estados = {c["estado"] for c in canales}
        if candidatos and not (estados & {"portal_no_disponible", "timeout", "bloqueada", "parcial"}):
            cobertura, estado = "completa", "ok"
        elif candidatos:
            cobertura, estado = "parcial", "parcial"
        elif estados & {"portal_no_disponible", "timeout", "bloqueada", "parcial"}:
            cobertura, estado = "insuficiente", next(iter(estados & {"portal_no_disponible", "timeout", "bloqueada", "parcial"}))
        else:
            cobertura, estado = "parcial", "sin_resultados"
            advertencias.append("ninguna variante devolvió resultados; una búsqueda vacía no demuestra inexistencia")
        salida = sorted(candidatos.values(), key=lambda c: (-(len(c.canales)), c.identificador))[:max_candidatos]
        for c in salida:
            c.verificado = False
        return ResultadoBusqueda(estado=estado, candidatos=salida, canales_ejecutados=canales,
                                 coverage_status=cobertura, advertencias=advertencias)

    # ----------------------------------------------------------------- leer
    async def leer_providencia(self, corporacion: str, identificador: Optional[str] = None, url_oficial: Optional[str] = None,
                               segmento: int = 0, tamano: int = 3500) -> ResultadoLectura:
        corp = normalizar_corporacion(corporacion)
        if not identificador and not url_oficial:
            return ResultadoLectura(estado="no_hallada", advertencias=["se requiere identificador o url_oficial"])
        ident = identificador or url_oficial.rsplit("/", 1)[-1]
        doc, resp, canal = await self._obtener_documento(corp, ident, url_oficial)
        if not doc:
            return ResultadoLectura(estado=resp.estado if resp.estado != "ok" else "no_hallada",
                                    advertencias=[resp.detalle or "no se recuperó el documento"])
        bloques = segmentar(doc.texto, tamano)
        if not bloques:
            return ResultadoLectura(estado="parcial", advertencias=["el documento no contiene texto extraíble"])
        i = max(0, min(segmento, len(bloques) - 1))
        b = bloques[i]
        roles = {}
        for bl in bloques:
            roles[bl.rol] = roles.get(bl.rol, 0) + 1
        return ResultadoLectura(
            estado="ok",
            documento={"corporacion": corp.value, "identificador": doc.identificador, "url_oficial": doc.url_oficial,
                       "sha256": doc.sha256, "consultada_en": doc.consultada_en.isoformat(), "canal": canal,
                       "tipo_contenido": doc.tipo_contenido, "caracteres": len(doc.texto), "segmentos": len(bloques),
                       "secciones_detectadas": roles, "metadatos": {k: v for k, v in doc.metadatos.items() if k in ("title", "paginas", "description")}},
            segmento=Segmento(indice=i, total=len(bloques), texto=b.texto, localizador=b.localizador, rol_estimado=b.rol),
            advertencias=["el rol de sección es una estimación estructural; confirmar leyendo el contexto"] if b.rol == "desconocido" else [],
        )

    # ---------------------------------------------------------- actualizar
    async def actualizar_linea(self, subregla: str, sentencia_hito: str, corporacion: str,
                               fecha_corte: Optional[str] = None, max_candidatos: int = 20) -> dict:
        corp = normalizar_corporacion(corporacion)
        corte = date.fromisoformat(fecha_corte) if fecha_corte else date.today()
        desde, hasta = corte.year - 4, corte.year
        res = await self.buscar_providencia(subregla, corporacion, desde, hasta, "amplio", max_candidatos, sentencia_hito)
        hito_can = canonizar_identificador(sentencia_hito)
        decisiones = []
        for c in res.candidatos:
            if c.identificador == hito_can:
                continue
            frag = c.fragmento_descubrimiento or ""
            cita_hito = hito_can in identificadores_en_texto(frag)
            senal = any(p in frag.lower() for p in ("rectific", "modific", "apart", "super", "cambio de precedente", "distingu"))
            decisiones.append({**c.model_dump(mode="json"), "cita_hito_en_fragmento": cita_hito,
                               "posible_cambio_precedente": senal})
        return {"estado": res.estado, "ventana": {"desde": desde, "hasta": hasta, "fecha_corte": corte.isoformat()},
                "sentencia_hito": hito_can, "decisiones": decisiones, "canales_ejecutados": res.canales_ejecutados,
                "coverage_status": res.coverage_status, "advertencias": res.advertencias + [
                    "`posible_cambio_precedente` es una señal textual del fragmento de descubrimiento, no una clasificación jurídica; "
                    "verificar cada decisión con verificar_cita y leer_providencia"]}

    # --------------------------------------------------------------- estado
    def estado_verificacion(self, trabajo_id: str) -> dict:
        t = self.trabajos.get(trabajo_id)
        if not t:
            return {"estado": "no_hallada", "detalle": "trabajo desconocido o expirado"}
        return {k: v for k, v in t.items() if k != "tarea"}

    async def lanzar_trabajo(self, nombre: str, corrutina) -> str:
        trabajo_id = uuid.uuid4().hex[:12]
        self.trabajos[trabajo_id] = {"trabajo_id": trabajo_id, "operacion": nombre, "estado": "pendiente",
                                     "iniciado_en": datetime.now(timezone.utc).isoformat(), "resultado": None, "error": None}

        async def _correr():
            try:
                r = await corrutina
                self.trabajos[trabajo_id].update(estado="terminado", resultado=r.model_dump(mode="json") if hasattr(r, "model_dump") else r)
            except Exception as e:  # el error se reporta, no se traduce a "no existe"
                self.trabajos[trabajo_id].update(estado="error", error=f"{e.__class__.__name__}: {e}")

        self.trabajos[trabajo_id]["tarea"] = asyncio.create_task(_correr())
        return trabajo_id

    # ------------------------------------------------------------ diagnóstico
    async def diagnosticar_portales(self) -> dict:
        salud = await asyncio.gather(*(a.salud() for a in self.adaptadores.values()))
        return {"comprobado_en": datetime.now(timezone.utc).isoformat(),
                "navegador_disponible": await self.nav.disponible(),
                "portales": [s.model_dump(mode="json") for s in salud],
                "corpus": {"documentos": len(self.corpus.listar()), "directorio": str(self.corpus.dir)},
                "nota": "un portal 'portal_no_disponible' o 'timeout' no significa que la jurisprudencia no exista; reintentar o usar ruta alternativa"}
