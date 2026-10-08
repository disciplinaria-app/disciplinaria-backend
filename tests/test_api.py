"""Pruebas de los endpoints del triage de correspondencia."""

import base64
import textwrap

import pytest
from fastapi.testclient import TestClient

import main
from agents import agente_triage
from tests.utilidades import construir_pdf_texto

CLAVE = "clave-de-prueba-0001"
CLAVE_ALTERNA = "clave-de-prueba-0002"
CABECERA = {"X-API-Key": CLAVE}

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

CONTEXTO = {
    "entidad_interpelada": "Fiduprevisora S.A.",
    "radicado_enviado": "CNDJ-2025-0412",
}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", "clave-del-modelo")
    monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset({CLAVE, CLAVE_ALTERNA}))

    async def ejecutar(**_kwargs):
        return dict(RESPUESTA), []

    monkeypatch.setattr(agente_triage, "ejecutar", ejecutar)
    with TestClient(main.app) as cliente:
        yield cliente


class TestDisponibilidad:
    def test_raiz_y_health_siguen_respondiendo(self, cliente):
        assert cliente.get("/").status_code == 200
        assert cliente.get("/health").json() == {"status": "ok"}

    def test_el_diagnostico_no_exige_clave(self, cliente):
        """
        Debe poder consultarse antes de configurar la clave, pues sirve para
        verificar el despliegue, y no revela dato alguno de la correspondencia.
        """
        datos = cliente.get("/correo/diagnostico").json()
        assert set(datos) == {
            "ocr_disponible",
            "idioma_espanol_disponible",
            "componentes_faltantes",
            "limite_paginas_ocr",
            "limite_bytes_adjunto",
        }

    def test_sin_clave_del_modelo_el_triage_responde_503(self, monkeypatch):
        monkeypatch.setattr(main, "OPENROUTER_API_KEY", "")
        monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset({CLAVE}))
        with TestClient(main.app) as cliente:
            respuesta = cliente.post(
                "/correo/triage/json",
                json={"remitente": "x@y.gov.co"},
                headers=CABECERA,
            )
        assert respuesta.status_code == 503


class TestAutenticacion:
    def _solicitud(self, cliente, headers=None):
        return cliente.post(
            "/correo/triage/json",
            json={"remitente": "x@y.gov.co", "asunto": "Oficio"},
            headers=headers or {},
        )

    def test_sin_clave_se_rechaza_con_401(self, cliente):
        respuesta = self._solicitud(cliente)
        assert respuesta.status_code == 401
        assert "X-API-Key" in respuesta.json()["detail"]

    def test_con_clave_equivocada_se_rechaza_con_403(self, cliente):
        assert self._solicitud(cliente, {"X-API-Key": "no-es-la-clave"}).status_code == 403

    def test_con_la_clave_correcta_se_autoriza(self, cliente):
        assert self._solicitud(cliente, CABECERA).status_code == 200

    def test_admite_varias_claves_para_poder_rotarlas(self, cliente):
        assert self._solicitud(cliente, {"X-API-Key": CLAVE_ALTERNA}).status_code == 200

    def test_admite_la_clave_como_portador_en_authorization(self, cliente):
        respuesta = self._solicitud(cliente, {"Authorization": f"Bearer {CLAVE}"})
        assert respuesta.status_code == 200

    def test_un_authorization_de_otro_tipo_no_sirve(self, cliente):
        respuesta = self._solicitud(cliente, {"Authorization": f"Basic {CLAVE}"})
        assert respuesta.status_code == 401

    def test_la_via_multiparte_tambien_exige_clave(self, cliente):
        respuesta = cliente.post("/correo/triage", data={"remitente": "x@y.gov.co"})
        assert respuesta.status_code == 401

    def test_sin_claves_configuradas_se_rechaza_todo(self, monkeypatch):
        """
        Fallar cerrado: un endpoint que consume el modelo y recibe
        correspondencia no puede quedar abierto por omisión de configuración.
        """
        monkeypatch.setattr(main, "OPENROUTER_API_KEY", "clave-del-modelo")
        monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset())
        with TestClient(main.app) as cliente:
            respuesta = cliente.post(
                "/correo/triage/json",
                json={"remitente": "x@y.gov.co"},
                headers=CABECERA,
            )
        assert respuesta.status_code == 503
        assert "TRIAGE_API_KEYS" in respuesta.json()["detail"]


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
                **CONTEXTO,
            },
            files=[("archivos", ("respuesta.pdf", pdf, "application/pdf"))],
            headers=CABECERA,
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
            headers=CABECERA,
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
            "/correo/triage", data={"remitente": "x@y.gov.co"}, files=archivos, headers=CABECERA
        )
        assert respuesta.status_code == 413

    def test_remitente_es_obligatorio(self, cliente):
        respuesta = cliente.post("/correo/triage", data={"asunto": "Oficio"}, headers=CABECERA)
        assert respuesta.status_code == 422


class TestTriageEnJson:
    def _enviar(self, cliente, **cambios):
        cuerpo = {
            "remitente": "notificaciones@previsora.gov.co",
            "asunto": "RE: Oficio CNDJ-2025-0412",
            "cuerpo": "<p>Adjunto damos respuesta.</p>",
            "fecha_recepcion": "2025-10-01",
            "contexto": CONTEXTO,
        }
        cuerpo.update(cambios)
        return cliente.post("/correo/triage/json", json=cuerpo, headers=CABECERA)

    def test_clasifica_el_correo_con_el_adjunto_en_texto(self, cliente):
        respuesta = self._enviar(
            cliente,
            adjuntos=[
                {
                    "nombre": "respuesta.pdf",
                    "texto": "LA PREVISORA S.A. informa que no es competente. Radicado CNDJ-2025-0412.",
                }
            ],
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["tipo_acto"] == "DEVOLUCION_POR_COMPETENCIA"
        assert "ENTIDAD_DISTINTA" in {a["codigo"] for a in ficha["alertas"]}
        assert ficha["documentos"][0]["nombre"] == "respuesta.pdf"

    def test_el_servidor_extrae_el_pdf_remitido_en_base64(self, cliente):
        """
        Forma que emplea un flujo de Power Automate, que no sabe leer PDF: el
        archivo viaja íntegro y la extracción queda del lado del servidor.
        """
        pdf = construir_pdf_texto(
            ["LA PREVISORA S.A. COMPANIA DE SEGUROS", "Respuesta al radicado CNDJ-2025-0999"]
        )
        respuesta = self._enviar(
            cliente,
            adjuntos=[
                {"nombre": "respuesta.pdf", "contenido_base64": base64.b64encode(pdf).decode()}
            ],
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["documentos"][0]["metodo"] == "TEXTO_NATIVO"
        assert ficha["documentos"][0]["paginas"] == 1
        assert ficha["cotejo"]["radicado_estado"] == "NO_COINCIDE"

    def test_admite_base64_plegado_en_lineas_como_el_de_mime(self, cliente):
        pdf = construir_pdf_texto(["LA PREVISORA S.A.", "Radicado CNDJ-2025-0412"])
        plegado = "\n".join(textwrap.wrap(base64.b64encode(pdf).decode(), 76))
        respuesta = self._enviar(
            cliente, adjuntos=[{"nombre": "respuesta.pdf", "contenido_base64": plegado}]
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["documentos"][0]["metodo"] == "TEXTO_NATIVO"

    def test_base64_invalido_se_advierte_sin_interrumpir_el_triage(self, cliente):
        respuesta = self._enviar(
            cliente, adjuntos=[{"nombre": "roto.pdf", "contenido_base64": "no-es-base64-%%%"}]
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["documentos"][0]["metodo"] == "NINGUNO"
        assert "DOCUMENTO_ILEGIBLE" in {a["codigo"] for a in ficha["alertas"]}

    def test_adjunto_sin_texto_ni_contenido_se_rechaza(self, cliente):
        assert self._enviar(cliente, adjuntos=[{"nombre": "vacio.pdf"}]).status_code == 422

    def test_rechaza_adjuntos_que_en_conjunto_exceden_el_limite(self, cliente, monkeypatch):
        monkeypatch.setattr(main, "MAX_BYTES_SOLICITUD", 1024)
        relleno = base64.b64encode(b"x" * 4096).decode()
        respuesta = self._enviar(
            cliente, adjuntos=[{"nombre": "grande.pdf", "contenido_base64": relleno}]
        )
        assert respuesta.status_code == 413

    def test_puede_desactivarse_el_reconocimiento_optico(self, cliente):
        """
        La acción HTTP de Power Automate agota la espera a los 120 segundos;
        desactivar el reconocimiento permite ajustarse a ese límite.
        """
        from tests.utilidades import construir_pdf_escaneado

        escaneado = construir_pdf_escaneado(["LA PREVISORA S.A."])
        respuesta = self._enviar(
            cliente,
            aplicar_ocr=False,
            adjuntos=[
                {"nombre": "escaneado.pdf", "contenido_base64": base64.b64encode(escaneado).decode()}
            ],
        )
        assert respuesta.status_code == 200
        documento = respuesta.json()["documentos"][0]
        assert documento["metodo"] == "NINGUNO"
        assert any("desactivado" in a for a in documento["advertencias"])


class TestAdjuntosQueNoSonPdf:
    def test_no_generan_alerta_de_ilegibilidad_y_se_enuncian(self, cliente):
        """
        Power Automate remite cuanto venía en el correo, logotipo de la firma
        incluido. Una alerta de documento ilegible por cada logotipo es la forma
        más rápida de que el lector deje de atender las alertas.
        """
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio",
                "contexto": CONTEXTO,
                "adjuntos": [
                    {
                        "nombre": "logo.png",
                        "contenido_base64": base64.b64encode(b"\x89PNG\r\n\x1a\n falso").decode(),
                    },
                    {
                        "nombre": "anexo.docx",
                        "contenido_base64": base64.b64encode(b"PK\x03\x04 contenido").decode(),
                    },
                ],
            },
            headers=CABECERA,
        )
        assert respuesta.status_code == 200
        ficha = respuesta.json()
        assert ficha["adjuntos_no_analizados"] == ["logo.png", "anexo.docx"]
        assert ficha["documentos"] == []
        assert "DOCUMENTO_ILEGIBLE" not in {a["codigo"] for a in ficha["alertas"]}

    def test_la_ficha_redactada_los_enuncia(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "x@y.gov.co",
                "adjuntos": [
                    {
                        "nombre": "logo.png",
                        "contenido_base64": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode(),
                    }
                ],
            },
            headers=CABECERA,
        )
        assert "logo.png" in respuesta.json()["redaccion"]["texto"]


class TestFichaRedactada:
    def test_la_respuesta_trae_el_correo_ya_compuesto(self, cliente):
        """
        Permite que un flujo sin código entregue estos tres campos a su acción
        de correo, sin componer el mensaje con expresiones ni recorrer alertas.
        """
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio CNDJ-2025-0412",
                "contexto": CONTEXTO,
            },
            headers=CABECERA,
        )
        redaccion = respuesta.json()["redaccion"]
        assert set(redaccion) == {"asunto", "texto", "html"}
        assert redaccion["asunto"].startswith("[ALTA]")
        assert "ENTIDAD_DISTINTA" in redaccion["texto"]
        assert redaccion["html"].startswith("<div")

    def test_puede_omitirse(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={"remitente": "x@y.gov.co", "redactar": False},
            headers=CABECERA,
        )
        assert respuesta.json()["redaccion"] is None

    def test_la_via_multiparte_tambien_la_entrega(self, cliente):
        respuesta = cliente.post(
            "/correo/triage",
            data={"remitente": "notificaciones@previsora.gov.co", "asunto": "RE: Oficio"},
            headers=CABECERA,
        )
        assert respuesta.json()["redaccion"]["asunto"].startswith("[")


class TestCuerpoEnBase64:
    def test_el_cuerpo_html_puede_remitirse_en_base64(self, cliente):
        """
        El cuerpo de un correo de Outlook es HTML con comillas y saltos de
        línea, que romperían la plantilla JSON de la acción HTTP de un flujo.
        El base64 elimina ese riesgo.
        """
        html = '<div style="color:red">Adjunto "la respuesta".\nSaludos.</div>'
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio",
                "cuerpo_base64": base64.b64encode(html.encode()).decode(),
                "contexto": CONTEXTO,
            },
            headers=CABECERA,
        )
        assert respuesta.status_code == 200
        assert respuesta.json()["tipo_acto"] == "DEVOLUCION_POR_COMPETENCIA"

    def test_si_se_remiten_ambos_prevalece_el_cuerpo_sin_codificar(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "x@y.gov.co",
                "cuerpo": "Adjunto remitimos la respuesta.",
                "cuerpo_base64": base64.b64encode(b"otro contenido").decode(),
            },
            headers=CABECERA,
        )
        assert respuesta.status_code == 200
        # El cuerpo sin codificar anuncia un adjunto que no llegó.
        assert "SIN_ADJUNTO_ANUNCIADO" in {
            a["codigo"] for a in respuesta.json()["alertas"]
        }

    def test_un_base64_mal_formado_se_rechaza_con_422(self, cliente):
        respuesta = cliente.post(
            "/correo/triage/json",
            json={"remitente": "x@y.gov.co", "cuerpo_base64": "no-es-base64-%%%"},
            headers=CABECERA,
        )
        assert respuesta.status_code == 422
        assert "cuerpo_base64" in respuesta.text

    def test_decodifica_el_acento_correctamente(self, cliente):
        cuerpo = "Devolución por competencia. Señor Magistrado."
        respuesta = cliente.post(
            "/correo/triage/json",
            json={
                "remitente": "x@y.gov.co",
                "cuerpo_base64": base64.b64encode(cuerpo.encode("utf-8")).decode(),
                "redactar": False,
            },
            headers=CABECERA,
        )
        assert respuesta.status_code == 200


class TestClaveConCaracteresNoAscii:
    def test_una_clave_configurada_con_acentos_no_produce_error_interno(self, monkeypatch):
        """
        Una cabecera HTTP no admite caracteres fuera de ASCII, de modo que la
        clave presentada nunca los tendrá; pero la configurada sí puede
        tenerlos, y `hmac.compare_digest` lanza TypeError si cualquiera de los
        dos argumentos no es ASCII. La comparación se hace en bytes para que el
        resultado sea un rechazo limpio y no un error 500.
        """
        monkeypatch.setattr(main, "OPENROUTER_API_KEY", "clave-del-modelo")
        monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset({"clavé-con-acento"}))
        with TestClient(main.app) as cliente:
            respuesta = cliente.post(
                "/correo/triage/json",
                json={"remitente": "x@y.gov.co"},
                headers={"X-API-Key": "clave-en-ascii"},
            )
        assert respuesta.status_code == 403
