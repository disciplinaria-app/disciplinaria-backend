"""
Agente 1 — FORMA
Cubre: CEDIA-007 (ortografía/tildes), CEDIA-008 (concordancia), CEDIA-010 (puntuación),
       CEDIA-011 (espaciado), CEDIA-017 (signos sin cerrar), CEDIA-018 (redundancias/
       repetición morfológica) + M19 patrones 1 y 2 (número sin sustantivo, sustantivo
       sin número).

Fuentes combinadas (en paralelo):
  1. LLM (OpenRouter/Claude) — criterios CEDIA específicos del derecho disciplinario
  2. LanguageTool Premium    — ortografía, gramática y puntuación de cobertura amplia

Los hallazgos de ambas fuentes se fusionan y deduplicam antes de retornar.
"""

import asyncio
import re
import httpx

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error, llamar_por_chunks
from config import LT_USERNAME, LT_API_KEY
from models.schemas import Hallazgo, ResultadoAgente

# ── Configuración ─────────────────────────────────────────────────────────────

LT_ENDPOINT  = "https://api.languagetool.org/v2/check"
LT_TIMEOUT   = httpx.Timeout(30.0, connect=10.0)
LT_MAX_CHARS = 40_000   # Premium soporta textos largos
LT_MAX_MATCHES = 10     # cap para no saturar los hallazgos

# Mapeo categoría LT → módulo CEDIA y severidad
_CAT_MAP = {
    "TYPOS":        ("Ortografía",             "alta"),
    "GRAMMAR":      ("Gramática/Concordancia",  "alta"),
    "PUNCTUATION":  ("CEDIA-007",               "media"),
    "TYPOGRAPHY":   ("Tipografía",              "baja"),
    "STYLE":        ("CEDIA-018",               "baja"),
    "REDUNDANCY":   ("CEDIA-018",               "baja"),
}
_NIVEL = {"alta": 3, "media": 2, "baja": 1}

# Reglas LT que no aportan valor en textos jurídicos (falsos positivos frecuentes)
_REGLAS_IGNORADAS = {
    "WHITESPACE_RULE",
    "UNPAIRED_BRACKETS",   # LT detecta bien, pero lo cubre CEDIA-017 del LLM
    "ES_QUESTION_MARK",    # textos legales raramente usan interrogación
}

# ── LanguageTool ──────────────────────────────────────────────────────────────

async def _consultar_languagetool(texto: str) -> list[dict]:
    """
    Llama a LanguageTool Premium y convierte los matches al formato
    dict compatible con _construir_hallazgos() de base_agent.

    Retorna lista vacía si LT no está configurado o falla.
    """
    if not LT_USERNAME or not LT_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=LT_TIMEOUT) as client:
            resp = await client.post(
                LT_ENDPOINT,
                data={
                    "text":     texto[:LT_MAX_CHARS],
                    "language": "es",
                    "username": LT_USERNAME,
                    "apiKey":   LT_API_KEY,
                    "level":    "picky",
                },
            )
            resp.raise_for_status()
            matches = resp.json().get("matches", [])
    except Exception:
        return []   # degradación graceful: LT falla → solo CEDIA

    hallazgos = []
    for m in matches:
        rule_id  = m.get("rule", {}).get("id", "")
        if rule_id in _REGLAS_IGNORADAS:
            continue

        cat_id   = m.get("rule", {}).get("category", {}).get("id", "")
        modulo, severidad = _CAT_MAP.get(cat_id, ("LT", "baja"))

        # Texto exacto del error en su contexto
        ctx    = m.get("context", {})
        ctx_txt = ctx.get("text", "")
        o, l   = ctx.get("offset", 0), ctx.get("length", 0)
        ubicacion = ctx_txt[o : o + l].strip() or ctx_txt.strip()

        # Primera sugerencia disponible
        replacements = m.get("replacements", [])
        correccion   = replacements[0]["value"] if replacements else ""

        hallazgos.append({
            "modulo":        modulo,
            "ubicacion":     ubicacion[:80],
            "error":         m.get("message", ""),
            "justificacion": m.get("rule", {}).get("description", "Regla LanguageTool"),
            "correccion":    correccion,
            "severidad":     severidad,
            # Posición exacta en el texto plano enviado a LT — permite
            # localizar el párrafo con precisión absoluta en track_changes.py
            "lt_offset":     m.get("offset"),
            "lt_length":     m.get("length"),
        })

        if len(hallazgos) >= LT_MAX_MATCHES:
            break

    return hallazgos


def _deduplicar(cedia: list[dict], lt: list[dict]) -> list[dict]:
    """
    Elimina hallazgos de LT que ya están cubiertos por CEDIA (misma ubicacion).
    Prioriza CEDIA sobre LT en caso de solapamiento.
    """
    ubicaciones_cedia = {h["ubicacion"].lower().strip() for h in cedia}
    lt_nuevos = [
        h for h in lt
        if h["ubicacion"].lower().strip() not in ubicaciones_cedia
    ]
    return cedia + lt_nuevos


# ── Análisis determinista de folios (CEDIA-012) ───────────────────────────────

_RE_MENTE  = re.compile(r"\b\w+mente\b", re.IGNORECASE)
_RE_GERUND = re.compile(r"\b\w+[aáe]ndo\b", re.IGNORECASE)   # -ando / -endo
_PALABRAS_POR_FOLIO = 300


def _analizar_folios(texto: str) -> list[dict]:
    """
    Divide el texto en folios virtuales (~300 palabras) y detecta:
    - Más de 1 adverbio en -mente por folio  (CEDIA-012, severidad media)
    - Más de 1 gerundio por folio            (CEDIA-005, severidad baja)

    Retorna lista de hallazgos en formato dict compatible con _deduplicar().
    Esta función es determinista: no usa LLM ni APIs externas.
    """
    palabras = texto.split()
    hallazgos: list[dict] = []
    folio = 1

    for inicio in range(0, len(palabras), _PALABRAS_POR_FOLIO):
        chunk = " ".join(palabras[inicio : inicio + _PALABRAS_POR_FOLIO])

        adverbios = _RE_MENTE.findall(chunk)
        if len(adverbios) > 1:
            primeros = ", ".join(adverbios[:3])
            hallazgos.append({
                "modulo":        "CEDIA-012",
                "ubicacion":     primeros[:80],
                "error":         (
                    f"Folio {folio}: {len(adverbios)} adverbios en -mente "
                    f"({primeros}). Máximo permitido: 1 por folio."
                ),
                "justificacion": "CEDIA-012: máximo 1 adverbio en -mente por página (≈300 palabras).",
                "correccion":    "Reemplazar los adverbios en -mente adicionales por construcciones con 'con + sustantivo'.",
                "severidad":     "media",
            })

        gerundios = _RE_GERUND.findall(chunk)
        if len(gerundios) > 1:
            primeros_g = ", ".join(gerundios[:3])
            hallazgos.append({
                "modulo":        "CEDIA-005",
                "ubicacion":     primeros_g[:80],
                "error":         (
                    f"Folio {folio}: {len(gerundios)} gerundios "
                    f"({primeros_g}). Máximo recomendado: 1 por folio."
                ),
                "justificacion": "CEDIA-005: saturación de gerundios debilita el registro jurídico-forense.",
                "correccion":    "Sustituir los gerundios adicionales por verbos conjugados o cláusulas de infinitivo.",
                "severidad":     "baja",
            })

        folio += 1

    return hallazgos


# ── Prompt CEDIA ──────────────────────────────────────────────────────────────

SYSTEM = """Eres CEDIA-FORMA, corrector especializado en documentos jurídicos disciplinarios colombianos.
Tu misión es detectar exclusivamente errores de escritura objetivos y verificables según RAE 2010.
Aplica el principio de duda razonable: si el texto puede leerse como correcto, no lo reportes.
NO analices el contenido jurídico. Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

CRITERIOS DE ANÁLISIS — detecta solo errores verificablemente incorrectos:

CEDIA-007 · ORTOGRAFÍA Y TILDES (M1a, M1b, M1c, M1d):
- Palabras mal escritas (letras omitidas, intercambiadas, adicionales)
- Tildes obligatorias ausentes: verbos en pretérito (evidenció, ordenó, resolvió, concluyó,
  señaló, manifestó, consideró, advirtió, profirió, absolvió); esdrújulas (jurídico, técnico,
  artículo, número, específico); tildes diacríticas (él/el, tú/tu, más/mas, sí/si, aún/aun)
- Tildes incorrectas en adjetivos: "previo", "continuo" NO llevan tilde
- Homófonos en contexto jurídico: callo/cayó, haber/a ver, interpuso/impuso
- Régimen preposicional: "de acuerdo con" (no "a"), "en razón de" (no "a"),
  "respecto de" (no "a"), "acorde con" (no "a")
- Dequeísmo: "consideró de que" → "consideró que"; queísmo: "se percató que" → "se percató de que"
- Inserción espuria de preposición: "proceso de disciplinario" → "proceso disciplinario"

CEDIA-008 · CONCORDANCIA (M2a-M2e):
- Concordancia nominal de género: "las pruebas aportados" → "aportadas"
- Concordancia nominal de número: "las decisión" → "la decisión"
- Concordancia verbal: sujeto plural con verbo singular ("los elementos probatorios demuestra")
- EXCEPCIONES que NO son error: sujeto colectivo singular ("la Sala considera"), pasiva refleja

CEDIA-008-G · CONCORDANCIA GÉNERO-NOMBRE PROPIO (severidad ALTA):
Detectar cuando el artículo + sustantivo de rol tiene género opuesto al del nombre propio
que le sigue en el mismo párrafo.
  - Términos FEMENINOS de rol: 'la abogada', 'la disciplinada', 'la investigada',
    'la quejosa', 'la defensora', 'la togada'
  - Términos MASCULINOS de rol: 'el abogado', 'el disciplinado', 'el investigado',
    'el quejoso', 'el defensor', 'el togado'
  - Indicios de nombre masculino: CHRISTIAN, CARLOS, JORGE, LUIS, ANDRÉS, GABRIEL,
    RAFAEL, GERARDO, RODRIGO, MANUEL, JUAN, PEDRO y similares
  - Indicios de nombre femenino: MARÍA, ANA, LAURA, CAROLINA, ANDREA, CAMILA, DIANA,
    PATRICIA, CLAUDIA, JESSICA y similares
  - Ejemplo de error: 'la abogada CHRISTIAN GERARDO MARTÍNEZ' → 'el abogado CHRISTIAN GERARDO MARTÍNEZ'
  - Ejemplo de error: 'el disciplinado MARÍA CAMILA TORRES' → 'la disciplinada MARÍA CAMILA TORRES'
  - Severidad ALTA: la discordancia afecta la identificación del sujeto disciplinado

CEDIA-010 · PUNTUACIÓN RAE 2010 — solo reglas inequívocas:
- Coma entre sujeto y predicado: NUNCA ("el abogado[,] incurrió")
- Coma antes de "que" sustantivo: NUNCA ("concluyó[,] que no podía")
- Vocativo siempre entre comas: "Señor defensor[,] tiene el uso"
- Inciso explicativo siempre entre comas
- Coma antes de conjunción en enumeración simple: NUNCA

CEDIA-011 · ESPACIADO:
- Dobles espacios entre palabras
- Espacio antes de signo de puntuación
- Falta espacio tras punto final de oración
- Espaciado incorrecto en fechas y referencias: "31de" → "31 de", "artículo28" → "artículo 28"

CEDIA-017 · SIGNOS SIN CERRAR (severidad ALTA):
- Paréntesis abierto sin cerrar
- Comillas abiertas sin cerrar (especialmente en citas largas de audiencias)
- Guión de inciso abierto sin cerrar
- Corchete abierto sin cerrar

CEDIA-018 · REDUNDANCIAS Y REPETICIÓN MORFOLÓGICA (M5a, M5g):
- Repetición morfológica por raíz léxica en mismo párrafo:
  contactar/contactarlo (raíz CONTACT), respondió/respondiendo (raíz RESPOND)
- Redundancias fijas: "el día lunes" → "el lunes", "resultado final" → "resultado",
  "regresar de nuevo" → "regresar", "en horas de la mañana" → hora específica

M19 PATRONES 1 Y 2 · OMISIÓN DE SUSTANTIVOS O NÚMEROS:
- Patrón 1: número sin sustantivo referencial ("en el 37 de la Ley" → "en el artículo 37")
- Patrón 2: sustantivo sin número ("el artículo de la Ley 1123" sin especificar cuál)

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: afecta validez jurídica del acto o genera nulidad/recurso exitoso
- Media: debilita argumentación o genera ambigüedad interpretable por la defensa
- Baja: error de forma corregible sin impacto en el fondo

REGLAS OBLIGATORIAS PARA EL CAMPO "correccion":
  1. RAÍZ MORFOLÓGICA: la corrección NO puede contener la misma raíz léxica
     que la palabra errónea que reemplaza. Si la única corrección posible
     comparte raíz, propón una construcción alternativa sin esa raíz.
     Ejemplo: "contactar/contactarlo" → no corregir como "hacer contacto" (raíz
     CONTACT presente) → corregir como "comunicarse con él".
  2. ADVERBIOS EN -mente: si el párrafo del fragmento ya contiene un adverbio
     en -mente, la corrección NO puede introducir otro adverbio en -mente.
     Usa en su lugar una construcción adverbial (con + sustantivo abstracto).
     Ejemplo: párrafo tiene "jurídicamente" → corrección propuesta "claramente"
     → cambiar a "con claridad".
  3. REDUNDANCIA TEMPORAL: "el día lunes" → corregir SOLO como "el lunes"
     (no como "el día 17" ni ninguna variante que agregue información nueva).
     "en horas de la mañana" → reemplazar por la hora específica si está
     disponible en el texto; si no → "en la mañana".

Responde con este JSON exacto (máximo 12 hallazgos):
```json
{{
  "puntaje": <0-100; 100=sin errores de forma>,
  "resumen": "<párrafo conciso sobre el estado formal del documento>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-007|CEDIA-008|CEDIA-010|CEDIA-011|CEDIA-017|CEDIA-018|M19>",
      "ubicacion": "<cita textual breve del fragmento, máx 80 caracteres>",
      "error": "<descripción precisa del error>",
      "justificacion": "<regla RAE o criterio CEDIA que se incumple>",
      "correccion": "<texto corregido listo para usar>",
      "severidad": "<alta|media|baja>"
    }}
  ],
  "fortalezas": ["<aspectos de forma bien logrados>"],
  "recomendaciones": ["<correcciones prioritarias>"]
}}
```"""


# ── Punto de entrada ──────────────────────────────────────────────────────────

async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    # LT corre en paralelo mientras el LLM procesa los chunks secuencialmente
    lt_task = asyncio.create_task(_consultar_languagetool(texto))
    folio_hallazgos = _analizar_folios(texto)

    try:
        datos = await llamar_por_chunks(SYSTEM, lambda chunk: PLANTILLA.format(texto=chunk), texto=texto)
        lt_hallazgos = await lt_task
    except Exception as exc:
        return construir_resultado_error("FORMA", exc)

    cedia_hallazgos = datos.get("hallazgos", [])
    combinados = _deduplicar(cedia_hallazgos, lt_hallazgos)
    combinados = _deduplicar(combinados, folio_hallazgos)
    datos["hallazgos"] = combinados

    return construir_resultado("FORMA", datos)
