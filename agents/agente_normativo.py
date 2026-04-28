"""
Agente 5 — NORMATIVO
Cubre: CEDIA-003 (norma sin verificar contenido real), CEDIA-004 (artículo
       inexistente), CEDIA-014 (error de favorabilidad), CEDIA-016 (art. 29
       Ley 1123 = INCOMPATIBILIDADES, no deberes) + M18 (citas jurisprudenciales
       incompletas), M19 patrón 3 (verbo sin objeto directo — "incurrió en
       previsto en..." sin sustantivo rector).

Usa búsqueda vectorial en Supabase para verificar el texto real de los artículos
citados. Si Supabase no está configurado, opera en modo solo-LLM.
"""

import re
from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from .supabase_utils import verificar_articulo, buscar_articulos
from models.schemas import ResultadoAgente
from config import NORMAS

SYSTEM = """Eres CEDIA-NORMATIVO, experto verificador de citas normativas en documentos
disciplinarios colombianos. Validas que cada artículo citado EXISTA en la ley indicada,
que el contenido invocado CORRESPONDA al texto real, y que la norma aplicada sea la
CORRECTA para el tipo de sujeto disciplinado.
REGLA ABSOLUTA: jamás inventes el contenido de un artículo. Si no puedes verificarlo,
reporta "artículo no verificado" como hallazgo de severidad media.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

_PATRON_ARTICULO = re.compile(
    r"art[íi]culo\s+(\d+[°o]?[a-z]?)\s*(?:de\s+(?:la\s+)?[Ll]ey\s+(\d+))?",
    re.IGNORECASE,
)

_NORMA_CANONICA = {
    "ley_1123": "1123", "1123": "1123",
    "ley_1952": "1952", "1952": "1952",
    "734":      "734",
}

_LEYES_CON_AÑO = {"1123": "2007", "1952": "2019", "734": "2002", "270": "1996", "906": "2004"}
_RE_CITA_LEY_MIN = re.compile(r'\bley\s+\d{3,4}\b')
_RE_ARTICULO_SIN_TILDE = re.compile(r'\barticulo\b')
_RE_ARTICULO_SIN_GRADO = re.compile(r'\b(art[íi]culo)\s+(\d+)(?![°o\d])', re.IGNORECASE)
_RE_NUMERAL_SIN_GRADO = re.compile(r'\bnumeral\s+(\d+)(?![°o\d])', re.IGNORECASE)
_RE_ABREVIATURA_CITA = re.compile(r'\b(art|num|lit|par)\.\s*\d+', re.IGNORECASE)
_RE_LITERAL_SIN_PAREN = re.compile(r'\bliteral\s+([a-zA-Z])(?!\))', re.IGNORECASE)
_RE_LEY_SIN_AÑO = re.compile(r'\bLey\s+(\d{3,4})(?!\s+de\s+\d{4})\b')


def _verificar_formato_citas_normativas(texto: str) -> list[dict]:
    """Detecta errores de formato en la estructura canónica de citas normativas."""
    muestra = texto[:8000]
    hallazgos: list[dict] = []

    for m in _RE_CITA_LEY_MIN.finditer(muestra):
        if m.group(0)[0].islower():
            ctx = muestra[max(0, m.start() - 10):m.end() + 10]
            hallazgos.append({
                "modulo": "CEDIA-FMT",
                "ubicacion": m.group(0)[:80],
                "error": f'"{m.group(0)}" — "ley" con minúscula inicial antes de número de ley',
                "justificacion": "Formato canónico de cita normativa: 'Ley XXXX de YYYY'",
                "correccion": m.group(0).replace("ley", "Ley", 1),
                "severidad": "baja",
            })

    for m in _RE_ARTICULO_SIN_TILDE.finditer(muestra):
        ctx = muestra[max(0, m.start() - 5):m.end() + 25]
        hallazgos.append({
            "modulo": "CEDIA-FMT",
            "ubicacion": ctx[:80],
            "error": '"articulo" sin tilde diacrítica',
            "justificacion": "Ortografía y formato canónico: 'Artículo'",
            "correccion": "Artículo",
            "severidad": "baja",
        })

    for m in _RE_ARTICULO_SIN_GRADO.finditer(muestra):
        art_word, num = m.group(1), m.group(2)
        hallazgos.append({
            "modulo": "CEDIA-FMT",
            "ubicacion": m.group(0)[:80],
            "error": f'"{m.group(0)}" — número de artículo sin signo de grado (°)',
            "justificacion": "Formato canónico: 'Artículo N°'",
            "correccion": f"{art_word} {num}°",
            "severidad": "baja",
        })

    for m in _RE_NUMERAL_SIN_GRADO.finditer(muestra):
        num = m.group(1)
        hallazgos.append({
            "modulo": "CEDIA-FMT",
            "ubicacion": m.group(0)[:80],
            "error": f'"numeral {num}" — falta signo de grado (°)',
            "justificacion": "Formato canónico: 'numeral N°'",
            "correccion": f"numeral {num}°",
            "severidad": "baja",
        })

    expandido = {"art": "Artículo", "num": "numeral", "lit": "literal", "par": "parágrafo"}
    for m in _RE_ABREVIATURA_CITA.finditer(muestra):
        abrev = m.group(1).lower()
        hallazgos.append({
            "modulo": "CEDIA-FMT",
            "ubicacion": m.group(0)[:80],
            "error": f'Abreviatura "{m.group(0)}" en texto formal',
            "justificacion": "En providencias se escriben las formas completas, no abreviaturas",
            "correccion": m.group(0).replace(m.group(1), expandido.get(abrev, m.group(1)), 1),
            "severidad": "baja",
        })

    for m in _RE_LITERAL_SIN_PAREN.finditer(muestra):
        letra = m.group(1)
        hallazgos.append({
            "modulo": "CEDIA-FMT",
            "ubicacion": m.group(0)[:80],
            "error": f'"literal {letra}" sin paréntesis de cierre',
            "justificacion": "Formato canónico: 'literal x)'",
            "correccion": f"literal {letra})",
            "severidad": "baja",
        })

    for m in _RE_LEY_SIN_AÑO.finditer(muestra):
        num_ley = m.group(1)
        anio = _LEYES_CON_AÑO.get(num_ley)
        if anio:
            hallazgos.append({
                "modulo": "CEDIA-FMT",
                "ubicacion": m.group(0)[:80],
                "error": f'"Ley {num_ley}" sin año de expedición',
                "justificacion": "Formato canónico: 'Ley XXXX de YYYY'",
                "correccion": f"Ley {num_ley} de {anio}",
                "severidad": "baja",
            })

    return hallazgos[:5]


async def _construir_contexto_supabase(texto: str, norma: str) -> str:
    """Extrae referencias normativas del texto y las verifica en Supabase."""
    ley = _NORMA_CANONICA.get(norma, norma)
    refs = _PATRON_ARTICULO.findall(texto[:8000])
    if not refs:
        return ""

    lineas = ["CONTENIDO REAL DE ARTÍCULOS SEGÚN BASE NORMATIVA SUPABASE:"]
    vistos = set()
    for num, ley_ref in refs[:10]:
        ley_buscar = ley_ref if ley_ref else ley
        clave = (num, ley_buscar)
        if clave in vistos:
            continue
        vistos.add(clave)

        art = await verificar_articulo(num, ley_buscar)
        if art:
            lineas.append(
                f"  Art. {art['numero_articulo']} Ley {ley_buscar}: "
                f"{art.get('titulo', '')} — {art.get('contenido', '')[:300]}"
            )
        else:
            lineas.append(f"  Art. {num} Ley {ley_buscar}: NO ENCONTRADO EN BASE NORMATIVA")

    return "\n".join(lineas) if len(lineas) > 1 else ""


def _plantilla(norma_nombre: str, contexto_supabase: str) -> str:
    supabase_bloque = (
        f"\nCONTEXTO VERIFICADO EN BASE NORMATIVA:\n{contexto_supabase}\n"
        if contexto_supabase
        else "\n[Base normativa no disponible — usar conocimiento propio con cautela]\n"
    )
    return f"""Analiza el siguiente documento jurídico disciplinario colombiano bajo la {norma_nombre}.
{supabase_bloque}
DOCUMENTO:
{{texto}}

CRITERIOS DE ANÁLISIS:

CEDIA-004 · ARTÍCULO INEXISTENTE O NUMERACIÓN INCORRECTA:
- Cita de artículo cuyo número no existe en la ley (error de alta severidad)
- Transposición de números: el deber está en art. 28 pero se cita el art. 29
- REGLA CRÍTICA CEDIA-016 · LEY 1123/2007:
  * Artículo 28 = DEBERES PROFESIONALES (21 deberes del abogado)
  * Artículo 29 = INCOMPATIBILIDADES (no deberes) — si se cita como fuente
    de un deber: ERROR DE ALTA SEVERIDAD
  * Artículos 30-39 = tipos de faltas disciplinarias
  * Artículo 40 = sanciones (censura, multa, suspensión, exclusión)
  * Artículo 73 = suspensión (1 a 12 meses) — no el art. 43
  * La Ley 1123 NO tiene faltas gravísimas/graves/leves (solo la Ley 1952/734)
  * Términos exclusivos Ley 1123: QUEJOSO, DEBERES PROFESIONALES, FALTAS ÉTICAS

CEDIA-003 · NORMA SIN VERIFICAR CONTENIDO REAL:
- El artículo existe pero su contenido no corresponde a lo que se invoca
- Ejemplo: citar art. 37 para "debida diligencia" cuando ese artículo regula
  otra materia
- Usar el contexto de Supabase para verificar; si no está disponible, alertar

CEDIA-014 · ERROR DE FAVORABILIDAD NORMATIVA:
- Para hechos anteriores al 29/06/2021: puede aplicarse Ley 734/2002
  (ultraactiva) si es más favorable; no es obligatorio aplicar Ley 1952
- Para hechos posteriores al 29/06/2021: aplica Ley 1952/2019
- Error: aplicar Ley 1952 retroactivamente a hechos anteriores sin análisis
  de favorabilidad
- Error: mezclar artículos de Ley 734 y Ley 1952 sin justificar la transición

M18 · CITAS JURISPRUDENCIALES INCOMPLETAS:
- Sentencias sin número de radicado, fecha O corporación
- "La jurisprudencia ha establecido reiteradamente" sin cita específica
- Artículos sin identificar la ley de origen

M19 PATRÓN 3 · VERBO SIN OBJETO DIRECTO:
- "incurrió en previsto en" sin el sustantivo rector que complete el sentido
- "sancionado según" sin indicar el artículo concreto
- Verbo de imputación sin complemento normativo completo

CEDIA-FMT · FORMATO DE CITAS NORMATIVAS (3A):
Estructura canónica obligatoria:
  Artículo N°[, numeral N°][, literal x)][, inciso N°][, parágrafo N°] de la Ley XXXX de YYYY
Errores a detectar:
- "ley" en minúscula antes de número → debe ser "Ley"
- "articulo" sin tilde → debe ser "Artículo"
- Número sin signo de grado: "artículo 28" → "artículo 28°"
- "numeral 3" sin grado → "numeral 3°"
- Abreviaturas en texto formal: "art.", "num.", "lit.", "par." → escribir completo
- "literal a" sin paréntesis → "literal a)"
- "Ley 1123" sin año → "Ley 1123 de 2007" (1952→2019, 734→2002)
Severidad: baja (error de forma sin impacto sustancial)

CEDIA-FMT · AUSENCIA DE NOTA AL PIE (3B):
- Cuando el texto cita un artículo en el cuerpo (ej. "Artículo 28° de la Ley 1123")
  pero no existe ninguna nota al pie o referencia bibliográfica correspondiente,
  alertar con severidad MEDIA — debilita la fundamentación documental del fallo.
- Indicador de nota al pie: superíndice numérico [1], (1) o texto "Véase pie de página"
  junto a la cita; ausencia de estos → hallazgo.

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: artículo inexistente, norma equivocada para el sujeto disciplinado,
        o confusión art. 28/29 Ley 1123 — generan nulidad o recurso exitoso
- Media: artículo existente pero invocado para materia incorrecta, o cita
         incompleta que debilita la fundamentación
- Baja: cita parcialmente incompleta corregible sin afectar el fondo

REGLA OBLIGATORIA PARA EL CAMPO "correccion":
Si la corrección propuesta introduce un adverbio en -mente y el párrafo del
fragmento ya contiene uno, usa en su lugar una construcción adverbial equivalente
(con + sustantivo abstracto). Ejemplo: párrafo tiene "normativamente" → corrección
no puede proponer "específicamente" → proponer "de forma específica".

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{{{
  "puntaje": <0-100; 100=aplicación normativa impecable>,
  "resumen": "<párrafo conciso sobre la corrección normativa del documento>",
  "hallazgos": [
    {{{{
      "modulo": "<CEDIA-003|CEDIA-004|CEDIA-014|CEDIA-016|CEDIA-FMT|M18|M19>",
      "ubicacion": "<cita textual breve del fragmento, máx 80 caracteres>",
      "error": "<descripción de la discrepancia normativa>",
      "justificacion": "<texto real del artículo según base normativa o criterio CEDIA>",
      "correccion": "<redacción correcta de la cita o artículo correcto a invocar>",
      "severidad": "<alta|media|baja>"
    }}}}
  ],
  "fortalezas": ["<aspectos normativos correctamente aplicados>"],
  "recomendaciones": ["<correcciones normativas prioritarias>"]
}}}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    norma_nombre = NORMAS.get(norma, norma)
    contexto_supabase = await _construir_contexto_supabase(texto, norma)
    plantilla = _plantilla(norma_nombre, contexto_supabase)
    prompt = plantilla.format(texto=texto[:8000])
    fmt_hallazgos = _verificar_formato_citas_normativas(texto)

    try:
        raw = await llamar_openrouter(SYSTEM, prompt, max_tokens=4000)
        datos = extraer_json_respuesta(raw)
        llm_hallazgos = datos.get("hallazgos", [])
        vistos = {h.get("ubicacion", "")[:60].lower() for h in llm_hallazgos}
        for fh in fmt_hallazgos:
            key = fh.get("ubicacion", "")[:60].lower()
            if key not in vistos:
                llm_hallazgos.append(fh)
                vistos.add(key)
        datos["hallazgos"] = llm_hallazgos[:10]
        return construir_resultado("NORMATIVO", datos)
    except Exception as exc:
        return construir_resultado_error("NORMATIVO", exc)
