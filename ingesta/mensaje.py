"""
Lectura de un mensaje MIME y conversión al material que el triage necesita.

Dos problemas del correo real gobiernan este módulo.

El primero es el reenvío. Al reenviar, el remitente del sobre pasa a ser el
propio buzón y el remitente real queda sepultado dentro del mensaje: ora como
adjunto «message/rfc822», ora como bloque de encabezados en el cuerpo. Sin
desenvolverlo, el cotejo compararía la entidad interpelada contra el propio
despacho y jamás advertiría la discrepancia.

El segundo son las firmas. Casi todo correo institucional lleva el logotipo de
la entidad como imagen incorporada. Tratarla como adjunto produciría una alerta
de documento ilegible en cada mensaje, que es la forma más rápida de que el
destinatario deje de leer las alertas. Solo se admiten adjuntos reales, y entre
ellos solo los PDF se someten a extracción; los demás se enuncian por su nombre.
"""

import re
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from services import correo as servicio_correo

EXTENSIONES_PDF = (".pdf",)
MAGIA_PDF = b"%PDF"

# Cabecera con que el sistema marca las fichas que él mismo remite. Si el buzón
# de fichas coincide con el de ingesta —que es la configuración por omisión—,
# la ficha volvería a ese buzón, se clasificaría a sí misma y el ciclo se
# realimentaría sin término. Esta marca corta el bucle.
CABECERA_SISTEMA = "X-Disciplinaria-Triage"

# Directivas que el usuario puede escribir al reenviar a mano. Resuelven una
# limitación propia de esta ruta: la entidad interpelada se deduce de la cadena
# citada, pero el radicado que el despacho remitió no es inferible, de modo que
# sin declararlo ese cotejo queda inutilizable.
_DIRECTIVAS = {
    "entidad": re.compile(r"^\s*#\s*entidad\s*:?\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "radicado": re.compile(r"^\s*#\s*radicado\s*:?\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "asunto": re.compile(r"^\s*#\s*asunto\s*:?\s*(.+)$", re.IGNORECASE | re.MULTILINE),
}


def extraer_directivas(cuerpo: str) -> dict[str, str]:
    """
    Lee las directivas que el usuario haya escrito al reenviar.

    Se buscan en el cuerpo del reenvío —no en el mensaje original—, pues son
    anotaciones del propio usuario. Un reenvío automático por regla de Outlook
    no las trae, y entonces el contexto se deduce de la cadena citada.
    """
    halladas: dict[str, str] = {}
    for nombre, patron in _DIRECTIVAS.items():
        coincidencia = patron.search(cuerpo or "")
        if coincidencia:
            valor = coincidencia.group(1).strip()
            if valor:
                halladas[nombre] = valor[:200]
    return halladas


@dataclass
class CorreoEntrante:
    """Material de un correo, ya normalizado para el triage."""

    identificador: str
    remitente: str
    asunto: str
    fecha: str | None
    cuerpo: str
    adjuntos_pdf: list[tuple[str, bytes]] = field(default_factory=list)
    otros_adjuntos: list[str] = field(default_factory=list)
    reenviado: bool = False
    generado_por_el_sistema: bool = False
    advertencias: list[str] = field(default_factory=list)
    # Contexto declarado por el usuario mediante directivas en el reenvío.
    entidad_declarada: str | None = None
    radicado_declarado: str | None = None
    asunto_declarado: str | None = None


def _es_pdf(nombre: str, tipo: str, contenido: bytes) -> bool:
    """
    Reconoce un PDF por su tipo declarado, su extensión o su firma binaria.

    Las entidades remiten con frecuencia el adjunto como
    «application/octet-stream», de modo que el tipo declarado no basta.
    """
    if tipo == "application/pdf":
        return True
    if nombre.lower().endswith(EXTENSIONES_PDF):
        return True
    return contenido[:4] == MAGIA_PDF


def _texto_del_cuerpo(mensaje: EmailMessage) -> str:
    """Obtiene el cuerpo en texto, convirtiendo el HTML si es la única forma."""
    try:
        parte = mensaje.get_body(preferencelist=("plain", "html"))
    except Exception:
        parte = None
    if parte is None:
        return ""
    try:
        contenido = parte.get_content()
    except Exception:
        carga = parte.get_payload(decode=True) or b""
        contenido = carga.decode("utf-8", errors="replace")
    if not isinstance(contenido, str):
        return ""
    if parte.get_content_type() == "text/html":
        return servicio_correo.despojar_html(contenido)
    return contenido


def _fecha_iso(mensaje: EmailMessage) -> str | None:
    cabecera = mensaje.get("Date")
    if not cabecera:
        return None
    try:
        return parsedate_to_datetime(str(cabecera)).date().isoformat()
    except (TypeError, ValueError):
        return None


def _mensaje_adjunto(mensaje: EmailMessage) -> EmailMessage | None:
    """Localiza el mensaje original cuando viene reenviado como adjunto."""
    for parte in mensaje.walk():
        if parte.get_content_type() != "message/rfc822":
            continue
        carga = parte.get_payload()
        if isinstance(carga, list) and carga:
            interno = carga[0]
            if isinstance(interno, EmailMessage):
                return interno
        if isinstance(carga, EmailMessage):
            return carga
    return None


def _recoger_adjuntos(
    mensaje: EmailMessage,
) -> tuple[list[tuple[str, bytes]], list[str], list[str]]:
    """
    Separa los adjuntos PDF de los demás y descarta el contenido incorporado.

    Devuelve (pdf, nombres de otros adjuntos, advertencias).
    """
    pdf: list[tuple[str, bytes]] = []
    otros: list[str] = []
    advertencias: list[str] = []

    for parte in mensaje.walk():
        if parte.get_content_maintype() == "multipart":
            continue
        if parte.get_content_type() == "message/rfc822":
            continue

        disposicion = (parte.get_content_disposition() or "").lower()
        nombre = parte.get_filename()

        # El contenido incorporado —logotipos y firmas— no es correspondencia.
        if disposicion == "inline" or parte.get("Content-ID"):
            continue
        if disposicion != "attachment" and not nombre:
            continue

        try:
            contenido = parte.get_payload(decode=True) or b""
        except Exception as exc:
            advertencias.append(
                f"No se pudo decodificar el adjunto «{nombre or 'sin nombre'}»: {exc}"
            )
            continue

        nombre = nombre or "adjunto"
        if _es_pdf(nombre, parte.get_content_type(), contenido):
            pdf.append((nombre, contenido))
        else:
            otros.append(nombre)

    return pdf, otros, advertencias


def parsear(crudo: bytes, direcciones_propias: frozenset[str] = frozenset()) -> CorreoEntrante:
    """
    Convierte un mensaje MIME en el material que el triage necesita.

    `direcciones_propias` son los buzones del propio usuario. Si el mensaje
    proviene de uno de ellos, se presume reenviado y se intenta recuperar el
    remitente original.
    """
    mensaje = message_from_bytes(crudo, policy=policy.default)
    advertencias: list[str] = []

    identificador = str(mensaje.get("Message-ID") or "").strip()
    propio_del_sistema = bool(mensaje.get(CABECERA_SISTEMA))
    remitente = str(mensaje.get("From") or "").strip()
    asunto = str(mensaje.get("Subject") or "").strip()
    fecha = _fecha_iso(mensaje)

    # Las directivas se leen del cuerpo externo, que es el del reenvío, antes
    # de desenvolverlo y descartarlo.
    directivas = extraer_directivas(_texto_del_cuerpo(mensaje))

    direccion_sobre = servicio_correo.extraer_direccion(remitente)
    propio = bool(direccion_sobre) and direccion_sobre in direcciones_propias
    sospecha_reenvio = propio or servicio_correo.parece_reenvio(asunto)

    # Primera forma de reenvío: el original viaja como adjunto message/rfc822.
    interno = _mensaje_adjunto(mensaje)
    if interno is not None:
        pdf, otros, avisos = _recoger_adjuntos(interno)
        advertencias.extend(avisos)
        return CorreoEntrante(
            identificador=identificador or str(interno.get("Message-ID") or "").strip(),
            remitente=str(interno.get("From") or remitente).strip(),
            asunto=str(interno.get("Subject") or asunto).strip(),
            fecha=_fecha_iso(interno) or fecha,
            cuerpo=_texto_del_cuerpo(interno),
            adjuntos_pdf=pdf,
            otros_adjuntos=otros,
            reenviado=True,
            generado_por_el_sistema=propio_del_sistema,
            advertencias=advertencias,
            entidad_declarada=directivas.get("entidad"),
            radicado_declarado=directivas.get("radicado"),
            asunto_declarado=directivas.get("asunto"),
        )

    cuerpo = _texto_del_cuerpo(mensaje)
    pdf, otros, avisos = _recoger_adjuntos(mensaje)
    advertencias.extend(avisos)
    reenviado = False

    # Segunda forma: el original aparece como bloque de encabezados en el cuerpo.
    if sospecha_reenvio:
        remitente_interno, asunto_interno, cuerpo_interno = servicio_correo.desenvolver_reenvio(
            cuerpo
        )
        if remitente_interno:
            remitente = remitente_interno
            asunto = asunto_interno or asunto
            cuerpo = cuerpo_interno
            reenviado = True
        elif propio:
            advertencias.append(
                "El correo proviene de un buzón propio pero no se identificó el bloque "
                "del mensaje reenviado; el remitente y el asunto corresponden al reenvío, "
                "no a la entidad que escribió."
            )

    return CorreoEntrante(
        identificador=identificador,
        remitente=remitente,
        asunto=asunto,
        fecha=fecha,
        cuerpo=cuerpo,
        adjuntos_pdf=pdf,
        otros_adjuntos=otros,
        reenviado=reenviado,
        generado_por_el_sistema=propio_del_sistema,
        advertencias=advertencias,
        entidad_declarada=directivas.get("entidad"),
        radicado_declarado=directivas.get("radicado"),
        asunto_declarado=directivas.get("asunto"),
    )
