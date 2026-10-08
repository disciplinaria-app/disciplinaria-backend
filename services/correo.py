"""
Normalización del cuerpo del correo.

La correspondencia institucional llega casi siempre como un reenvío acumulado:
el mensaje nuevo encabeza una cadena de respuestas anteriores. Entregar ese
bloque al modelo sin separarlo induce dos errores: atribuir a quien ahora
escribe lo que dijo otro, y tomar por vigente un término ya vencido.

Este módulo aísla el mensaje actual y conserva la cadena anterior como
contexto subordinado, pues de ella se infiere a qué entidad se escribió.
"""

import html
import re

# Marcas con que Outlook y los clientes de correo abren la cita del mensaje previo.
_SEPARADORES_CITA = (
    re.compile(r"^\s*-{2,}\s*(mensaje\s+original|original\s+message|mensaje\s+reenviado|forwarded\s+message)\s*-{2,}", re.IGNORECASE),
    re.compile(r"^\s*_{10,}\s*$"),
    re.compile(r"^\s*De:\s*.+$", re.IGNORECASE),
    re.compile(r"^\s*From:\s*.+$", re.IGNORECASE),
    re.compile(r"^\s*El\s+.{3,60}\s+escribi[oó]:\s*$", re.IGNORECASE),
    re.compile(r"^\s*On\s+.{3,80}\s+wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*Enviado\s+desde\s+mi\s+", re.IGNORECASE),
)

_ETIQUETA_HTML = re.compile(r"<[^>]+>")
_BLOQUE_NO_VISIBLE = re.compile(r"<(script|style|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_SALTO_HTML = re.compile(r"<\s*(br|/p|/div|/tr|/li)\s*/?\s*>", re.IGNORECASE)


def parece_html(texto: str) -> bool:
    return bool(re.search(r"<\s*(html|body|div|p|br|table|span)\b", texto or "", re.IGNORECASE))


def despojar_html(texto: str) -> str:
    """Convierte un cuerpo HTML en texto plano preservando los saltos de línea."""
    sin_ocultos = _BLOQUE_NO_VISIBLE.sub(" ", texto or "")
    con_saltos = _SALTO_HTML.sub("\n", sin_ocultos)
    plano = _ETIQUETA_HTML.sub(" ", con_saltos)
    plano = html.unescape(plano)
    plano = re.sub(r"[ \t ]+", " ", plano)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", plano).strip()


def _es_separador(linea: str) -> bool:
    return any(patron.match(linea) for patron in _SEPARADORES_CITA)


def limpiar_cuerpo(cuerpo: str) -> tuple[str, str]:
    """
    Separa el mensaje actual de la cadena de respuestas anteriores.

    Devuelve la tupla (mensaje_actual, cadena_anterior). Si no se detecta
    cita previa, la cadena anterior queda vacía.
    """
    if not cuerpo:
        return "", ""

    texto = despojar_html(cuerpo) if parece_html(cuerpo) else cuerpo
    lineas = texto.splitlines()

    corte = len(lineas)
    for indice, linea in enumerate(lineas):
        if _es_separador(linea):
            corte = indice
            break

    actuales = lineas[:corte]
    anteriores = lineas[corte:]

    # Dentro del mensaje actual puede subsistir texto citado con «>».
    actuales = [l for l in actuales if not l.lstrip().startswith(">")]

    mensaje = re.sub(r"\n\s*\n\s*\n+", "\n\n", "\n".join(actuales)).strip()
    cadena = re.sub(r"\n\s*\n\s*\n+", "\n\n", "\n".join(anteriores)).strip()
    return mensaje, cadena


def inferir_entidad_interpelada(cadena_anterior: str) -> str | None:
    """
    Intenta deducir de la cadena anterior la entidad a la que se escribió.

    Solo se apoya en encabezados explícitos («Para:», «To:», «Señores»). Si no
    los halla, devuelve None antes que arriesgar una inferencia: un dato
    inventado en este campo corrompería todo el cotejo posterior.
    """
    if not cadena_anterior:
        return None
    patrones = (
        re.compile(r"^\s*(?:Para|To|CC)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*Se[ñn]ores?\s*:?\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    )
    for patron in patrones:
        coincidencia = patron.search(cadena_anterior)
        if coincidencia:
            valor = coincidencia.group(1).strip()
            # Descartar listas de direcciones, que no identifican la entidad.
            valor = re.sub(r"<[^>]*>", "", valor).strip(" ;,")
            if valor and "@" not in valor and len(valor) > 3:
                return valor[:200]
    return None


# Marcas con que un cliente abre el bloque de un mensaje reenviado.
_APERTURA_REENVIO = re.compile(
    r"^\s*(?:-{2,}\s*(?:mensaje\s+(?:original|reenviado)|original\s+message|forwarded\s+message)\s*-{2,}"
    r"|_{10,})\s*$",
    re.IGNORECASE,
)
_ENCABEZADO_REMITENTE = re.compile(r"^\s*(?:De|From)\s*:\s*(.+)$", re.IGNORECASE)
_ENCABEZADO_ASUNTO = re.compile(r"^\s*(?:Asunto|Subject)\s*:\s*(.+)$", re.IGNORECASE)
_ENCABEZADO_CUALQUIERA = re.compile(
    r"^\s*(?:De|From|Para|To|CC|CCO|BCC|Enviado|Sent|Asunto|Subject|Fecha|Date|Importancia)\s*:",
    re.IGNORECASE,
)
_PREFIJOS_REENVIO = re.compile(r"^\s*(?:RV|RE?V|FW|FWD|Fwd)\s*:", re.IGNORECASE)

# Dentro de este número de líneas tras el «De:» debe aparecer el «Asunto:»
# para considerar que se trata de un bloque de encabezados y no de prosa.
_VENTANA_ENCABEZADOS = 12


def parece_reenvio(asunto: str | None) -> bool:
    """Reconoce el prefijo que los clientes antepuesen al reenviar."""
    return bool(_PREFIJOS_REENVIO.match(asunto or ""))


def desenvolver_reenvio(cuerpo: str) -> tuple[str | None, str | None, str]:
    """
    Desenvuelve un mensaje reenviado en línea.

    Devuelve (remitente_original, asunto_original, cuerpo_original). El cuerpo
    original es cuanto sigue al bloque de encabezados reenviados.

    Esta operación es indispensable en la ruta de reenvío: al reenviar, el
    remitente del sobre pasa a ser el propio usuario y el remitente real queda
    sepultado en el bloque interno. Sin desenvolverlo, el cotejo compararía la
    entidad interpelada contra el propio despacho y jamás advertiría la
    discrepancia que motiva todo el módulo.

    Si no se identifica un bloque de encabezados, devuelve (None, None, cuerpo)
    para que el llamador conserve los datos del sobre.
    """
    if not cuerpo:
        return None, None, ""

    texto = despojar_html(cuerpo) if parece_html(cuerpo) else cuerpo
    lineas = texto.splitlines()

    for indice, linea in enumerate(lineas):
        coincidencia = _ENCABEZADO_REMITENTE.match(linea)
        if not coincidencia:
            continue

        # El «De:» debe pertenecer a un bloque de encabezados, no a la prosa.
        ventana = lineas[indice + 1 : indice + 1 + _VENTANA_ENCABEZADOS]
        asunto = None
        fin_bloque = indice + 1
        for desplazamiento, siguiente in enumerate(ventana):
            if _ENCABEZADO_ASUNTO.match(siguiente):
                asunto = _ENCABEZADO_ASUNTO.match(siguiente).group(1).strip()
                fin_bloque = indice + 1 + desplazamiento + 1
                break
            if not _ENCABEZADO_CUALQUIERA.match(siguiente) and siguiente.strip():
                # Línea de prosa antes del asunto: no era un bloque de encabezados.
                break
        if asunto is None:
            continue

        remitente = coincidencia.group(1).strip()
        cuerpo_original = "\n".join(lineas[fin_bloque:]).strip()
        return remitente or None, asunto or None, cuerpo_original

    return None, None, texto


def extraer_direccion(remitente: str | None) -> str:
    """Aísla la dirección de un remitente con la forma «Nombre <buzón@dominio>»."""
    if not remitente:
        return ""
    coincidencia = re.search(r"<([^<>]+@[^<>]+)>", remitente)
    if coincidencia:
        return coincidencia.group(1).strip().lower()
    coincidencia = re.search(r"[\w.+-]+@[\w.-]+\.\w+", remitente)
    return coincidencia.group(0).strip().lower() if coincidencia else ""
