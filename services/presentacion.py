"""
Redacción de la ficha para su lectura.

La ficha se redacta para ser leída en el teléfono y decidida en diez segundos:
el asunto lleva la urgencia y la entidad, y las alertas encabezan el cuerpo.
Las advertencias del procesamiento van al final pero nunca se omiten: el lector
debe saber cuándo la ficha se construyó sobre material incompleto.

El módulo es común a las tres rutas de ingesta. La de reenvío la remite por
SMTP; la de Power Automate la recibe ya redactada en la respuesta del endpoint,
de modo que el flujo no deba componer el mensaje con expresiones ni recorrer la
lista de alertas.
"""

import html
from dataclasses import dataclass, field

from models.schemas import FichaRedactada, TriageResponse

_SIMBOLO_SEVERIDAD = {"ALTA": "●", "MEDIA": "◐", "BAJA": "○"}
_COLOR_SEVERIDAD = {"ALTA": "#b3261e", "MEDIA": "#9a6700", "BAJA": "#555555"}
LIMITE_ASUNTO = 160


@dataclass
class DatosCorreo:
    """Lo que se sabe del correo recibido, al margen de cómo se obtuvo."""

    remitente: str = ""
    asunto: str = ""
    fecha: str | None = None
    reenviado: bool = False
    advertencias: list[str] = field(default_factory=list)


def recortar(texto: str, limite: int) -> str:
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def componer_asunto(ficha: TriageResponse, datos: DatosCorreo) -> str:
    """Asunto que permite decidir sin abrir el mensaje."""
    entidad = recortar(
        ficha.entidad_remitente or datos.remitente or "Remitente no determinado", 50
    )
    partes = [f"[{ficha.urgencia}]", entidad, ficha.tipo_acto.replace("_", " ").title()]
    alerta_grave = next((a for a in ficha.alertas if a.severidad == "ALTA"), None)
    if alerta_grave:
        partes.append(alerta_grave.codigo.replace("_", " ").title())
    return recortar(" · ".join(partes), LIMITE_ASUNTO)


def _lineas_comunes(ficha: TriageResponse, datos: DatosCorreo) -> list[tuple[str, str]]:
    """Campos de la ficha, en el orden en que conviene leerlos."""
    lineas: list[tuple[str, str]] = [
        ("Entidad que suscribe", ficha.entidad_remitente or "No determinada"),
        ("Tipo de acto", ficha.tipo_acto.replace("_", " ").title()),
        ("Materia", ficha.materia),
    ]
    if ficha.radicados:
        lineas.append(("Radicados citados", ", ".join(ficha.radicados[:8])))
    if ficha.expedientes:
        lineas.append(("Expedientes", ", ".join(ficha.expedientes[:8])))
    lineas.append(("Requiere actuación", "Sí" if ficha.requiere_actuacion else "No"))
    if ficha.actuacion_sugerida:
        lineas.append(("Actuación sugerida", ficha.actuacion_sugerida))
    if ficha.termino:
        if ficha.termino.dias_restantes is None:
            plazo = ficha.termino.fundamento or "Término sin fecha determinada"
        elif ficha.termino.dias_restantes < 0:
            plazo = (
                f"Venció el {ficha.termino.fecha_limite} "
                f"(hace {abs(ficha.termino.dias_restantes)} días)"
            )
        else:
            plazo = (
                f"Vence el {ficha.termino.fecha_limite} "
                f"(restan {ficha.termino.dias_restantes} días)"
            )
        lineas.append(("Término", plazo))
    lineas.append(("Correo recibido", f"{datos.remitente} — {datos.asunto or 'sin asunto'}"))
    if datos.fecha:
        lineas.append(("Fecha", datos.fecha))
    if datos.reenviado:
        lineas.append(("Procedencia", "Reenvío: el remitente se recuperó del mensaje original"))
    if ficha.adjuntos_no_analizados:
        lineas.append(
            (
                "Anexos no analizados",
                ", ".join(ficha.adjuntos_no_analizados[:8]) + " (solo se analizan PDF)",
            )
        )
    if ficha.documentos:
        lineas.append(
            (
                "Documentos leídos",
                "; ".join(
                    f"{d.nombre} ({d.metodo.replace('_', ' ').lower()}, {d.paginas or '?'} pág.)"
                    for d in ficha.documentos
                ),
            )
        )
    return lineas


def componer_texto(ficha: TriageResponse, datos: DatosCorreo) -> str:
    bloques: list[str] = []

    if ficha.alertas:
        bloques.append("ALERTAS")
        bloques.extend(
            f"  {_SIMBOLO_SEVERIDAD.get(a.severidad, '·')} [{a.severidad}] "
            f"{a.codigo}: {a.descripcion}"
            for a in ficha.alertas
        )
        bloques.append("")

    bloques.append(ficha.resumen)
    bloques.append("")

    for etiqueta, valor in _lineas_comunes(ficha, datos):
        bloques.append(f"{etiqueta}: {valor}")

    advertencias = list(ficha.advertencias) + list(datos.advertencias)
    if advertencias:
        bloques.append("")
        bloques.append("ADVERTENCIAS DEL PROCESAMIENTO")
        bloques.extend(f"  - {a}" for a in advertencias)

    bloques.append("")
    bloques.append(
        "Esta ficha es un instrumento de triage y no sustituye la lectura del documento."
    )
    return "\n".join(bloques)


def componer_html(ficha: TriageResponse, datos: DatosCorreo) -> str:
    def escapar(valor: str) -> str:
        return html.escape(str(valor or ""))

    partes = [
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        'font-size:15px;line-height:1.5;color:#1a1a1a;max-width:680px">'
    ]

    if ficha.alertas:
        partes.append('<div style="margin:0 0 18px">')
        for alerta in ficha.alertas:
            color = _COLOR_SEVERIDAD.get(alerta.severidad, "#555555")
            partes.append(
                f'<div style="border-left:3px solid {color};padding:6px 0 6px 12px;margin:0 0 8px">'
                f'<strong style="color:{color}">{escapar(alerta.severidad)} · '
                f"{escapar(alerta.codigo.replace('_', ' '))}</strong><br>"
                f"{escapar(alerta.descripcion)}</div>"
            )
        partes.append("</div>")

    partes.append(f'<p style="margin:0 0 18px">{escapar(ficha.resumen)}</p>')

    partes.append('<table style="border-collapse:collapse;width:100%">')
    for etiqueta, valor in _lineas_comunes(ficha, datos):
        partes.append(
            "<tr>"
            '<td style="padding:4px 12px 4px 0;vertical-align:top;color:#666;'
            f'white-space:nowrap">{escapar(etiqueta)}</td>'
            f'<td style="padding:4px 0;vertical-align:top">{escapar(valor)}</td>'
            "</tr>"
        )
    partes.append("</table>")

    advertencias = list(ficha.advertencias) + list(datos.advertencias)
    if advertencias:
        partes.append(
            '<div style="margin:18px 0 0;padding:10px 12px;background:#f6f6f4;'
            'border-radius:4px;font-size:13px;color:#555">'
            "<strong>Advertencias del procesamiento</strong>"
            "<ul style='margin:6px 0 0;padding-left:18px'>"
        )
        partes.extend(f"<li>{escapar(a)}</li>" for a in advertencias)
        partes.append("</ul></div>")

    partes.append(
        '<p style="margin:18px 0 0;font-size:12px;color:#888">Esta ficha es un '
        "instrumento de triage y no sustituye la lectura del documento.</p></div>"
    )
    return "".join(partes)


def componer(ficha: TriageResponse, datos: DatosCorreo) -> FichaRedactada:
    return FichaRedactada(
        asunto=componer_asunto(ficha, datos),
        texto=componer_texto(ficha, datos),
        html=componer_html(ficha, datos),
    )


def redactar_aviso_de_fallo(descripcion: str, motivo: str, intentos: int) -> FichaRedactada:
    """
    Redacta el aviso de que un correo no pudo procesarse.

    Un correo que no se pudo clasificar nunca se descarta en silencio: el
    destinatario debe saber que hay correspondencia pendiente de lectura.
    """
    texto = "\n".join(
        [
            "El sistema no pudo clasificar un correo tras agotar los reintentos.",
            "",
            f"Correo: {descripcion}",
            f"Intentos: {intentos}",
            f"Motivo: {motivo}",
            "",
            "Revise el correo directamente en el buzón: hay correspondencia pendiente",
            "de lectura que el sistema no alcanzó a procesar.",
        ]
    )
    return FichaRedactada(
        asunto=recortar(f"[ALTA] No se pudo clasificar · {descripcion}", LIMITE_ASUNTO),
        texto=texto,
        html=f"<pre style=\"font-family:inherit;white-space:pre-wrap\">{html.escape(texto)}</pre>",
    )
