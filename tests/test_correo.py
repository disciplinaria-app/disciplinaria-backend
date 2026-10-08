"""Pruebas de la normalización del cuerpo del correo."""

from services import correo


class TestLimpiezaDeCuerpo:
    def test_aisla_el_mensaje_nuevo_de_la_cadena_de_outlook(self):
        cuerpo = (
            "Cordial saludo, adjunto damos respuesta a su comunicación.\n"
            "\n"
            "De: Despacho CNDJ <despacho@cendoj.ramajudicial.gov.co>\n"
            "Enviado: lunes, 22 de septiembre de 2025 9:14 a. m.\n"
            "Para: Fiduprevisora S.A.\n"
            "Asunto: Oficio CNDJ-2025-0412\n"
            "\n"
            "Señores Fiduprevisora, con el fin de resolver la actuación...\n"
        )
        actual, anterior = correo.limpiar_cuerpo(cuerpo)
        assert actual == "Cordial saludo, adjunto damos respuesta a su comunicación."
        assert "Oficio CNDJ-2025-0412" in anterior
        assert "adjunto damos respuesta" not in anterior

    def test_separador_de_mensaje_original(self):
        actual, anterior = correo.limpiar_cuerpo(
            "Remitimos respuesta.\n-----Mensaje original-----\nTexto previo del despacho."
        )
        assert actual == "Remitimos respuesta."
        assert "Texto previo del despacho." in anterior

    def test_descarta_lineas_citadas_con_signo_de_mayor(self):
        actual, _ = correo.limpiar_cuerpo("Nuestra respuesta.\n> Su consulta anterior.")
        assert actual == "Nuestra respuesta."

    def test_cuerpo_sin_cadena_anterior(self):
        actual, anterior = correo.limpiar_cuerpo("Acusamos recibo.")
        assert actual == "Acusamos recibo."
        assert anterior == ""

    def test_cuerpo_vacio(self):
        assert correo.limpiar_cuerpo("") == ("", "")
        assert correo.limpiar_cuerpo(None) == ("", "")


class TestHtml:
    def test_reconoce_y_convierte_cuerpo_html(self):
        cuerpo = (
            "<html><head><style>p{color:red}</style></head><body>"
            "<p>Se&ntilde;or Magistrado:</p><p>Adjunto la respuesta.</p></body></html>"
        )
        assert correo.parece_html(cuerpo)
        actual, _ = correo.limpiar_cuerpo(cuerpo)
        assert "Señor Magistrado:" in actual
        assert "Adjunto la respuesta." in actual
        assert "color:red" not in actual
        assert "<" not in actual

    def test_texto_plano_no_se_trata_como_html(self):
        assert not correo.parece_html("Respuesta al oficio 2025-0412 (a < b)")


class TestInferenciaDeEntidadInterpelada:
    def test_deduce_la_entidad_del_encabezado_para(self):
        cadena = "De: Despacho\nPara: Fiduprevisora S.A.\nAsunto: Oficio"
        assert correo.inferir_entidad_interpelada(cadena) == "Fiduprevisora S.A."

    def test_descarta_encabezados_que_solo_traen_direcciones(self):
        cadena = "Para: contacto@fiduprevisora.com.co\nAsunto: Oficio"
        assert correo.inferir_entidad_interpelada(cadena) is None

    def test_sin_cadena_anterior_no_infiere(self):
        assert correo.inferir_entidad_interpelada("") is None
        assert correo.inferir_entidad_interpelada("Texto suelto sin encabezados") is None
