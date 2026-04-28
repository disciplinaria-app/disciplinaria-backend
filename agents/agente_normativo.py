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
from .base_agent import llamar_por_chunks, construir_resultado, construir_resultado_error
from .supabase_utils import verificar_articulo, buscar_articulos
from models.schemas import ResultadoAgente
from config import NORMAS

SYSTEM = """Eres CEDIA-NORMATIVO, experto verificador de citas normativas en documentos
disciplinarios colombianos. Operas con tres subagentes:
SA5.1 — Formato de citas: estructura canónica Artículo N°, Ley XXXX de YYYY.
SA5.2 — Nota al pie: toda cita de artículo debe tener referencia de pie de página.
SA5.3 — Verificación vectorial: contrasta el contenido invocado con el texto real.
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

SA5.1 — FORMATO DE CITAS NORMATIVAS (CEDIA-FMT)
Estructura canónica obligatoria:
  Artículo N°[, numeral N°][, literal x)][, inciso N°][, parágrafo N°] de la Ley XXXX de YYYY
Errores a detectar y corregir:
- "ley" en minúscula antes de número → "Ley"
- "articulo" sin tilde → "Artículo"
- Número sin signo de grado: "artículo 28" → "artículo 28°"
- "numeral 3" sin grado → "numeral 3°"
- Abreviaturas en texto formal: "art.", "num.", "lit.", "par." → forma completa
- "literal a" sin paréntesis → "literal a)"
- "Ley 1123" sin año → "Ley 1123 de 2007" (1952→2019, 734→2002)
Severidad: BAJA (error de forma).

SA5.2 — AUSENCIA DE NOTA AL PIE (CEDIA-FMT)
Cuando el documento cite un artículo en el cuerpo del texto sin nota al pie
o referencia bibliográfica correspondiente → hallazgo de severidad MEDIA.
Indicador de nota al pie: [1], (1), superíndice numérico, o "Véase pie de página".
Si ninguno aparece junto a la cita → "Cita normativa sin nota al pie —
incluir texto del artículo citado o referencia al pie."

SA5.3 — VERIFICACIÓN VECTORIAL (Supabase)
Usando el contexto de la base normativa disponible arriba:
CEDIA-016 — ESTRUCTURA NORMATIVA LEY 1123/2007 (ALTA SEVERIDAD):
  Art. 28 = DEBERES PROFESIONALES (21 deberes del abogado)
  Art. 29 = INCOMPATIBILIDADES — si se cita como fuente de un deber → ALTA
  Art. 30-33 = Deberes con la administración de justicia
  Art. 34 = Prohibiciones (conflicto de intereses literal e)
  Art. 37 = Faltas gravísimas
  Art. 40 = Sanciones (censura, multa, suspensión, exclusión)
  Art. 73 = Suspensión (1 a 12 meses) — NO el art. 43
  Ley 1123 NO tiene faltas gravísimas/graves/leves → ERROR ALTA si aparecen
  Término exclusivo Ley 1123: QUEJOSO (nunca denunciante o demandante)

Artículo inexistente o numeración incorrecta:
  - Número de artículo que no existe en la ley citada → ALTA
  - Transposición: el deber está en art. 28 pero se cita art. 29 → ALTA
  - Usar la base normativa de Supabase para verificar; si no disponible → MEDIA
    con nota "artículo no verificado en la base normativa"

Contenido invocado ≠ texto real:
  - El artículo existe pero su contenido no corresponde a lo que se invoca
  - Ejemplo: citar art. 37 para "debida diligencia" cuando ese artículo regula
    otro supuesto — verificar contra Supabase → MEDIA

CEDIA-003 — TERMINOLOGÍA LEY 1123 (ALTA SEVERIDAD):
Bajo Ley 1123/2007: QUEJOSO (nunca "denunciante", "demandante" ni "víctima").
Bajo Ley 1952/2019: "quejoso" también es correcto.
Si bajo Ley 1123 se usa "denunciante" → error ALTA que afecta la legitimación procesal.

CEDIA-004 — CARGA LABORAL DEL DEFENSOR PÚBLICO (ALTA SEVERIDAD):
La carga laboral del defensor público NO exime de responsabilidad disciplinaria.
Si el documento acepta la carga laboral como circunstancia atenuante o eximente → ALTA.
Fundamento: Art. 1° Ley 941/2005 — la defensa pública debe ser integral,
ininterrumpida, técnica y competente, independientemente de la carga de trabajo.

CEDIA-014 — DEFENSA TÉCNICA — ESTÁNDARES MÍNIMOS LEY 941/2005 (ALTA SEVERIDAD):
Verificar que la providencia evalúa si el defensor cumplió con los estándares
mínimos de la Ley 941/2005 antes de calificar la conducta disciplinada:
  — ¿Se analizó si la defensa fue integral e ininterrumpida?
  — ¿Se verificó si el defensor asistió a todas las diligencias?
  — ¿Se evaluó si la estrategia fue técnicamente fundamentada?
Si la providencia califica la conducta sin este análisis previo → ALTA.

M18 — CITAS JURISPRUDENCIALES INCOMPLETAS (MEDIA SEVERIDAD):
- Sentencias sin número de radicado, fecha Y corporación (los tres son obligatorios)
- "La jurisprudencia ha establecido reiteradamente" sin cita específica → MEDIA
- "Como lo ha dicho la Corte Constitucional" sin número de sentencia → MEDIA

M19 PATRÓN 3 — VERBO DE IMPUTACIÓN SIN COMPLEMENTO NORMATIVO (MEDIA SEVERIDAD):
- "incurrió en lo previsto en" sin el sustantivo rector que complete el sentido
- "sancionado según" sin indicar el artículo concreto
- Verbo de imputación (incurrir, tipificar, subsumirse) sin complemento normativo completo

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: artículo inexistente, norma equivocada para el sujeto, confusión art. 28/29
        Ley 1123, o providencia sin análisis de defensa técnica → nulidad o recurso exitoso
- Media: contenido invocado distinto al real, cita incompleta, ausencia de nota al pie
- Baja: error de formato de cita sin impacto en el fondo

REGLA OBLIGATORIA CAMPO "correccion":
Si el párrafo ya contiene un adverbio en -mente, la corrección NO puede introducir otro.
Usar "con + sustantivo abstracto": "normativamente" → "de forma normativa".

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
    fmt_hallazgos = _verificar_formato_citas_normativas(texto)

    try:
        datos = await llamar_por_chunks(
            SYSTEM,
            lambda chunk: plantilla.format(texto=chunk),
            texto=texto,
            max_tokens=4000,
        )
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
