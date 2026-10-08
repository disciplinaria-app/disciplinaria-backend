"""Pruebas del cotejo determinista."""

import pytest

from services import cotejo


class TestNormalizacionEntidad:
    def test_suprime_diacriticos_puntuacion_y_descriptores_genericos(self):
        """El descriptor «Compañía de Seguros» no identifica a la entidad y se suprime."""
        assert cotejo.normalizar_entidad("La Previsora S.A. Compañía de Seguros") == "previsora"
        assert cotejo.normalizar_entidad("FIDUPREVISORA S.A.S.") == "fiduprevisora"

    def test_entidad_vacia_o_ausente(self):
        assert cotejo.normalizar_entidad(None) == ""
        assert cotejo.normalizar_entidad("   ") == ""


class TestComparacionEntidades:
    def test_previsora_y_fiduprevisora_son_entidades_distintas(self):
        """
        El caso que motiva el cotejo: «previsora» es subcadena de
        «fiduprevisora», de modo que una comparación por subcadenas las tomaría
        por la misma entidad y silenciaría precisamente la alerta esperada.
        """
        assert (
            cotejo.comparar_entidades("Fiduprevisora S.A.", "La Previsora S.A. Compañía de Seguros")
            == "DIFIERE"
        )

    def test_denominacion_abreviada_frente_a_razon_social_completa(self):
        assert cotejo.comparar_entidades("La Previsora S.A.", "PREVISORA") == "COINCIDE"

    def test_coincidencia_pese_a_mayusculas_y_tildes(self):
        assert (
            cotejo.comparar_entidades(
                "Comisión Nacional de Disciplina Judicial",
                "COMISION NACIONAL DE DISCIPLINA JUDICIAL",
            )
            == "COINCIDE"
        )

    def test_sin_dato_suficiente_no_se_pronuncia(self):
        assert cotejo.comparar_entidades(None, "La Previsora S.A.") == "INDETERMINADO"
        assert cotejo.comparar_entidades("Fiduprevisora", None) == "INDETERMINADO"

    def test_entidades_sin_relacion(self):
        assert cotejo.comparar_entidades("Fiduprevisora S.A.", "Colpensiones") == "DIFIERE"


class TestExtraccionRadicados:
    def test_conserva_la_sigla_institucional(self):
        hallados = cotejo.extraer_radicados("En respuesta al oficio CNDJ-2025-0412 de la referencia")
        assert "CNDJ-2025-0412" in hallados

    def test_radicado_numerico_extenso(self):
        hallados = cotejo.extraer_radicados("Expediente 110013103001202300456")
        assert "110013103001202300456" in hallados

    def test_no_duplica_la_forma_corta_del_mismo_radicado(self):
        hallados = cotejo.extraer_radicados("Oficio CNDJ-2025-0412")
        assert hallados == ["CNDJ-2025-0412"]

    def test_descarta_numeros_demasiado_breves(self):
        assert cotejo.extraer_radicados("El artículo 35 de la Ley 1123") == []

    def test_texto_sin_radicados(self):
        assert cotejo.extraer_radicados("Cordial saludo, acusamos recibo de su comunicación.") == []


class TestEquivalenciaRadicados:
    def test_identidad_pese_al_formato(self):
        assert cotejo.radicados_equivalentes("CNDJ-2025-0412", "CNDJ 2025 0412")

    def test_consecutivo_final_de_una_cita_mas_extensa(self):
        assert cotejo.radicados_equivalentes("CNDJ-2025-0412", "20250412")

    def test_radicados_distintos(self):
        assert not cotejo.radicados_equivalentes("2025-0412", "2025-0999")

    def test_coincidencia_demasiado_breve_no_cuenta(self):
        assert not cotejo.radicados_equivalentes("2025-0412", "412")


class TestCotejoIntegrado:
    def test_entidad_distinta_y_radicado_coincidente(self):
        resultado = cotejo.cotejar(
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="La Previsora S.A. Compañía de Seguros",
            radicado_enviado="CNDJ-2025-0412",
            radicados_hallados=["CNDJ-2025-0412"],
        )
        assert resultado.entidad_estado == "DIFIERE"
        assert resultado.radicado_estado == "COINCIDE"

    def test_sin_radicado_remitido_el_estado_queda_indeterminado(self):
        resultado = cotejo.cotejar("Colpensiones", "Colpensiones", None, ["2025-0001"])
        assert resultado.radicado_estado == "INDETERMINADO"
        assert resultado.entidad_estado == "COINCIDE"

    def test_radicado_remitido_que_no_figura_en_la_respuesta(self):
        resultado = cotejo.cotejar(None, None, "CNDJ-2025-0412", ["CNDJ-2025-0999"])
        assert resultado.radicado_estado == "NO_COINCIDE"


class TestAlertasDeterministas:
    def _resultado(self, **cambios):
        base = dict(
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="La Previsora S.A.",
            radicado_enviado="CNDJ-2025-0412",
            radicados_hallados=["CNDJ-2025-0412"],
        )
        base.update(cambios)
        return cotejo.cotejar(**base)

    def test_alerta_de_entidad_distinta_con_severidad_alta(self):
        alertas = cotejo.alertas_deterministas(
            resultado=self._resultado(),
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="La Previsora S.A.",
            cuerpo="Adjunto damos respuesta.",
            numero_adjuntos=1,
            documentos_ilegibles=[],
        )
        codigos = {a.codigo: a for a in alertas}
        assert "ENTIDAD_DISTINTA" in codigos
        assert codigos["ENTIDAD_DISTINTA"].severidad == "ALTA"
        assert codigos["ENTIDAD_DISTINTA"].origen == "COTEJO"

    def test_adjunto_anunciado_y_no_recibido(self):
        alertas = cotejo.alertas_deterministas(
            resultado=self._resultado(entidad_recibida="Fiduprevisora S.A."),
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="Fiduprevisora S.A.",
            cuerpo="Cordial saludo. Adjunto remitimos la respuesta solicitada.",
            numero_adjuntos=0,
            documentos_ilegibles=[],
        )
        assert "SIN_ADJUNTO_ANUNCIADO" in {a.codigo for a in alertas}

    def test_correo_sin_anuncio_de_adjunto_no_genera_la_alerta(self):
        alertas = cotejo.alertas_deterministas(
            resultado=self._resultado(entidad_recibida="Fiduprevisora S.A."),
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="Fiduprevisora S.A.",
            cuerpo="Acusamos recibo de su comunicación.",
            numero_adjuntos=0,
            documentos_ilegibles=[],
        )
        assert alertas == []

    def test_documento_ilegible(self):
        alertas = cotejo.alertas_deterministas(
            resultado=self._resultado(entidad_recibida="Fiduprevisora S.A."),
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="Fiduprevisora S.A.",
            cuerpo="",
            numero_adjuntos=1,
            documentos_ilegibles=["oficio.pdf"],
        )
        ilegible = next(a for a in alertas if a.codigo == "DOCUMENTO_ILEGIBLE")
        assert ilegible.severidad == "ALTA"
        assert "oficio.pdf" in ilegible.descripcion

    def test_todos_los_codigos_emitidos_pertenecen_al_catalogo(self):
        alertas = cotejo.alertas_deterministas(
            resultado=self._resultado(radicados_hallados=["CNDJ-2025-0999"]),
            entidad_esperada="Fiduprevisora S.A.",
            entidad_recibida="La Previsora S.A.",
            cuerpo="Adjunto la respuesta.",
            numero_adjuntos=0,
            documentos_ilegibles=["x.pdf"],
        )
        assert {a.codigo for a in alertas} <= set(cotejo.CODIGOS_ALERTA)
