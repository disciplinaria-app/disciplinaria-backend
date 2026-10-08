"""Pruebas de la composición de la ficha remitida por correo."""

from ingesta import notificacion
from ingesta.mensaje import CorreoEntrante
from models.schemas import Alerta, DocumentoProcesado, Termino, TriageResponse

ENTRANTE = CorreoEntrante(
    identificador="<abc@previsora.gov.co>",
    remitente="Notificaciones Previsora <notificaciones@previsora.gov.co>",
    asunto="RE: Oficio CNDJ-2025-0412",
    fecha="2025-10-01",
    cuerpo="Cordial saludo, adjunto damos respuesta.",
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
        asunto = notificacion.componer_asunto(_ficha(), ENTRANTE)
        assert asunto.startswith("[ALTA]")
        assert "Previsora" in asunto
        assert "Entidad Distinta" in asunto

    def test_sin_alerta_grave_no_se_anuncia_ninguna(self):
        asunto = notificacion.componer_asunto(_ficha(alertas=[], urgencia="BAJA"), ENTRANTE)
        assert asunto.startswith("[BAJA]")
        assert "Distinta" not in asunto

    def test_el_asunto_se_mantiene_dentro_del_limite(self):
        largo = _ficha(entidad_remitente="Entidad " * 40)
        assert len(notificacion.componer_asunto(largo, ENTRANTE)) <= 160

    def test_sin_entidad_determinada_recurre_al_remitente_del_correo(self):
        asunto = notificacion.componer_asunto(_ficha(entidad_remitente=None), ENTRANTE)
        assert "previsora.gov.co" in asunto or "Previsora" in asunto


class TestCuerpoEnTexto:
    def test_las_alertas_encabezan_el_cuerpo(self):
        texto = notificacion.componer_texto(_ficha(), ENTRANTE)
        assert texto.index("ALERTAS") < texto.index("Entidad que suscribe")
        assert "ENTIDAD_DISTINTA" in texto

    def test_informa_el_termino_con_los_dias_calculados(self):
        ficha = _ficha(
            termino=Termino(fecha_limite="2025-10-20", dias_restantes=7, fundamento="Diez días")
        )
        texto = notificacion.componer_texto(ficha, ENTRANTE)
        assert "Vence el 2025-10-20 (restan 7 días)" in texto

    def test_informa_el_termino_vencido(self):
        ficha = _ficha(termino=Termino(fecha_limite="2025-09-01", dias_restantes=-12))
        assert "Venció el 2025-09-01 (hace 12 días)" in notificacion.componer_texto(
            ficha, ENTRANTE
        )

    def test_declara_la_procedencia_cuando_hubo_reenvio(self):
        texto = notificacion.componer_texto(_ficha(), ENTRANTE)
        assert "Reenvío" in texto

    def test_enuncia_los_anexos_que_no_se_analizan(self):
        entrante = CorreoEntrante(**{**ENTRANTE.__dict__, "otros_adjuntos": ["anexo.docx"]})
        texto = notificacion.componer_texto(_ficha(), entrante)
        assert "anexo.docx" in texto
        assert "solo se analizan PDF" in texto

    def test_las_advertencias_del_correo_y_de_la_ficha_siempre_aparecen(self):
        entrante = CorreoEntrante(
            **{**ENTRANTE.__dict__, "advertencias": ["Aviso de la lectura del correo."]}
        )
        ficha = _ficha(advertencias=["Aviso del procesamiento."])
        texto = notificacion.componer_texto(ficha, entrante)
        assert "Aviso de la lectura del correo." in texto
        assert "Aviso del procesamiento." in texto

    def test_advierte_que_no_sustituye_la_lectura_del_documento(self):
        assert "no sustituye la lectura" in notificacion.componer_texto(_ficha(), ENTRANTE)

    def test_informa_que_el_documento_se_leyo_por_reconocimiento_optico(self):
        texto = notificacion.componer_texto(_ficha(), ENTRANTE)
        assert "respuesta.pdf" in texto
        assert "ocr" in texto.lower()


class TestCuerpoEnHtml:
    def test_escapa_el_contenido_recibido(self):
        """El cuerpo proviene de un tercero y no puede inyectar marcado."""
        ficha = _ficha(materia="<script>alert(1)</script> y comillas \" '")
        cuerpo = notificacion.componer_html(ficha, ENTRANTE)
        assert "<script>" not in cuerpo
        assert "&lt;script&gt;" in cuerpo

    def test_incluye_las_alertas_y_los_campos(self):
        cuerpo = notificacion.componer_html(_ficha(), ENTRANTE)
        assert "ENTIDAD DISTINTA" in cuerpo
        assert "Fiduprevisora" in cuerpo

    def test_sin_alertas_el_cuerpo_sigue_siendo_valido(self):
        cuerpo = notificacion.componer_html(_ficha(alertas=[]), ENTRANTE)
        assert cuerpo.startswith("<div")
        assert cuerpo.endswith("</div>")


class TestEnvio:
    def _configuracion(self, **cambios):
        base = dict(
            servidor="smtp.ejemplo.com",
            usuario="buzon@ejemplo.com",
            clave="clave",
            remitente="buzon@ejemplo.com",
            destinatario="luis@cendoj.ramajudicial.gov.co",
        )
        base.update(cambios)
        return notificacion.ConfiguracionSMTP(**base)

    def test_configuracion_incompleta_se_rechaza_con_un_mensaje_claro(self):
        notificador = notificacion.NotificadorSMTP(self._configuracion(servidor=""))
        try:
            notificador.enviar("asunto", "texto")
        except ValueError as exc:
            assert "SMTP_SERVIDOR" in str(exc)
        else:
            raise AssertionError("debía rechazarse la configuración incompleta")

    def test_compone_un_mensaje_con_texto_y_html(self, monkeypatch):
        enviados = []

        class SesionFalsa:
            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def starttls(self):
                pass

            def login(self, *_a):
                pass

            def send_message(self, correo):
                enviados.append(correo)

        monkeypatch.setattr(notificacion.smtplib, "SMTP", SesionFalsa)
        notificador = notificacion.NotificadorSMTP(self._configuracion())
        notificacion.notificar_ficha(notificador, _ficha(), ENTRANTE)

        assert len(enviados) == 1
        correo = enviados[0]
        assert correo["To"] == "luis@cendoj.ramajudicial.gov.co"
        assert correo["Subject"].startswith("[ALTA]")
        tipos = {parte.get_content_type() for parte in correo.walk()}
        assert "text/plain" in tipos
        assert "text/html" in tipos

    def test_el_aviso_de_fallo_identifica_el_correo_y_el_motivo(self, monkeypatch):
        enviados = []
        monkeypatch.setattr(
            notificacion.NotificadorSMTP,
            "enviar",
            lambda self, asunto, texto, html=None: enviados.append((asunto, texto)),
        )
        notificador = notificacion.NotificadorSMTP(self._configuracion())
        notificacion.notificar_fallo(notificador, ENTRANTE, "TimeoutError: agotado", 3)

        asunto, texto = enviados[0]
        assert "No se pudo clasificar" in asunto
        assert "TimeoutError: agotado" in texto
        assert "Intentos: 3" in texto
        assert "correspondencia pendiente" in texto
