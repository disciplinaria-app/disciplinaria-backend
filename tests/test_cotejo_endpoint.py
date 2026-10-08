"""
Pruebas del cotejo aislado.

Este endpoint existe para que una capa de ingesta que lee el documento dentro
de su propio entorno conserve la verificación determinista sin remitir la
correspondencia. Lo que se verifica aquí, además del resultado, es esa
garantía: que no invoque al modelo y que no reciba contenido documental.
"""

import pytest
from fastapi.testclient import TestClient

import main
from agents import agente_triage

CLAVE = "clave-de-prueba-0001"
CABECERA = {"X-API-Key": CLAVE}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset({CLAVE}))
    # El endpoint no debe invocar al modelo: si lo hiciera, esto lo delataría.
    async def jamas(**_kwargs):
        raise AssertionError("el cotejo no debe invocar al agente")

    monkeypatch.setattr(agente_triage, "ejecutar", jamas)
    with TestClient(main.app) as cliente:
        yield cliente


def _cotejar(cliente, **cuerpo):
    return cliente.post("/correo/cotejo", json=cuerpo, headers=CABECERA)


class TestDeteccionDeEntidadEquivocada:
    def test_distingue_previsora_de_fiduprevisora(self, cliente):
        respuesta = _cotejar(
            cliente,
            entidad_interpelada="Fiduprevisora S.A.",
            entidad_remitente="La Previsora S.A. Compañía de Seguros",
            radicado_enviado="CNDJ-2025-0412",
            radicados_hallados=["CNDJ-2025-0412"],
        )
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["cotejo"]["entidad_estado"] == "DIFIERE"
        assert datos["cotejo"]["radicado_estado"] == "COINCIDE"
        assert "ENTIDAD_DISTINTA" in {a["codigo"] for a in datos["alertas"]}
        assert "NO es aquella" in datos["veredicto"]

    def test_denominacion_abreviada_frente_a_razon_social_completa(self, cliente):
        datos = _cotejar(
            cliente,
            entidad_interpelada="La Previsora S.A.",
            entidad_remitente="LA PREVISORA S.A. COMPAÑÍA DE SEGUROS",
        ).json()
        assert datos["cotejo"]["entidad_estado"] == "COINCIDE"
        assert datos["alertas"] == []
        assert "corresponde a la interpelada" in datos["veredicto"]

    def test_sin_una_de_las_dos_denominaciones_no_se_pronuncia(self, cliente):
        datos = _cotejar(cliente, entidad_remitente="Colpensiones").json()
        assert datos["cotejo"]["entidad_estado"] == "INDETERMINADO"
        assert "No fue posible cotejar la entidad" in datos["veredicto"]


class TestCotejoDeRadicados:
    def test_radicado_que_no_figura_en_la_respuesta(self, cliente):
        datos = _cotejar(
            cliente,
            entidad_interpelada="Colpensiones",
            entidad_remitente="Colpensiones",
            radicado_enviado="CNDJ-2025-0412",
            radicados_hallados=["CNDJ-2025-0999"],
        ).json()
        assert datos["cotejo"]["radicado_estado"] == "NO_COINCIDE"
        assert "RADICADO_NO_COINCIDE" in {a["codigo"] for a in datos["alertas"]}
        assert "otra actuación" in datos["veredicto"]

    def test_equivalencia_pese_al_formato(self, cliente):
        datos = _cotejar(
            cliente, radicado_enviado="CNDJ-2025-0412", radicados_hallados=["CNDJ 2025 0412"]
        ).json()
        assert datos["cotejo"]["radicado_estado"] == "COINCIDE"

    def test_sin_radicado_remitido_queda_indeterminado(self, cliente):
        datos = _cotejar(cliente, radicados_hallados=["2025-0001"]).json()
        assert datos["cotejo"]["radicado_estado"] == "INDETERMINADO"


class TestGarantias:
    def test_no_invoca_al_modelo(self, cliente):
        """El agente está sustituido por una función que falla si se la llama."""
        respuesta = _cotejar(
            cliente,
            entidad_interpelada="Fiduprevisora S.A.",
            entidad_remitente="La Previsora S.A.",
        )
        assert respuesta.status_code == 200

    def test_no_admite_contenido_documental(self, cliente):
        """
        El esquema no tiene campo para el texto del documento. Lo que se remita
        de más se descarta, de modo que la garantía no dependa de la disciplina
        de quien construya el flujo.
        """
        respuesta = _cotejar(
            cliente,
            entidad_interpelada="Fiduprevisora S.A.",
            entidad_remitente="La Previsora S.A.",
            texto_del_documento="Contenido reservado que no debería salir del tenant",
        )
        assert respuesta.status_code == 200
        assert "Contenido reservado" not in respuesta.text

    def test_no_exige_la_clave_del_modelo(self, monkeypatch):
        """Al no invocar al modelo, opera aunque OPENROUTER_API_KEY esté ausente."""
        monkeypatch.setattr(main, "OPENROUTER_API_KEY", "")
        monkeypatch.setattr(main, "TRIAGE_API_KEYS", frozenset({CLAVE}))
        with TestClient(main.app) as cliente:
            respuesta = cliente.post(
                "/correo/cotejo",
                json={"entidad_interpelada": "A", "entidad_remitente": "B"},
                headers=CABECERA,
            )
        assert respuesta.status_code == 200

    def test_exige_clave_de_acceso(self, cliente):
        assert cliente.post("/correo/cotejo", json={}).status_code == 401

    def test_una_solicitud_vacia_no_falla(self, cliente):
        datos = _cotejar(cliente).json()
        assert datos["cotejo"]["entidad_estado"] == "INDETERMINADO"
        assert datos["alertas"] == []
        assert "No se levantó alerta alguna" in datos["veredicto"]
