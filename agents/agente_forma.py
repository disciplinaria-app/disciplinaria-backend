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
import httpx

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
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
            "modulo":       modulo,
            "ubicacion":    ubicacion[:80],
            "error":        m.get("message", ""),
            "justificacion": m.get("rule", {}).get("description", "Regla LanguageTool"),
            "correccion":   correccion,
            "severidad":    severidad,
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
    prompt = PLANTILLA.format(texto=texto[:8000])

    # Llamar LLM y LanguageTool en paralelo
    llm_task = llamar_openrouter(SYSTEM, prompt)
    lt_task  = _consultar_languagetool(texto)

    try:
        raw, lt_hallazgos = await asyncio.gather(llm_task, lt_task)
    except Exception as exc:
        return construir_resultado_error("FORMA", exc)

    try:
        datos = extraer_json_respuesta(raw)
    except Exception as exc:
        return construir_resultado_error("FORMA", exc)

    # Combinar: CEDIA del LLM + novedades de LanguageTool
    cedia_hallazgos = datos.get("hallazgos", [])
    combinados = _deduplicar(cedia_hallazgos, lt_hallazgos)
    datos["hallazgos"] = combinados

    return construir_resultado("FORMA", datos)
