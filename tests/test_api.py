"""Pruebas de los endpoints del triage de correspondencia."""

import pytest
from fastapi.testclient import TestClient

import main
from agents import agente_triage
from tests.utilidades import construir_pdf_texto

RESPUESTA = {
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


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", "clave-de-prueba")

    async def ejecutar(**_kwargs):
        return dict(RESPUESTA), []

    monkeypatch.setattr(agente_triage, "ejecutar", ejecutar)
    with TestClient(main.app) as cliente:
        yield cliente


class TestDisponibilidad:
    def test_raiz_y_health_siguen_respondiendo(self, cliente):
        assert cliente.get("/").status_code == 200
        assert cliente.get("/health").json() == {"status": "ok"}

    def test_diagnostico_informa_el_estado_del_reconocimiento_optico(self, cliente):
        datos = cliente.get("/correo/diagnostico").json()
        assert set(datos) == {
            "ocr_disponible",
            "idioma_espanol_disponible",
            "componentes_faltantes",
            "limite_paginas_ocr",
            "limite_bytes_adjunto",
        }

    def test_sin_clave_configurada_el_triage_responde_503(self, monkeypatch):
        monkeypatch.setattr(main, "OPENROUTER_API_KEY", "")
        with TestClient(main.app) as cliente:
            respuesta = cliente.post(
                "/correo/triage/json",
                json={"remitente": "x@y.gov.co", "asunto": "Oficio"},
            )
        assert respuesta.status_code == 503


class TestTriageConAdjuntos:
    def test_clasifica_el_correo_y_alerta_la_entidad_equivocada(self, cliente):
        pdf = construir_pdf_texto(
            ["LA PREVISORA S.A. COMPANIA DE SEGUROS", "Respuesta al radicado CNDJ-2025-0412"]
        )
        respuesta = cliente.post(
            "/correo/triage",
            data={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio CNDJ-2025-0412",
                "cuerpo": "Cordial saludo, adjunto damos respuesta.",
                "fecha_recepcion": "2025-10-01",
                "entidad_interpelada": "Fiduprevisora S.A.",
                "radicado_enviado": "CNDJ-2025-0412",
            },
            files=[("archivos", ("respuesta.pdf", pdf, "application/pdf"))],
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["urgencia"] == "ALTA"
        assert "ENTIDAD_DISTINTA" in {a["codigo"] for a in ficha["alertas"]}
        assert ficha["cotejo"]["entidad_estado"] == "DIFIERE"
        assert ficha["documentos"][0]["metodo"] == "TEXTO_NATIVO"
        assert "texto" not in ficha["documentos"][0]

    def test_correo_sin_adjuntos(self, cliente):
        respuesta = cliente.post(
            "/correo/triage",
            data={"remitente": "notificaciones@previsora.gov.co", "cuerpo": "Acusamos recibo."},
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["documentos"] == []

    def test_rechaza_un_exceso_de_adjuntos(self, cliente):
        pdf = construir_pdf_texto(["Documento"])
        archivos = [
            ("archivos", (f"anexo{i}.pdf", pdf, "application/pdf"))
            for i in range(main.MAX_ADJUNTOS + 1)
        ]
        respuesta = cliente.post(
            "/correo/triage",
            data={"remitente": "x@y.gov.co"},
            files=archivos,
        )
        assert respuesta.status_code == 413

    def test_remitente_es_obligatorio(self, cliente):
        assert cliente.post("/correo/triage", data={"asunto": "Oficio"}).status_code == 422


class TestTriageEnTexto:
    def test_variante_json_para_capas_de_ingesta_externas(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio CNDJ-2025-0412",
                "cuerpo": "<p>Adjunto damos respuesta.</p>",
                "fecha_recepcion": "2025-10-01",
                "contexto": {
                    "entidad_interpelada": "Fiduprevisora S.A.",
                    "radicado_enviado": "CNDJ-2025-0412",
                },
                "adjuntos": [
                    {
                        "nombre": "respuesta.pdf",
                        "texto": "LA PREVISORA S.A. informa que no es competente. Radicado CNDJ-2025-0412.",
                    }
                ],
            },
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["tipo_acto"] == "DEVOLUCION_POR_COMPETENCIA"
        assert "ENTIDAD_DISTINTA" in {a["codigo"] for a in ficha["alertas"]}
        assert ficha["documentos"][0]["nombre"] == "respuesta.pdf"


class TestAdjuntoEnBase64:
    def test_el_servidor_extrae_el_pdf_remitido_en_base64(self, cliente):
        """
        Forma que emplea un flujo de Power Automate, que no sabe leer PDF: el
        archivo viaja íntegro y la extracción queda del lado del servidor.
        """
        import base64

        pdf = construir_pdf_texto(
            ["LA PREVISORA S.A. COMPANIA DE SEGUROS", "Respuesta al radicado CNDJ-2025-0999"]
        )
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio CNDJ-2025-0412",
                "cuerpo": "Adjunto damos respuesta.",
                "contexto": {
                    "entidad_interpelada": "Fiduprevisora S.A.",
                    "radicado_enviado": "CNDJ-2025-0412",
                },
                "adjuntos": [
                    {
                        "nombre": "respuesta.pdf",
                        "contenido_base64": base64.b64encode(pdf).decode(),
                    }
                ],
            },
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["documentos"][0]["metodo"] == "TEXTO_NATIVO"
        assert ficha["documentos"][0]["paginas"] == 1
        assert ficha["cotejo"]["radicado_estado"] == "NO_COINCIDE"

    def test_base64_invalido_se_advierte_sin_interrumpir_el_triage(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "x@y.gov.co",
                "adjuntos": [{"nombre": "roto.pdf", "contenido_base64": "no-es-base64-%%%"}],
            },
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["documentos"][0]["metodo"] == "NINGUNO"
        assert "DOCUMENTO_ILEGIBLE" in {a["codigo"] for a in ficha["alertas"]}

    def test_adjunto_sin_texto_ni_contenido_se_rechaza(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={"remitente": "x@y.gov.co", "adjuntos": [{"nombre": "vacio.pdf"}]},
        )
        assert respuesta.status_code == 422


class TestBase64Plegado:
    def test_admite_base64_plegado_en_lineas_como_el_de_mime(self, cliente):
        import base64
        import textwrap

        pdf = construir_pdf_texto(["LA PREVISORA S.A.", "Radicado CNDJ-2025-0412"])
        plegado = "\n".join(textwrap.wrap(base64.b64encode(pdf).decode(), 76))
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "x@y.gov.co",
                "adjuntos": [{"nombre": "respuesta.pdf", "contenido_base64": plegado}],
            },
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["documentos"][0]["metodo"] == "TEXTO_NATIVO"
