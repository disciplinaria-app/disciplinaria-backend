"""
Pruebas de la orquestación del triage.

El agente se sustituye por una función controlada: lo que aquí se verifica no
es la lectura del modelo, sino las garantías que el orquestador debe sostener
sobre ella —cómputo de términos, validación del catálogo, fusión de alertas y
continuidad del servicio cuando el agente falla—.
"""

import asyncio
from datetime import date, timedelta

import pytest

from agents import agente_triage
from models.schemas import ContextoEnvio
from services import triage
from tests.utilidades import construir_pdf_texto

CONTEXTO = ContextoEnvio(
    entidad_interpelada="Fiduprevisora S.A.",
    radicado_enviado="CNDJ-2025-0412",
    asunto_enviado="Oficio CNDJ-2025-0412",
)

RESPUESTA_BASE = {
    "entidad_remitente": "La Previsora S.A. Compañía de Seguros",
    "tipo_acto": "DEVOLUCION_POR_COMPETENCIA",
    "materia": "La entidad advierte que la comunicación fue dirigida por error.",
    "resumen": "La Previsora informa que el oficio correspondía a Fiduprevisora S.A.",
    "radicados": ["CNDJ-2025-0412"],
    "expedientes": [],
    "requiere_actuacion": True,
    "actuacion_sugerida": "Remitir nuevamente el oficio a Fiduprevisora S.A.",
    "termino": {"fecha_limite": None, "fundamento": None},
    "alertas": [],
    "urgencia": "BAJA",
}


def _stub(respuesta: dict, advertencias: list[str] | None = None):
    """Sustituye al agente por una respuesta fija."""

    async def ejecutar(**_kwargs):
        return dict(respuesta), list(advertencias or [])

    return ejecutar


_SIN_INDICAR = object()


def _procesar(monkeypatch, respuesta=_SIN_INDICAR, **kwargs):
    # Se distingue «no se indicó respuesta» de «la respuesta es un objeto
    # vacío», que es uno de los casos a probar.
    if respuesta is _SIN_INDICAR:
        respuesta = RESPUESTA_BASE
    monkeypatch.setattr(agente_triage, "ejecutar", _stub(respuesta))
    parametros = dict(
        remitente="notificaciones@previsora.gov.co",
        asunto="RE: Oficio CNDJ-2025-0412",
        cuerpo="Cordial saludo, adjunto damos respuesta a su comunicación.",
        fecha_recepcion="2025-10-01",
        contexto=CONTEXTO,
        adjuntos=[],
    )
    parametros.update(kwargs)
    return asyncio.run(triage.procesar(**parametros))


class TestDeteccionDeEntidadEquivocada:
    def test_alerta_cuando_responde_una_entidad_distinta_a_la_interpelada(self, monkeypatch):
        ficha = _procesar(monkeypatch)
        alertas = {a.codigo: a for a in ficha.alertas}
        assert "ENTIDAD_DISTINTA" in alertas
        assert alertas["ENTIDAD_DISTINTA"].severidad == "ALTA"
        assert ficha.cotejo.entidad_estado == "DIFIERE"
        assert ficha.tipo_acto == "DEVOLUCION_POR_COMPETENCIA"

    def test_la_urgencia_se_eleva_a_la_de_la_alerta_mas_grave(self, monkeypatch):
        """
        El agente propuso urgencia BAJA. Una alerta de severidad ALTA no puede
        quedar sepultada bajo la estimación del modelo.
        """
        ficha = _procesar(monkeypatch)
        assert ficha.urgencia == "ALTA"

    def test_sin_discrepancia_no_se_levanta_la_alerta(self, monkeypatch):
        respuesta = dict(RESPUESTA_BASE, entidad_remitente="Fiduprevisora S.A.")
        ficha = _procesar(monkeypatch, respuesta)
        assert "ENTIDAD_DISTINTA" not in {a.codigo for a in ficha.alertas}
        assert ficha.cotejo.entidad_estado == "COINCIDE"


class TestFusionDeAlertas:
    def test_la_concurrencia_de_cotejo_y_agente_se_marca_como_ambos(self, monkeypatch):
        respuesta = dict(
            RESPUESTA_BASE,
            alertas=[
                {
                    "codigo": "ENTIDAD_DISTINTA",
                    "descripcion": "Suscribe La Previsora, no Fiduprevisora.",
                    "severidad": "MEDIA",
                }
            ],
        )
        ficha = _procesar(monkeypatch, respuesta)
        alerta = next(a for a in ficha.alertas if a.codigo == "ENTIDAD_DISTINTA")
        assert alerta.origen == "AMBOS"
        assert alerta.severidad == "ALTA"  # conserva la severidad mayor
        assert "Suscribe La Previsora" in alerta.descripcion

    def test_las_alertas_se_ordenan_por_severidad(self, monkeypatch):
        respuesta = dict(
            RESPUESTA_BASE,
            alertas=[
                {"codigo": "REQUIERE_RESPUESTA", "descripcion": "Exige respuesta.", "severidad": "BAJA"},
                {"codigo": "SIN_SUSCRIPCION", "descripcion": "Sin firma.", "severidad": "MEDIA"},
            ],
        )
        ficha = _procesar(monkeypatch, respuesta)
        severidades = [a.severidad for a in ficha.alertas]
        assert severidades == sorted(severidades, key=lambda s: {"ALTA": 0, "MEDIA": 1, "BAJA": 2}[s])

    def test_se_descartan_los_codigos_ajenos_al_catalogo(self, monkeypatch):
        respuesta = dict(
            RESPUESTA_BASE,
            alertas=[{"codigo": "ASUNTO_CURIOSO", "descripcion": "Inventada.", "severidad": "ALTA"}],
        )
        ficha = _procesar(monkeypatch, respuesta)
        assert "ASUNTO_CURIOSO" not in {a.codigo for a in ficha.alertas}
        assert any("ASUNTO_CURIOSO" in a for a in ficha.advertencias)


class TestComputoDeTerminos:
    def test_los_dias_restantes_los_calcula_el_codigo_no_el_modelo(self, monkeypatch):
        limite = date.today() + timedelta(days=5)
        respuesta = dict(
            RESPUESTA_BASE,
            termino={"fecha_limite": limite.isoformat(), "fundamento": "Diez días hábiles"},
        )
        ficha = _procesar(monkeypatch, respuesta)
        assert ficha.termino.dias_restantes == 5
        alerta = next(a for a in ficha.alertas if a.codigo == "TERMINO_CORRIENDO")
        assert alerta.severidad == "MEDIA"

    def test_termino_inminente_eleva_la_severidad(self, monkeypatch):
        limite = date.today() + timedelta(days=2)
        respuesta = dict(RESPUESTA_BASE, termino={"fecha_limite": limite.isoformat()})
        ficha = _procesar(monkeypatch, respuesta)
        alerta = next(a for a in ficha.alertas if a.codigo == "TERMINO_CORRIENDO")
        assert alerta.severidad == "ALTA"

    def test_termino_vencido_se_advierte_con_mencion_a_la_preclusion(self, monkeypatch):
        limite = date.today() - timedelta(days=4)
        respuesta = dict(RESPUESTA_BASE, termino={"fecha_limite": limite.isoformat()})
        ficha = _procesar(monkeypatch, respuesta)
        assert ficha.termino.dias_restantes == -4
        alerta = next(a for a in ficha.alertas if a.codigo == "TERMINO_CORRIENDO")
        assert alerta.severidad == "ALTA"
        assert "precluida" in alerta.descripcion

    def test_fecha_en_formato_no_interpretable_se_descarta_y_se_advierte(self, monkeypatch):
        respuesta = dict(
            RESPUESTA_BASE,
            termino={"fecha_limite": "15 de octubre", "fundamento": "Diez días"},
        )
        ficha = _procesar(monkeypatch, respuesta)
        assert ficha.termino.fecha_limite is None
        assert ficha.termino.dias_restantes is None
        assert any("no interpretable" in a for a in ficha.advertencias)

    def test_sin_termino_el_campo_queda_vacio(self, monkeypatch):
        ficha = _procesar(monkeypatch)
        assert ficha.termino is None


class TestValidacionDelTipoDeActo:
    def test_tipo_ajeno_al_catalogo_se_registra_como_otro(self, monkeypatch):
        respuesta = dict(RESPUESTA_BASE, tipo_acto="OFICIO_RARO")
        ficha = _procesar(monkeypatch, respuesta)
        assert ficha.tipo_acto == "OTRO"
        assert any("OFICIO_RARO" in a for a in ficha.advertencias)

    def test_tipo_en_minusculas_se_normaliza(self, monkeypatch):
        respuesta = dict(RESPUESTA_BASE, tipo_acto="requerimiento")
        ficha = _procesar(monkeypatch, respuesta)
        assert ficha.tipo_acto == "REQUERIMIENTO"


class TestContinuidadAnteFallaDelAgente:
    def test_la_ficha_se_entrega_con_las_verificaciones_automaticas(self, monkeypatch):
        """
        Si el agente falla, las alertas deterministas deben llegar igual: un
        anexo anunciado y no recibido debe avisarse sin intervención del modelo.
        """

        async def fallar(**_kwargs):
            raise RuntimeError("tiempo de espera agotado")

        monkeypatch.setattr(agente_triage, "ejecutar", fallar)
        ficha = asyncio.run(
            triage.procesar(
                remitente="notificaciones@previsora.gov.co",
                asunto="RE: Oficio CNDJ-2025-0412",
                cuerpo="Adjunto remitimos la respuesta solicitada.",
                contexto=CONTEXTO,
            )
        )
        assert ficha.tipo_acto == "OTRO"
        assert "SIN_ADJUNTO_ANUNCIADO" in {a.codigo for a in ficha.alertas}
        assert any("tiempo de espera agotado" in a for a in ficha.advertencias)
        assert ficha.materia
        assert ficha.resumen


class TestProcesamientoDeAdjuntos:
    def test_coteja_los_radicados_hallados_en_el_pdf(self, monkeypatch):
        pdf = construir_pdf_texto(
            [
                "LA PREVISORA S.A. COMPANIA DE SEGUROS",
                "Respuesta al radicado CNDJ-2025-0999",
            ]
        )
        ficha = _procesar(monkeypatch, archivos=[("respuesta.pdf", pdf)])
        assert ficha.cotejo.radicado_estado == "NO_COINCIDE"
        assert "RADICADO_NO_COINCIDE" in {a.codigo for a in ficha.alertas}
        assert ficha.documentos[0].metodo == "TEXTO_NATIVO"

    def test_adjunto_ilegible_genera_alerta_de_severidad_alta(self, monkeypatch):
        ficha = _procesar(monkeypatch, archivos=[("anexo.docx", b"PK\x03\x04 no es pdf")])
        alerta = next(a for a in ficha.alertas if a.codigo == "DOCUMENTO_ILEGIBLE")
        assert alerta.severidad == "ALTA"
        assert "anexo.docx" in alerta.descripcion

    def test_el_texto_de_los_adjuntos_no_viaja_en_la_respuesta(self, monkeypatch):
        """El sistema entrega la ficha estructurada, no el contenido del documento."""
        pdf = construir_pdf_texto(["LA PREVISORA S.A.", "Radicado CNDJ-2025-0412"])
        ficha = _procesar(monkeypatch, archivos=[("respuesta.pdf", pdf)])
        assert ficha.documentos[0].texto  # disponible en memoria para el análisis
        serializada = ficha.model_dump()
        assert "texto" not in serializada["documentos"][0]
        assert "PREVISORA" not in ficha.model_dump_json()


class TestInferenciaDeContexto:
    def test_deduce_la_entidad_interpelada_de_la_cadena_y_lo_advierte(self, monkeypatch):
        cuerpo = (
            "Cordial saludo, damos respuesta.\n"
            "De: Despacho CNDJ\n"
            "Para: Fiduprevisora S.A.\n"
            "Asunto: Oficio CNDJ-2025-0412\n"
        )
        ficha = _procesar(
            monkeypatch,
            cuerpo=cuerpo,
            contexto=ContextoEnvio(radicado_enviado="CNDJ-2025-0412"),
        )
        assert ficha.cotejo.entidad_estado == "DIFIERE"
        assert any("se dedujo" in a for a in ficha.advertencias)

    def test_sin_contexto_el_cotejo_de_entidad_queda_indeterminado(self, monkeypatch):
        ficha = _procesar(monkeypatch, cuerpo="Damos respuesta.", contexto=None)
        assert ficha.cotejo.entidad_estado == "INDETERMINADO"
        assert "ENTIDAD_DISTINTA" not in {a.codigo for a in ficha.alertas}


class TestRespuestasMalformadasDelAgente:
    def test_un_json_que_no_es_objeto_no_derriba_el_triage(self, monkeypatch):
        """
        El extractor de JSON admite cualquier estructura válida. Si el agente
        devuelve una lista, el orquestador debe degradar a cotejo, no fallar.
        """

        async def ejecutar(**_kwargs):
            return ["no", "es", "un", "objeto"], []

        monkeypatch.setattr(agente_triage, "ejecutar", ejecutar)
        ficha = asyncio.run(
            triage.procesar(
                remitente="notificaciones@previsora.gov.co",
                cuerpo="Adjunto remitimos la respuesta.",
                contexto=CONTEXTO,
            )
        )
        assert ficha.tipo_acto == "OTRO"
        assert any("estructura JSON inesperada" in a for a in ficha.advertencias)
        assert "SIN_ADJUNTO_ANUNCIADO" in {a.codigo for a in ficha.alertas}

    def test_respuesta_vacia_del_agente(self, monkeypatch):
        ficha = _procesar(monkeypatch, {})
        assert ficha.tipo_acto == "OTRO"
        assert ficha.materia
        assert ficha.requiere_actuacion is False
