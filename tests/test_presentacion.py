"""Pruebas de la redacción de la ficha, común a las tres rutas de ingesta."""

from models.schemas import Alerta, DocumentoProcesado, Termino, TriageResponse
from services import presentacion
from services.presentacion import DatosCorreo

DATOS = DatosCorreo(
    remitente="Notificaciones Previsora <notificaciones@previsora.gov.co>",
    asunto="RE: Oficio CNDJ-2025-0412",
    fecha="2025-10-01",
    reenviado=True,
)


def _ficha(**cambios) -> TriageResponse:
    base = dict(
        entidad_remitente="La Previsora S.A. Compañía de Seguros",
        tipo_acto="DEVOLUCION_POR_COMPETENCIA",
        materia="La entidad advierte que la comunicación fue dirigida por error.",
        resumen="La Previsora informa que el oficio correspondía a Fiduprevisora S.A.",
        radicados=["CNDJ-2025-0412"],
        requiere_actuacion=True,
        actuacion_sugerida="Remitir nuevamente el oficio a Fiduprevisora S.A.",
        alertas=[
            Alerta(
                codigo="ENTIDAD_DISTINTA",
                descripcion="Se dirigió a Fiduprevisora pero responde La Previsora.",
                severidad="ALTA",
                origen="AMBOS",
            )
        ],
        urgencia="ALTA",
        documentos=[
            DocumentoProcesado(
                nombre="respuesta.pdf", paginas=2, metodo="OCR", caracteres=1800
            )
        ],
    )
    base.update(cambios)
    return TriageResponse(**base)


class TestAsunto:
    def test_encabeza_la_urgencia_la_entidad_y_la_alerta_grave(self):
        asunto = presentacion.componer_asunto(_ficha(), DATOS)
        assert asunto.startswith("[ALTA]")
        assert "Previsora" in asunto
        assert "Entidad Distinta" in asunto

    def test_sin_alerta_grave_no_se_anuncia_ninguna(self):
        asunto = presentacion.componer_asunto(_ficha(alertas=[], urgencia="BAJA"), DATOS)
        assert asunto.startswith("[BAJA]")
        assert "Distinta" not in asunto

    def test_el_asunto_se_mantiene_dentro_del_limite(self):
        largo = _ficha(entidad_remitente="Entidad " * 40)
        assert len(presentacion.componer_asunto(largo, DATOS)) <= presentacion.LIMITE_ASUNTO

    def test_sin_entidad_determinada_recurre_al_remitente_del_correo(self):
        asunto = presentacion.componer_asunto(_ficha(entidad_remitente=None), DATOS)
        assert "Previsora" in asunto


class TestCuerpoEnTexto:
    def test_las_alertas_encabezan_el_cuerpo(self):
        texto = presentacion.componer_texto(_ficha(), DATOS)
        assert texto.index("ALERTAS") < texto.index("Entidad que suscribe")
        assert "ENTIDAD_DISTINTA" in texto

    def test_informa_el_termino_con_los_dias_calculados(self):
        ficha = _ficha(
            termino=Termino(fecha_limite="2025-10-20", dias_restantes=7, fundamento="Diez días")
        )
        assert "Vence el 2025-10-20 (restan 7 días)" in presentacion.componer_texto(ficha, DATOS)

    def test_informa_el_termino_vencido(self):
        ficha = _ficha(termino=Termino(fecha_limite="2025-09-01", dias_restantes=-12))
        assert "Venció el 2025-09-01 (hace 12 días)" in presentacion.componer_texto(ficha, DATOS)

    def test_termino_sin_fecha_recurre_al_fundamento(self):
        ficha = _ficha(termino=Termino(fundamento="Diez días hábiles desde la notificación"))
        assert "Diez días hábiles" in presentacion.componer_texto(ficha, DATOS)

    def test_declara_la_procedencia_cuando_hubo_reenvio(self):
        assert "Reenvío" in presentacion.componer_texto(_ficha(), DATOS)
        sin_reenvio = DatosCorreo(remitente="x@y.gov.co", asunto="Oficio")
        assert "Reenvío" not in presentacion.componer_texto(_ficha(), sin_reenvio)

    def test_enuncia_los_anexos_que_no_se_analizan(self):
        ficha = _ficha(adjuntos_no_analizados=["anexo.docx", "logo.png"])
        texto = presentacion.componer_texto(ficha, DATOS)
        assert "anexo.docx" in texto
        assert "solo se analizan PDF" in texto

    def test_las_advertencias_del_correo_y_de_la_ficha_siempre_aparecen(self):
        datos = DatosCorreo(
            remitente="x@y.gov.co", advertencias=["Aviso de la lectura del correo."]
        )
        ficha = _ficha(advertencias=["Aviso del procesamiento."])
        texto = presentacion.componer_texto(ficha, datos)
        assert "Aviso de la lectura del correo." in texto
        assert "Aviso del procesamiento." in texto

    def test_advierte_que_no_sustituye_la_lectura_del_documento(self):
        assert "no sustituye la lectura" in presentacion.componer_texto(_ficha(), DATOS)

    def test_informa_que_el_documento_se_leyo_por_reconocimiento_optico(self):
        texto = presentacion.componer_texto(_ficha(), DATOS)
        assert "respuesta.pdf" in texto
        assert "ocr" in texto.lower()


class TestCuerpoEnHtml:
    def test_escapa_el_contenido_recibido(self):
        """El cuerpo proviene de un tercero y no puede inyectar marcado."""
        ficha = _ficha(materia="<script>alert(1)</script> y comillas \" '")
        cuerpo = presentacion.componer_html(ficha, DATOS)
        assert "<script>" not in cuerpo
        assert "&lt;script&gt;" in cuerpo

    def test_escapa_tambien_el_remitente_del_correo(self):
        datos = DatosCorreo(remitente="<img src=x onerror=alert(1)>", asunto="Oficio")
        cuerpo = presentacion.componer_html(_ficha(), datos)
        assert "<img" not in cuerpo
        assert "&lt;img" in cuerpo

    def test_incluye_las_alertas_y_los_campos(self):
        cuerpo = presentacion.componer_html(_ficha(), DATOS)
        assert "ENTIDAD DISTINTA" in cuerpo
        assert "Fiduprevisora" in cuerpo

    def test_sin_alertas_el_cuerpo_sigue_siendo_valido(self):
        cuerpo = presentacion.componer_html(_ficha(alertas=[]), DATOS)
        assert cuerpo.startswith("<div")
        assert cuerpo.endswith("</div>")


class TestComposicionCompleta:
    def test_entrega_asunto_texto_y_html(self):
        redactada = presentacion.componer(_ficha(), DATOS)
        assert redactada.asunto.startswith("[ALTA]")
        assert "ENTIDAD_DISTINTA" in redactada.texto
        assert redactada.html.startswith("<div")

    def test_el_aviso_de_fallo_identifica_el_correo_y_el_motivo(self):
        redactada = presentacion.redactar_aviso_de_fallo(
            "notificaciones@previsora.gov.co — RE: Oficio", "TimeoutError: agotado", 3
        )
        assert "No se pudo clasificar" in redactada.asunto
        assert "TimeoutError: agotado" in redactada.texto
        assert "Intentos: 3" in redactada.texto
        assert "correspondencia pendiente" in redactada.texto
        assert "<pre" in redactada.html
