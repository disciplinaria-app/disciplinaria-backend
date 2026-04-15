"""
Agente 2 — ESTILO JUDICIAL
Evalúa el uso correcto del registro jurídico-formal: gerundios inapropiados,
abuso de adverbios, manejo de mayúsculas institucionales y latinismos.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado
from models.schemas import ResultadoAgente

SYSTEM = """Eres un experto en redacción jurídica colombiana especializado en estilo judicial.
Evalúas el registro, la propiedad idiomática y las convenciones del lenguaje forense colombiano.
No analices el contenido sustancial. Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

Evalúa EXCLUSIVAMENTE los aspectos de ESTILO JUDICIAL:
- Gerundios: uso incorrecto de gerundios copulativos ("resolviendo", "ordenando" como predicado principal), gerundio de posterioridad
- Adverbios en -mente: acumulación innecesaria, adverbios que debilitan la contundencia jurídica ("claramente", "evidentemente", "notoriamente" sin sustento)
- Registro formal: coloquialismos, términos imprecisos o informales inadecuados para un fallo disciplinario
- Mayúsculas institucionales: uso incorrecto de mayúsculas en cargos, entidades, dependencias (p. ej. "el Alcalde" vs. "el alcalde", "la Procuraduría General")
- Latinismos y locuciones latinas: uso correcto e imprescindible de expresiones como "in dubio pro disciplinado", "prima facie", "res iudicata", "non bis in ídem"; latinismos innecesarios o mal empleados

Responde con este JSON exacto:
```json
{{
  "puntaje": <número entre 0 y 100, donde 100 = estilo judicial impecable>,
  "resumen": "<párrafo conciso sobre el nivel de estilo judicial del documento>",
  "errores": ["<descripción del problema con el fragmento del texto>", ...],
  "fortalezas": ["<aspecto de estilo bien logrado>", ...],
  "recomendaciones": ["<sugerencia de redacción específica>", ...]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("ESTILO JUDICIAL", datos)
    except Exception as exc:
        return construir_resultado("ESTILO JUDICIAL", {
            "puntaje": 0,
            "resumen": f"Error al procesar el agente de estilo judicial: {exc}",
            "errores": [str(exc)],
            "fortalezas": [],
            "recomendaciones": ["Revisar manualmente gerundios, adverbios y mayúsculas"],
        })
