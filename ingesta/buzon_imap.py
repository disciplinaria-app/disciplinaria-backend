"""
Acceso al buzón de reenvío por IMAP.

El buzón es propio del sistema, no el institucional: una regla de Outlook
reenvía a él la correspondencia que debe clasificarse. Esta ruta no exige
intervención del área técnica ni credenciales del buzón institucional.
"""

import imaplib
from dataclasses import dataclass
from typing import Iterator

TIEMPO_DE_ESPERA = 60


@dataclass
class ConfiguracionIMAP:
    servidor: str
    usuario: str
    clave: str
    puerto: int = 993
    carpeta: str = "INBOX"
    usar_ssl: bool = True

    def completa(self) -> bool:
        return bool(self.servidor and self.usuario and self.clave)


class BuzonIMAP:
    """
    Conexión al buzón, utilizable como gestor de contexto.

    Se consultan los mensajes no leídos y se marcan como leídos solo cuando su
    procesamiento concluye, de modo que una caída a mitad de ciclo no haga
    perder correspondencia.
    """

    def __init__(self, configuracion: ConfiguracionIMAP):
        self.configuracion = configuracion
        self._conexion: imaplib.IMAP4 | None = None

    def __enter__(self) -> "BuzonIMAP":
        self.conectar()
        return self

    def __exit__(self, *_excepcion) -> None:
        self.cerrar()

    def conectar(self) -> None:
        configuracion = self.configuracion
        if not configuracion.completa():
            raise ValueError(
                "La configuración IMAP está incompleta: se requieren IMAP_SERVIDOR, "
                "IMAP_USUARIO e IMAP_CLAVE."
            )
        constructor = imaplib.IMAP4_SSL if configuracion.usar_ssl else imaplib.IMAP4
        self._conexion = constructor(
            configuracion.servidor, configuracion.puerto, timeout=TIEMPO_DE_ESPERA
        )
        self._conexion.login(configuracion.usuario, configuracion.clave)
        self._conexion.select(configuracion.carpeta)

    def cerrar(self) -> None:
        if self._conexion is None:
            return
        try:
            self._conexion.close()
        except (imaplib.IMAP4.error, OSError):
            pass
        try:
            self._conexion.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
        self._conexion = None

    def _exigir_conexion(self) -> imaplib.IMAP4:
        if self._conexion is None:
            raise RuntimeError("El buzón no está conectado.")
        return self._conexion

    def identificadores_sin_leer(self, limite: int) -> list[bytes]:
        """
        Devuelve los UID de los mensajes no leídos.

        Se usan UID y no números de secuencia porque estos se desplazan cuando
        el buzón cambia durante la sesión, y un desplazamiento haría marcar como
        leído un correo distinto del procesado.
        """
        conexion = self._exigir_conexion()
        estado, datos = conexion.uid("SEARCH", None, "UNSEEN")
        if estado != "OK" or not datos or not datos[0]:
            return []
        # Se atienden los más antiguos primero, para no postergar indefinidamente
        # un correo cuando el buzón recibe más de lo que cabe en un ciclo.
        return datos[0].split()[:limite]

    def mensajes_sin_leer(self, limite: int) -> Iterator[tuple[bytes, bytes]]:
        """
        Entrega los mensajes no leídos como (identificador, mensaje crudo).

        Se usa BODY.PEEK para no marcarlos como leídos por el solo hecho de
        descargarlos: la marca se aplica después, cuando el procesamiento
        concluye.
        """
        conexion = self._exigir_conexion()
        for identificador in self.identificadores_sin_leer(limite):
            estado, datos = conexion.uid("FETCH", identificador, "(BODY.PEEK[])")
            if estado != "OK" or not datos:
                continue
            crudo = next(
                (
                    parte[1]
                    for parte in datos
                    if isinstance(parte, tuple) and isinstance(parte[1], (bytes, bytearray))
                ),
                None,
            )
            if crudo:
                yield identificador, bytes(crudo)

    def marcar_leido(self, identificador: bytes) -> None:
        conexion = self._exigir_conexion()
        conexion.uid("STORE", identificador, "+FLAGS", "\\Seen")
