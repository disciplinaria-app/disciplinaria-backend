"""Pruebas de la lectura de mensajes MIME."""

from email.message import EmailMessage

from ingesta import mensaje as lectura
from tests.utilidades import construir_pdf_texto

PROPIAS = frozenset({"luis@cendoj.ramajudicial.gov.co"})
PDF = construir_pdf_texto(["LA PREVISORA S.A.", "Radicado CNDJ-2025-0412"])


def _correo(
    remitente="notificaciones@previsora.gov.co",
    asunto="RE: Oficio CNDJ-2025-0412",
    cuerpo="Cordial saludo, adjunto damos respuesta.",
    html=None,
    fecha="Wed, 01 Oct 2025 10:12:00 -0500",
) -> EmailMessage:
    correo = EmailMessage()
    correo["From"] = remitente
    correo["To"] = "luis@cendoj.ramajudicial.gov.co"
    correo["Subject"] = asunto
    correo["Message-ID"] = "<abc123@previsora.gov.co>"
    if fecha:
        correo["Date"] = fecha
    if html == "solo":
        correo.set_content(f"<html><body><p>{cuerpo}</p></body></html>", subtype="html")
    elif html == "ambos":
        correo.set_content("Version en texto plano.")
        correo.add_alternative(f"<html><body><p>{cuerpo}</p></body></html>", subtype="html")
    else:
        correo.set_content(cuerpo)
    return correo


class TestCorreoDirecto:
    def test_toma_los_datos_del_sobre_y_recoge_el_pdf(self):
        correo = _correo()
        correo.add_attachment(
            PDF, maintype="application", subtype="pdf", filename="respuesta.pdf"
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.remitente == "notificaciones@previsora.gov.co"
        assert entrante.asunto == "RE: Oficio CNDJ-2025-0412"
        assert entrante.fecha == "2025-10-01"
        assert entrante.identificador == "<abc123@previsora.gov.co>"
        assert "adjunto damos respuesta" in entrante.cuerpo
        assert [n for n, _ in entrante.adjuntos_pdf] == ["respuesta.pdf"]
        assert entrante.adjuntos_pdf[0][1] == PDF
        assert entrante.reenviado is False

    def test_cuerpo_solo_en_html_se_convierte_a_texto(self):
        entrante = lectura.parsear(_correo(html="solo").as_bytes(), PROPIAS)
        assert "adjunto damos respuesta" in entrante.cuerpo
        assert "<" not in entrante.cuerpo

    def test_con_ambas_partes_se_prefiere_el_texto_plano(self):
        entrante = lectura.parsear(_correo(html="ambos").as_bytes(), PROPIAS)
        assert entrante.cuerpo.strip() == "Version en texto plano."

    def test_fecha_ilegible_no_interrumpe(self):
        entrante = lectura.parsear(_correo(fecha="el martes pasado").as_bytes(), PROPIAS)
        assert entrante.fecha is None

    def test_sin_cabecera_de_fecha(self):
        entrante = lectura.parsear(_correo(fecha=None).as_bytes(), PROPIAS)
        assert entrante.fecha is None

    def test_decodifica_asunto_y_nombre_de_archivo_codificados(self):
        correo = _correo(asunto="RE: Devolución por competencia — Oficio Nº 412")
        correo.add_attachment(
            PDF, maintype="application", subtype="pdf", filename="devolución oficio.pdf"
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert "Devolución por competencia" in entrante.asunto
        assert entrante.adjuntos_pdf[0][0] == "devolución oficio.pdf"


class TestSeleccionDeAdjuntos:
    def test_el_logotipo_incorporado_de_la_firma_se_descarta(self):
        """
        Casi todo correo institucional lleva el logotipo en la firma. Tratarlo
        como adjunto produciría una alerta de documento ilegible en cada
        mensaje, que es la forma más rápida de que dejen de leerse las alertas.
        """
        correo = _correo()
        correo.add_related(
            b"\x89PNG\r\n\x1a\n falso",
            maintype="image",
            subtype="png",
            cid="<logo@previsora>",
            filename="logo.png",
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.adjuntos_pdf == []
        assert entrante.otros_adjuntos == []

    def test_adjunto_que_no_es_pdf_se_enuncia_sin_someterlo_a_extraccion(self):
        correo = _correo()
        correo.add_attachment(
            b"PK\x03\x04 contenido",
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="anexo.docx",
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.adjuntos_pdf == []
        assert entrante.otros_adjuntos == ["anexo.docx"]

    def test_pdf_declarado_como_flujo_binario_se_reconoce(self):
        """Las entidades remiten con frecuencia el PDF como octet-stream."""
        correo = _correo()
        correo.add_attachment(
            PDF, maintype="application", subtype="octet-stream", filename="respuesta.pdf"
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert [n for n, _ in entrante.adjuntos_pdf] == ["respuesta.pdf"]

    def test_pdf_sin_extension_se_reconoce_por_su_firma_binaria(self):
        correo = _correo()
        correo.add_attachment(
            PDF, maintype="application", subtype="octet-stream", filename="documento"
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert [n for n, _ in entrante.adjuntos_pdf] == ["documento"]


CUERPO_REENVIADO = """-----Mensaje original-----
De: Notificaciones Previsora <notificaciones@previsora.gov.co>
Enviado: miercoles, 1 de octubre de 2025 10:12 a. m.
Para: Luis Miranda <luis@cendoj.ramajudicial.gov.co>
Asunto: RE: Oficio CNDJ-2025-0412

Cordial saludo. Esta entidad no es competente; adjunto la devolucion.

De: Luis Miranda
Para: Fiduprevisora S.A.
Asunto: Oficio CNDJ-2025-0412
"""


class TestReenvioEnLinea:
    def test_recupera_el_remitente_real_sepultado_en_el_reenvio(self):
        """
        Al reenviar, el remitente del sobre es el propio buzón. Si no se
        desenvuelve, el cotejo compararía la entidad interpelada contra el
        propio despacho y nunca advertiría la discrepancia.
        """
        correo = _correo(
            remitente="luis@cendoj.ramajudicial.gov.co",
            asunto="RV: Oficio CNDJ-2025-0412",
            cuerpo=CUERPO_REENVIADO,
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.reenviado is True
        assert "previsora.gov.co" in entrante.remitente
        assert entrante.asunto == "RE: Oficio CNDJ-2025-0412"
        assert entrante.cuerpo.startswith("Cordial saludo. Esta entidad no es competente")
        # La cadena original debe sobrevivir: de ella se deduce la entidad interpelada.
        assert "Fiduprevisora" in entrante.cuerpo

    def test_el_prefijo_de_reenvio_basta_para_intentar_el_desenvolvimiento(self):
        correo = _correo(
            remitente="otro@dominio.gov.co",
            asunto="FW: Oficio CNDJ-2025-0412",
            cuerpo=CUERPO_REENVIADO,
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.reenviado is True
        assert "previsora.gov.co" in entrante.remitente

    def test_buzon_propio_sin_bloque_reconocible_se_advierte(self):
        correo = _correo(
            remitente="luis@cendoj.ramajudicial.gov.co",
            cuerpo="Te reenvío esto, mira el adjunto.",
        )
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.reenviado is False
        assert any("buzón propio" in a for a in entrante.advertencias)

    def test_correo_ajeno_no_se_desenvuelve_aunque_cite_encabezados(self):
        """Una respuesta ordinaria cita la cadena anterior y no debe tocarse."""
        correo = _correo(cuerpo="Damos respuesta.\n\n" + CUERPO_REENVIADO)
        entrante = lectura.parsear(correo.as_bytes(), PROPIAS)
        assert entrante.reenviado is False
        assert entrante.remitente == "notificaciones@previsora.gov.co"


class TestReenvioComoAdjunto:
    def test_usa_el_mensaje_original_y_sus_adjuntos(self):
        """Outlook reenvía con frecuencia el original como message/rfc822."""
        interno = _correo()
        interno.add_attachment(
            PDF, maintype="application", subtype="pdf", filename="respuesta.pdf"
        )
        externo = EmailMessage()
        externo["From"] = "luis@cendoj.ramajudicial.gov.co"
        externo["To"] = "triage@midominio.com"
        externo["Subject"] = "RV: Oficio CNDJ-2025-0412"
        externo["Date"] = "Wed, 01 Oct 2025 11:00:00 -0500"
        externo.set_content("Reenvio automatico.")
        externo.add_attachment(interno)

        entrante = lectura.parsear(externo.as_bytes(), PROPIAS)
        assert entrante.reenviado is True
        assert entrante.remitente == "notificaciones@previsora.gov.co"
        assert entrante.asunto == "RE: Oficio CNDJ-2025-0412"
        assert entrante.fecha == "2025-10-01"
        assert "adjunto damos respuesta" in entrante.cuerpo
        assert [n for n, _ in entrante.adjuntos_pdf] == ["respuesta.pdf"]
