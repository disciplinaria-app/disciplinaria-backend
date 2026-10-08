"""
Worker de ingesta por reenvío.

Sondea el buzón propio del sistema, clasifica cada correo nuevo y remite la
ficha al usuario. Invoca el triage en proceso, sin pasar por la API HTTP: es el
mismo código y ahorra un salto de red y una credencial.

Garantías que el ciclo sostiene:

- Un correo se marca como leído solo cuando su procesamiento concluye, de modo
  que una caída a mitad de ciclo no haga perder correspondencia.
- El fallo de un correo no detiene los demás ni el ciclo.
- Tras agotar los reintentos, el correo se da por procesado y se avisa al
  usuario. Nunca se descarta en silencio ni se reintenta sin fin.
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass

import config
from ingesta import notificacion
from ingesta.buzon_imap import BuzonIMAP, ConfiguracionIMAP
from ingesta.estado import Estado
from ingesta.mensaje import CorreoEntrante, parsear
from ingesta.notificacion import ConfiguracionSMTP, NotificadorSMTP
from models.schemas import ContextoEnvio, TriageResponse
from services import triage

ESPERA_TRAS_FALLO_DE_CONEXION = (30, 60, 120, 300)


@dataclass
class Resumen:
    """Lo ocurrido en un ciclo, para la bitácora."""

    revisados: int = 0
    clasificados: int = 0
    fallidos: int = 0
    omitidos: int = 0

    def __str__(self) -> str:
        return (
            f"revisados={self.revisados} clasificados={self.clasificados} "
            f"fallidos={self.fallidos} omitidos={self.omitidos}"
        )


def construir_contexto(entrante: CorreoEntrante) -> ContextoEnvio:
    """
    Arma el contexto del envío a partir de lo que el usuario haya declarado.

    Lo que no se declare queda en None, y el triage intentará deducir la entidad
    interpelada de la cadena citada. El radicado no se deduce: sin declararlo,
    ese cotejo queda indeterminado, y así se informa en la ficha.
    """
    return ContextoEnvio(
        entidad_interpelada=entrante.entidad_declarada,
        radicado_enviado=entrante.radicado_declarado,
        asunto_enviado=entrante.asunto_declarado,
    )


async def clasificar(entrante: CorreoEntrante) -> TriageResponse:
    return await triage.procesar(
        remitente=entrante.remitente,
        asunto=entrante.asunto,
        cuerpo=entrante.cuerpo,
        fecha_recepcion=entrante.fecha,
        contexto=construir_contexto(entrante),
        archivos=entrante.adjuntos_pdf,
        adjuntos_no_analizados=entrante.otros_adjuntos,
    )


async def procesar_mensaje(
    crudo: bytes,
    notificador: NotificadorSMTP,
    estado: Estado,
    direcciones_propias: frozenset[str],
) -> str:
    """
    Procesa un mensaje y devuelve el desenlace: «clasificado», «omitido» o
    «fallido». No propaga excepciones: el fallo de un correo no debe detener
    los demás.
    """
    entrante: CorreoEntrante | None = None
    try:
        entrante = parsear(crudo, direcciones_propias)
        if entrante.generado_por_el_sistema:
            # Es una ficha que el propio sistema remitió: clasificarla
            # realimentaría el ciclo sin término.
            return "omitido"
        if entrante.identificador and estado.ya_procesado(entrante.identificador):
            return "omitido"

        ficha = await clasificar(entrante)
        notificacion.notificar_ficha(notificador, ficha, entrante)
        estado.registrar_exito(entrante.identificador)
        return "clasificado"

    except Exception as exc:
        motivo = f"{type(exc).__name__}: {exc}"
        identificador = entrante.identificador if entrante else ""
        intentos = estado.registrar_fallo(identificador, motivo)
        print(f"  fallo al procesar ({intentos} intento/s): {motivo}", file=sys.stderr)

        if intentos >= config.MAX_INTENTOS_POR_CORREO or not identificador:
            # Se agotaron los reintentos: se avisa y se da por procesado, para
            # no reintentar sin fin, pero nunca en silencio.
            try:
                notificacion.notificar_fallo(notificador, entrante, motivo, intentos)
            except Exception as error_aviso:
                # Si tampoco se puede avisar, el correo se conserva sin leer.
                # Darlo por procesado sin que el usuario lo sepa equivaldría a
                # perder correspondencia, que es lo único inadmisible aquí.
                print(
                    f"  no se pudo avisar del fallo ({error_aviso}); el correo se "
                    "conserva sin leer",
                    file=sys.stderr,
                )
                raise _Reintentable(motivo) from exc
            estado.registrar_exito(identificador)
            return "fallido"
        # Quedan reintentos: el correo se deja sin leer para el próximo ciclo.
        raise _Reintentable(motivo) from exc


class _Reintentable(Exception):
    """El correo falló pero conserva reintentos: no se marca como leído."""


async def ejecutar_ciclo(
    buzon: BuzonIMAP,
    notificador: NotificadorSMTP,
    estado: Estado,
    limite: int,
    direcciones_propias: frozenset[str],
) -> Resumen:
    resumen = Resumen()
    for identificador, crudo in buzon.mensajes_sin_leer(limite):
        resumen.revisados += 1
        try:
            desenlace = await procesar_mensaje(crudo, notificador, estado, direcciones_propias)
        except _Reintentable:
            resumen.fallidos += 1
            # Se deja sin leer a propósito, para reintentarlo en el próximo ciclo.
            continue

        if desenlace == "clasificado":
            resumen.clasificados += 1
        elif desenlace == "omitido":
            resumen.omitidos += 1
        else:
            resumen.fallidos += 1

        try:
            buzon.marcar_leido(identificador)
        except Exception as exc:
            print(f"  no se pudo marcar como leído: {exc}", file=sys.stderr)

    estado.guardar()
    return resumen


def configuracion_imap() -> ConfiguracionIMAP:
    return ConfiguracionIMAP(
        servidor=config.IMAP_SERVIDOR,
        usuario=config.IMAP_USUARIO,
        clave=config.IMAP_CLAVE,
        puerto=config.IMAP_PUERTO,
        carpeta=config.IMAP_CARPETA,
        usar_ssl=config.IMAP_SSL,
    )


def configuracion_smtp() -> ConfiguracionSMTP:
    return ConfiguracionSMTP(
        servidor=config.SMTP_SERVIDOR,
        usuario=config.SMTP_USUARIO,
        clave=config.SMTP_CLAVE,
        remitente=config.SMTP_REMITENTE,
        destinatario=config.DESTINATARIO_FICHAS,
        puerto=config.SMTP_PUERTO,
        usar_starttls=config.SMTP_STARTTLS,
    )


def verificar_configuracion() -> list[str]:
    """Enumera lo que falta para operar, antes de intentar conectarse."""
    faltantes: list[str] = []
    if not config.OPENROUTER_API_KEY:
        faltantes.append("OPENROUTER_API_KEY")
    if not configuracion_imap().completa():
        faltantes.append("IMAP_SERVIDOR, IMAP_USUARIO e IMAP_CLAVE")
    if not configuracion_smtp().completa():
        faltantes.append("SMTP_SERVIDOR, SMTP_REMITENTE y DESTINATARIO_FICHAS")
    return faltantes


def un_ciclo(limite: int) -> Resumen:
    """Abre el buzón, ejecuta un ciclo y lo cierra."""
    estado = Estado(config.ESTADO_INGESTA)
    notificador = NotificadorSMTP(configuracion_smtp())
    with BuzonIMAP(configuracion_imap()) as buzon:
        return asyncio.run(
            ejecutar_ciclo(
                buzon, notificador, estado, limite, config.DIRECCIONES_PROPIAS
            )
        )


def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="python -m ingesta.worker",
        description=(
            "Sondea el buzón de reenvío, clasifica la correspondencia nueva y remite "
            "la ficha al usuario."
        ),
    )
    analizador.add_argument(
        "--una-vez",
        action="store_true",
        help="Ejecuta un solo ciclo y termina, en lugar de sondear indefinidamente.",
    )
    analizador.add_argument(
        "--intervalo",
        type=int,
        default=config.INTERVALO_SONDEO,
        help="Segundos entre sondeos (por omisión, INTERVALO_SONDEO).",
    )
    analizador.add_argument(
        "--limite",
        type=int,
        default=config.MAX_CORREOS_POR_CICLO,
        help="Máximo de correos por ciclo (por omisión, MAX_CORREOS_POR_CICLO).",
    )
    opciones = analizador.parse_args(argumentos)

    faltantes = verificar_configuracion()
    if faltantes:
        print(
            "No se puede iniciar la ingesta. Falta configurar: " + "; ".join(faltantes),
            file=sys.stderr,
        )
        return 2

    if opciones.una_vez:
        try:
            print(f"ciclo único: {un_ciclo(opciones.limite)}")
        except Exception as exc:
            print(f"el ciclo falló: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0

    print(
        f"ingesta en marcha: buzón {config.IMAP_USUARIO}, carpeta {config.IMAP_CARPETA}, "
        f"sondeo cada {opciones.intervalo} s"
    )
    fallos_de_conexion = 0
    while True:
        try:
            print(f"ciclo: {un_ciclo(opciones.limite)}", flush=True)
            fallos_de_conexion = 0
            espera = opciones.intervalo
        except KeyboardInterrupt:
            print("ingesta detenida.")
            return 0
        except Exception as exc:
            # Una caída de red o del servidor de correo no debe terminar el
            # worker: se espera más en cada fallo consecutivo y se reintenta.
            indice = min(fallos_de_conexion, len(ESPERA_TRAS_FALLO_DE_CONEXION) - 1)
            espera = ESPERA_TRAS_FALLO_DE_CONEXION[indice]
            fallos_de_conexion += 1
            print(
                f"el ciclo falló ({type(exc).__name__}: {exc}); se reintenta en {espera} s",
                file=sys.stderr,
                flush=True,
            )
        try:
            time.sleep(espera)
        except KeyboardInterrupt:
            print("ingesta detenida.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
