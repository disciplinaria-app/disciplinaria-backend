"""
Envío de la ficha por SMTP.

La redacción de la ficha vive en `services/presentacion.py`, común a las tres
rutas de ingesta. Este módulo solo se ocupa del envío: la ruta de reenvío es la
única que remite el correo por su cuenta, pues la de Power Automate lo hace con
su propia acción de correo dentro del tenant.
"""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from ingesta.mensaje import CABECERA_SISTEMA, CorreoEntrante
from models.schemas import FichaRedactada, TriageResponse
from services import presentacion


def datos_del_correo(entrante: CorreoEntrante) -> presentacion.DatosCorreo:
    return presentacion.DatosCorreo(
        remitente=entrante.remitente,
        asunto=entrante.asunto,
        fecha=entrante.fecha,
        reenviado=entrante.reenviado,
        advertencias=list(entrante.advertencias),
    )


@dataclass
class ConfiguracionSMTP:
    servidor: str
    usuario: str
    clave: str
    remitente: str
    destinatario: str
    puerto: int = 587
    usar_starttls: bool = True

    def completa(self) -> bool:
        return bool(self.servidor and self.remitente and self.destinatario)


class NotificadorSMTP:
    """Remite la ficha al buzón del usuario."""

    def __init__(self, configuracion: ConfiguracionSMTP):
        self.configuracion = configuracion

    def enviar(self, asunto: str, texto: str, cuerpo_html: str | None = None) -> None:
        configuracion = self.configuracion
        if not configuracion.completa():
            raise ValueError(
                "La configuración SMTP está incompleta: se requieren SMTP_SERVIDOR, "
                "SMTP_REMITENTE y un destinatario."
            )

        correo = EmailMessage()
        correo["From"] = configuracion.remitente
        correo["To"] = configuracion.destinatario
        correo["Subject"] = asunto
        # Marca que impide que la ficha se clasifique a sí misma cuando el buzón
        # de destino coincide con el de ingesta.
        correo[CABECERA_SISTEMA] = "ficha"
        correo.set_content(texto)
        if cuerpo_html:
            correo.add_alternative(cuerpo_html, subtype="html")

        if configuracion.usar_starttls:
            with smtplib.SMTP(configuracion.servidor, configuracion.puerto, timeout=60) as sesion:
                sesion.starttls()
                if configuracion.usuario:
                    sesion.login(configuracion.usuario, configuracion.clave)
                sesion.send_message(correo)
        else:
            with smtplib.SMTP_SSL(
                configuracion.servidor, configuracion.puerto, timeout=60
            ) as sesion:
                if configuracion.usuario:
                    sesion.login(configuracion.usuario, configuracion.clave)
                sesion.send_message(correo)


def _remitir(notificador: NotificadorSMTP, redactada: FichaRedactada) -> None:
    notificador.enviar(redactada.asunto, redactada.texto, redactada.html)


def notificar_ficha(
    notificador: NotificadorSMTP, ficha: TriageResponse, entrante: CorreoEntrante
) -> None:
    redactada = ficha.redaccion or presentacion.componer(ficha, datos_del_correo(entrante))
    _remitir(notificador, redactada)


def notificar_fallo(
    notificador: NotificadorSMTP, entrante: CorreoEntrante | None, motivo: str, intentos: int
) -> None:
    """Avisa que un correo no pudo procesarse tras agotar los reintentos."""
    descripcion = (
        f"{entrante.remitente} — {entrante.asunto or 'sin asunto'}"
        if entrante
        else "correo no legible"
    )
    _remitir(notificador, presentacion.redactar_aviso_de_fallo(descripcion, motivo, intentos))
