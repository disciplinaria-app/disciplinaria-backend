"""Pruebas del envío de la ficha por SMTP."""

from ingesta import notificacion
from ingesta.mensaje import CABECERA_SISTEMA, CorreoEntrante
from models.schemas import Alerta, FichaRedactada, TriageResponse

ENTRANTE = CorreoEntrante(
    identificador="<abc@previsora.gov.co>",
    remitente="Notificaciones Previsora <notificaciones@previsora.gov.co>",
    asunto="RE: Oficio CNDJ-2025-0412",
    fecha="2025-10-01",
    cuerpo="Cordial saludo, adjunto damos respuesta.",
    reenviado=True,
    advertencias=["Aviso de la lectura del correo."],
)

FICHA = TriageResponse(
    entidad_remitente="La Previsora S.A. Compañía de Seguros",
    tipo_acto="DEVOLUCION_POR_COMPETENCIA",
    materia="La entidad advierte que la comunicación fue dirigida por error.",
    resumen="La Previsora informa que el oficio correspondía a Fiduprevisora S.A.",
    alertas=[
        Alerta(
            codigo="ENTIDAD_DISTINTA",
            descripcion="Se dirigió a Fiduprevisora pero responde La Previsora.",
            severidad="ALTA",
            origen="COTEJO",
        )
    ],
    urgencia="ALTA",
)


class SesionFalsa:
    enviados: list = []

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
        SesionFalsa.enviados.append(correo)


def _configuracion(**cambios):
    base = dict(
        servidor="smtp.ejemplo.com",
        usuario="buzon@ejemplo.com",
        clave="clave",
        remitente="buzon@ejemplo.com",
        destinatario="luis@cendoj.ramajudicial.gov.co",
    )
    base.update(cambios)
    return notificacion.ConfiguracionSMTP(**base)


def _notificador(monkeypatch, **cambios):
    SesionFalsa.enviados = []
    monkeypatch.setattr(notificacion.smtplib, "SMTP", SesionFalsa)
    monkeypatch.setattr(notificacion.smtplib, "SMTP_SSL", SesionFalsa)
    return notificacion.NotificadorSMTP(_configuracion(**cambios))


class TestAdaptacionDeDatos:
    def test_traslada_los_datos_del_correo_a_la_capa_de_presentacion(self):
        datos = notificacion.datos_del_correo(ENTRANTE)
        assert datos.remitente == ENTRANTE.remitente
        assert datos.asunto == ENTRANTE.asunto
        assert datos.fecha == "2025-10-01"
        assert datos.reenviado is True
        assert datos.advertencias == ["Aviso de la lectura del correo."]


class TestEnvio:
    def test_configuracion_incompleta_se_rechaza_con_un_mensaje_claro(self, monkeypatch):
        notificador = _notificador(monkeypatch, servidor="")
        try:
            notificador.enviar("asunto", "texto")
        except ValueError as exc:
            assert "SMTP_SERVIDOR" in str(exc)
        else:
            raise AssertionError("debía rechazarse la configuración incompleta")

    def test_compone_un_mensaje_con_texto_y_html(self, monkeypatch):
        notificador = _notificador(monkeypatch)
        notificacion.notificar_ficha(notificador, FICHA, ENTRANTE)

        assert len(SesionFalsa.enviados) == 1
        correo = SesionFalsa.enviados[0]
        assert correo["To"] == "luis@cendoj.ramajudicial.gov.co"
        assert correo["Subject"].startswith("[ALTA]")
        tipos = {parte.get_content_type() for parte in correo.walk()}
        assert "text/plain" in tipos
        assert "text/html" in tipos

    def test_la_ficha_remitida_lleva_la_marca_del_sistema(self, monkeypatch):
        notificador = _notificador(monkeypatch)
        notificador.enviar("asunto", "texto")
        assert SesionFalsa.enviados[0][CABECERA_SISTEMA] == "ficha"

    def test_sin_starttls_se_emplea_una_sesion_cifrada_desde_el_inicio(self, monkeypatch):
        notificador = _notificador(monkeypatch, usar_starttls=False, puerto=465)
        notificador.enviar("asunto", "texto")
        assert len(SesionFalsa.enviados) == 1

    def test_reutiliza_la_redaccion_que_la_ficha_ya_trae(self, monkeypatch):
        """
        Si la ficha llega redactada —como la devuelve el endpoint—, no se
        vuelve a componer: se remite tal cual.
        """
        notificador = _notificador(monkeypatch)
        ficha = FICHA.model_copy(
            update={
                "redaccion": FichaRedactada(
                    asunto="[MEDIA] Asunto ya redactado", texto="Cuerpo ya redactado", html="<p>x</p>"
                )
            }
        )
        notificacion.notificar_ficha(notificador, ficha, ENTRANTE)
        assert SesionFalsa.enviados[0]["Subject"] == "[MEDIA] Asunto ya redactado"

    def test_el_aviso_de_fallo_se_remite_con_el_motivo(self, monkeypatch):
        notificador = _notificador(monkeypatch)
        notificacion.notificar_fallo(notificador, ENTRANTE, "TimeoutError: agotado", 3)
        correo = SesionFalsa.enviados[0]
        assert "No se pudo clasificar" in correo["Subject"]
        plano = correo.get_body(preferencelist=("plain",)).get_content()
        assert "TimeoutError: agotado" in plano

    def test_el_aviso_de_fallo_sin_correo_legible(self, monkeypatch):
        notificador = _notificador(monkeypatch)
        notificacion.notificar_fallo(notificador, None, "ValueError", 3)
        assert "correo no legible" in SesionFalsa.enviados[0]["Subject"]
