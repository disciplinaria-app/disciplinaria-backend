"""
Agente 1 — FORMA
Cubre: CEDIA-007 (ortografía/tildes), CEDIA-008 (concordancia), CEDIA-010 (puntuación),
       CEDIA-011 (espaciado), CEDIA-017 (signos sin cerrar), CEDIA-018 (redundancias/
       repetición morfológica) + M19 patrones 1 y 2 (número sin sustantivo, sustantivo
       sin número).
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

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


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("FORMA", datos)
    except Exception as exc:
        return construir_resultado_error("FORMA", exc)
