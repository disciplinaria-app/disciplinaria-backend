"""
Cotejo determinista de la correspondencia recibida.

Confronta la entidad que suscribe el documento y los radicados que este cita
contra los que el usuario esperaba, sin intervención del modelo de lenguaje.
El modelo interpreta; este módulo constata. Las alertas que nacen aquí son
reproducibles y auditables, de modo que el hallazgo no depende de la lectura
probabilística del agente.

Criterio de diseño: ante la duda, alertar. En un sistema de triage un falso
positivo cuesta una verificación de treinta segundos; un falso negativo cuesta
advertir el error cuando ya precluyó la oportunidad de corregirlo.
"""

import re
import unicodedata

from models.schemas import Alerta, ResultadoCotejo

# --- Códigos de alerta -----------------------------------------------------

CODIGOS_ALERTA = {
    "ENTIDAD_DISTINTA": "La entidad que responde no es aquella a la que se dirigió la comunicación",
    "DEVOLUCION_POR_COMPETENCIA": "La entidad manifiesta no ser competente o advierte un envío errado",
    "RADICADO_NO_COINCIDE": "El radicado citado no corresponde al de la comunicación remitida",
    "TERMINO_CORRIENDO": "El documento fija o activa un término",
    "REQUIERE_RESPUESTA": "El documento exige una respuesta o actuación del destinatario",
    "DOCUMENTO_ILEGIBLE": "No fue posible recuperar el texto del adjunto",
    "DOCUMENTO_INCOMPLETO": "El documento parece incompleto o remite a anexos ausentes",
    "SIN_SUSCRIPCION": "El documento no aparece suscrito por funcionario identificable",
    "SIN_ADJUNTO_ANUNCIADO": "El correo anuncia un adjunto que no fue recibido",
    "DATO_RESERVADO": "El documento parece contener información sujeta a reserva o datos personales sensibles",
}

# --- Normalización ---------------------------------------------------------

# Formas societarias y descriptores genéricos que no identifican a la entidad.
_RUIDO_ENTIDAD = (
    "en liquidacion",
    "compania de seguros",
    "cia de seguros",
    "sociedad fiduciaria",
    "s a s",
    "sas",
    "s a",
    "ltda",
    "e s p",
    "esp",
    "e i c e",
    "eice",
    "scs",
    "sca",
)

_PALABRAS_VACIAS = {
    "la", "el", "los", "las", "un", "una", "de", "del", "y", "e", "al",
    "sociedad", "entidad", "empresa", "compania", "cia", "grupo",
}

# El orden importa: los patrones con prefijo institucional van primero para que
# el literal extraído conserve la sigla («CNDJ-2025-0412» y no solo «2025-0412»).
# La deduplicación posterior, que opera sobre los dígitos, descarta la forma corta.
_PATRONES_RADICADO = (
    # Prefijo alfabético institucional: CNDJ-2025-0412, PQRSD 2025-123
    re.compile(r"\b[A-ZÁÉÍÓÚÑ]{2,10}[-\s]?(?:19|20)?\d{2,4}[-/]\d{3,8}\b"),
    # Año seguido de consecutivo: 2025-0412, 2025 00412
    re.compile(r"\b(?:19|20)\d{2}[-/ ]\d{3,8}\b"),
    # Consecutivo seguido de año: 0412-2025
    re.compile(r"\b\d{3,8}[-/](?:19|20)\d{2}\b"),
    # Radicado numérico extenso de la Rama Judicial y entidades
    re.compile(r"\b\d{8,25}\b"),
)

# Giros con que una entidad anuncia un adjunto.
_ANUNCIO_ADJUNTO = re.compile(
    r"\b(adjunt\w+|anex\w+|se\s+remite\s+(el|la|los|las)\s+(archiv|document|oficio)\w*"
    r"|en\s+el\s+archivo\s+adjunto)\b",
    re.IGNORECASE,
)


def despojar_acentos(texto: str) -> str:
    """Suprime diacríticos conservando la letra base (ñ incluida como n)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_entidad(nombre: str | None) -> str:
    """
    Reduce el nombre de una entidad a su núcleo identificador.

    Suprime diacríticos, puntuación, formas societarias y descriptores
    genéricos, de modo que «La Previsora S.A. Compañía de Seguros» y
    «PREVISORA» converjan, sin que ello arrastre a «Fiduprevisora», que
    conserva un núcleo distinto.
    """
    if not nombre:
        return ""
    texto = despojar_acentos(nombre).lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    for ruido in _RUIDO_ENTIDAD:
        texto = re.sub(rf"\b{re.escape(ruido)}\b", " ", texto)
    palabras = [p for p in texto.split() if p and p not in _PALABRAS_VACIAS]
    return " ".join(palabras)


def tokens_entidad(nombre: str | None) -> frozenset[str]:
    """Núcleos léxicos del nombre, descartando partículas de una sola letra."""
    return frozenset(p for p in normalizar_entidad(nombre).split() if len(p) > 1)


def comparar_entidades(esperada: str | None, recibida: str | None) -> str:
    """
    Compara dos denominaciones y devuelve COINCIDE, DIFIERE o INDETERMINADO.

    La comparación opera sobre núcleos léxicos completos y nunca por
    subcadenas: «previsora» es subcadena de «fiduprevisora», pero son
    entidades distintas, y confundirlas es precisamente el error que este
    cotejo debe descubrir.
    """
    nucleo_esperado = tokens_entidad(esperada)
    nucleo_recibido = tokens_entidad(recibida)
    if not nucleo_esperado or not nucleo_recibido:
        return "INDETERMINADO"
    if nucleo_esperado == nucleo_recibido:
        return "COINCIDE"
    # Una denominación abreviada frente a la razón social completa.
    if nucleo_esperado <= nucleo_recibido or nucleo_recibido <= nucleo_esperado:
        return "COINCIDE"
    return "DIFIERE"


def normalizar_radicado(radicado: str | None) -> str:
    """Conserva solo los dígitos, que son lo estable entre formatos de cita."""
    if not radicado:
        return ""
    return re.sub(r"\D", "", radicado)


def extraer_radicados(texto: str, limite: int = 40) -> list[str]:
    """
    Extrae candidatos a radicado del texto, preservando el orden de aparición.

    Devuelve los literales tal como figuran en el documento; la comparación
    posterior se hace sobre su forma numérica.
    """
    hallados: list[str] = []
    vistos: set[str] = set()
    for patron in _PATRONES_RADICADO:
        for coincidencia in patron.finditer(texto):
            literal = coincidencia.group(0).strip()
            clave = normalizar_radicado(literal)
            # Un número de menos de cuatro dígitos no identifica un radicado.
            if len(clave) < 4 or clave in vistos:
                continue
            vistos.add(clave)
            hallados.append(literal)
            if len(hallados) >= limite:
                return hallados
    return hallados


def radicados_equivalentes(uno: str, otro: str) -> bool:
    """
    Dos citas designan el mismo radicado si sus dígitos coinciden, o si la más
    corta es el consecutivo final de la más larga (p. ej. «0412» en
    «CNDJ-2025-0412»), con al menos cuatro dígitos de coincidencia.
    """
    a, b = normalizar_radicado(uno), normalizar_radicado(otro)
    if not a or not b:
        return False
    if a == b:
        return True
    corto, largo = (a, b) if len(a) <= len(b) else (b, a)
    return len(corto) >= 4 and largo.endswith(corto)


def cotejar(
    entidad_esperada: str | None,
    entidad_recibida: str | None,
    radicado_enviado: str | None,
    radicados_hallados: list[str],
) -> ResultadoCotejo:
    """Construye el resultado del cotejo determinista."""
    estado_entidad = comparar_entidades(entidad_esperada, entidad_recibida)

    esperados = [radicado_enviado] if radicado_enviado else []
    if not radicado_enviado:
        estado_radicado = "INDETERMINADO"
    elif not radicados_hallados:
        estado_radicado = "INDETERMINADO"
    elif any(radicados_equivalentes(radicado_enviado, h) for h in radicados_hallados):
        estado_radicado = "COINCIDE"
    else:
        estado_radicado = "NO_COINCIDE"

    return ResultadoCotejo(
        entidad_estado=estado_entidad,
        entidad_esperada_normalizada=normalizar_entidad(entidad_esperada) or None,
        entidad_recibida_normalizada=normalizar_entidad(entidad_recibida) or None,
        radicado_estado=estado_radicado,
        radicados_esperados=[r for r in esperados if r],
        radicados_hallados=radicados_hallados,
    )


def alertas_deterministas(
    resultado: ResultadoCotejo,
    entidad_esperada: str | None,
    entidad_recibida: str | None,
    cuerpo: str,
    numero_adjuntos: int,
    documentos_ilegibles: list[str],
) -> list[Alerta]:
    """Alertas que se sostienen sin recurrir al modelo de lenguaje."""
    alertas: list[Alerta] = []

    if resultado.entidad_estado == "DIFIERE":
        alertas.append(
            Alerta(
                codigo="ENTIDAD_DISTINTA",
                descripcion=(
                    f"La comunicación se dirigió a «{entidad_esperada}», pero el documento "
                    f"recibido lo suscribe «{entidad_recibida}». Verifique si hubo confusión "
                    "de destinatario antes de darle trámite."
                ),
                severidad="ALTA",
                origen="COTEJO",
            )
        )

    if resultado.radicado_estado == "NO_COINCIDE":
        alertas.append(
            Alerta(
                codigo="RADICADO_NO_COINCIDE",
                descripcion=(
                    f"Se remitió el radicado «{resultado.radicados_esperados[0]}», pero el "
                    f"documento cita {', '.join(resultado.radicados_hallados[:5])}. "
                    "La respuesta podría corresponder a otra actuación."
                ),
                severidad="MEDIA",
                origen="COTEJO",
            )
        )

    if numero_adjuntos == 0 and _ANUNCIO_ADJUNTO.search(cuerpo or ""):
        alertas.append(
            Alerta(
                codigo="SIN_ADJUNTO_ANUNCIADO",
                descripcion=(
                    "El cuerpo del correo anuncia un documento adjunto, pero no se recibió "
                    "ningún archivo. Solicite la remisión del anexo."
                ),
                severidad="MEDIA",
                origen="COTEJO",
            )
        )

    if documentos_ilegibles:
        alertas.append(
            Alerta(
                codigo="DOCUMENTO_ILEGIBLE",
                descripcion=(
                    "No fue posible recuperar el texto de "
                    f"{', '.join(documentos_ilegibles)}. La ficha no cubre su contenido: "
                    "requiere lectura directa."
                ),
                severidad="ALTA",
                origen="COTEJO",
            )
        )

    return alertas
