"""
Agente 1 — FORMA
Cubre: CEDIA-007 (ortografía/tildes), CEDIA-008 (concordancia), CEDIA-010 (puntuación),
       CEDIA-011 (espaciado), CEDIA-017 (signos sin cerrar), CEDIA-018 (redundancias/
       repetición morfológica) + M19 patrones 1 y 2 (número sin sustantivo, sustantivo
       sin número).

Fuentes combinadas (en paralelo):
  1. Detección determinista (deteccion_forma.py) — reglas mecánicas: tildes de lista
     cerrada, espaciado numérico, O/0, palabras unidas, redundancias, régimen, dequeísmo
  2. LLM (OpenRouter) — reglas que exigen juicio contextual: concordancia, tiempos,
     repetición morfológica, inserción espuria
  3. LanguageTool Premium — ortografía, gramática y puntuación de cobertura amplia

Prioridad en deduplicación: determinista > LLM > LanguageTool.
"""

import asyncio
import httpx

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error, llamar_por_chunks
from .deteccion_forma import analizar_deterministico
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


def _deduplicar(*fuentes: list[dict]) -> list[dict]:
    """
    Fusiona hallazgos de varias fuentes en orden de prioridad (la primera gana).
    Un hallazgo se descarta si su ubicacion ya está cubierta, o si su ubicacion
    contiene/está contenida en una ya vista (solapamiento parcial).
    """
    resultado: list[dict] = []
    vistas: list[str] = []
    for fuente in fuentes:
        for h in fuente:
            ubi = h["ubicacion"].lower().strip()
            if not ubi:
                continue
            if any(ubi in v or v in ubi for v in vistas):
                continue
            vistas.append(ubi)
            resultado.append(h)
    return resultado


# ── Prompt CEDIA ──────────────────────────────────────────────────────────────

SYSTEM = """Eres CEDIA-FORMA, corrector especializado en documentos jurídicos disciplinarios colombianos.
Detecta exclusivamente errores objetivos de escritura verificables según RAE 2010.
No interpretes contenido jurídico. No evalúes argumentos. Solo verifica escritura.
Principio de duda razonable: si el texto puede leerse como correcto, no lo reportes.
REGLA CRÍTICA — campo "ubicacion":
El campo "ubicacion" debe ser texto copiado literalmente del documento, entre 5 y 25 palabras.
PROHIBIDO: descripciones, títulos de sección, meta-referencias abstractas.
INCORRECTO: "Toda la sección CONSIDERACIONES" / "Ausencia total en el documento"
CORRECTO: "el disciplinado manifestó que no recordaba el caso"
Si no puedes citar texto literal → omite el hallazgo completamente.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente fragmento de un documento jurídico disciplinario colombiano.
No interpretes contenido jurídico. Solo verifica errores objetivos de escritura.

DOCUMENTO:
{texto}

M1 — ORTOGRAFÍA CONTEXTUAL (solo casos que exigen leer el contexto)
Verbos donde la forma sin tilde TAMBIÉN es palabra válida — decidir por contexto:
"el juez ordeno" → "ordenó" (3ª persona pretérito) pero "yo ordeno" es correcto.
Aplica a: afirmo/afirmó, ordeno/ordenó, considero/consideró, señalo/señaló,
evidencio/evidenció, continuo/continuó, practico/practicó, sanciono/sancionó.
Tildes diacríticas por contexto: él/el, tú/tu, más/mas, sí/si, aún/aun, sé/se.
Tildes incorrectas: "previo", "continuo" como adjetivos NO llevan tilde.
Homófonos: callo/cayó, haber/a ver, porque/por qué/porqué.
Queísmo: "se percató que" → "se percató de que".
No reportar: nombres propios extranjeros, términos técnicos sin equivalente,
tildes de lista fija (incurrio, resolvio…) ni espaciado numérico — eso lo
detecta otro módulo; no lo dupliques.

M2 — CONCORDANCIA NOMINAL (incluye verificación género-nombre propio)
Regla: artículo, sustantivo y adjetivo deben concordar en género y número.
"las pruebas aportados" → "aportadas"; "los elemento probatorio" → "los elementos".
ALTA SEVERIDAD — género opuesto al nombre propio que sigue en el párrafo:
"la abogada CHRISTIAN GERARDO MARTÍNEZ" → "el abogado CHRISTIAN GERARDO MARTÍNEZ"
"el disciplinado MARÍA CAMILA TORRES" → "la disciplinada MARÍA CAMILA TORRES"
Indicios masculinos: CHRISTIAN, CARLOS, JORGE, LUIS, ANDRÉS, GABRIEL, GERARDO, JUAN.
Indicios femeninos: MARÍA, ANA, LAURA, CAROLINA, ANDREA, CAMILA, DIANA, PATRICIA.
Excepciones que NO son error: sujeto colectivo singular ("la Sala considera"), pasiva refleja.
CRÍTICO: Este criterio aplica a TODOS los párrafos del documento sin excepción,
incluyendo encabezado, antecedentes, consideraciones y especialmente la parte
resolutiva (RESUELVE / PRIMERO / SEGUNDO / TERCERO). Un error de concordancia
género↔nombre propio en la parte resolutiva es siempre ALTA SEVERIDAD porque
identifica incorrectamente al sujeto disciplinado en el acto jurídico definitivo.

M3 — CONCORDANCIA VERBAL
Regla: verbo concuerda en número y persona con el sujeto gramatical.
"los elementos probatorios demuestra" → "demuestran"
"la defensa y la fiscalía presentó" → "presentaron"
No reportar: sujetos pospuestos ambiguos, sujetos colectivos con verbo singular aceptado.

M4 — CONSISTENCIA TEMPORAL
Regla: hechos narrados en pretérito, consideraciones jurídicas en presente,
decisum en presente o futuro. Cambio injustificado en el mismo párrafo = error.
SOLO alertar cuando el tiempo cambia sin justificación narrativa ni jurídica.
No reportar: citas textuales ni transcripciones de declaraciones.
No reportar: "incumplió los deberes [pretérito] — la falta es gravísima [presente]"
— la alternancia narración/calificación es correcta.

M5 — REPETICIÓN MORFOLÓGICA POR RAÍZ
Detectar: misma raíz morfológica en el mismo párrafo indica pobreza léxica.
contactar/contactarlo (raíz CONTACT), respondió/respondiendo (raíz RESPOND),
comunicar/comunicación en mismo párrafo.
Excepción: términos técnicos sin sinónimo real (disciplinado, quejoso, falta, norma).
CRÍTICO: la corrección NO puede usar la misma raíz léxica que la palabra errónea.
"comunicar/comunicación" → NO "hacer comunicación" → SÍ "transmitir / informar".

CEDIA-017 — INSERCIÓN ESPURIA DE PREPOSICIÓN (solo casos contextuales)
Preposición intrusa entre verbo transitivo y complemento directo, cuando el
régimen del verbo NO la exige: "proceso de disciplinario" → "proceso disciplinario",
"falta de profesional" → "falta profesional".
VERBOS QUE RIGEN "con" POR SU PROPIO RÉGIMEN — NUNCA reportar:
  comunicarse con, hablar con, contar con, reunirse con, cumplir con,
  comprometerse con, contactar con.
PROHIBIDO: reportar "se comunicó con", "habló con", "se reunió con" como inserción.
El dequeísmo simple (consideró de que…) lo detecta otro módulo; no lo dupliques.

CRITERIOS DE SEVERIDAD:
- Alta: afecta validez jurídica o identifica incorrectamente al sujeto disciplinado
- Media: genera ambigüedad interpretable por la defensa
- Baja: error de forma sin impacto sustancial

REGLA OBLIGATORIA CAMPO "correccion":
Si el párrafo ya contiene un adverbio en -mente, la corrección NO puede introducir otro.
Usar "con + sustantivo abstracto": "claramente" → "con claridad".

Responde con este JSON exacto (máximo 12 hallazgos):
```json
{{
  "puntaje": <0-100; 100=sin errores de forma>,
  "resumen": "<párrafo conciso sobre el estado formal del documento>",
  "hallazgos": [
    {{
      "modulo": "<M1|M2|M3|M4|M5|CEDIA-017>",
      "ubicacion": "<fragmento exacto del texto con el error, máx 80 caracteres>",
      "error": "<descripción concisa del error>",
      "justificacion": "<regla RAE o criterio CEDIA que lo sustenta>",
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
    # Detección determinista: instantánea, 0 tokens, siempre reproducible
    det_hallazgos = analizar_deterministico(texto)

    # LT corre en paralelo mientras el LLM procesa los chunks secuencialmente
    lt_task = asyncio.create_task(_consultar_languagetool(texto))

    try:
        datos = await llamar_por_chunks(SYSTEM, lambda chunk: PLANTILLA.format(texto=chunk), texto=texto)
        lt_hallazgos = await lt_task
    except Exception as exc:
        return construir_resultado_error("FORMA", exc)

    cedia_hallazgos = datos.get("hallazgos", [])
    # Prioridad: determinista > LLM > LanguageTool
    datos["hallazgos"] = _deduplicar(det_hallazgos, cedia_hallazgos, lt_hallazgos)

    return construir_resultado("FORMA", datos)
