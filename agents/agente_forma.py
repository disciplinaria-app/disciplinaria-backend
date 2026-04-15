"""
Agente 1 — FORMA
Evalúa la corrección ortográfica, la concordancia gramatical, la puntuación,
el uso de signos y el espaciado dentro del documento disciplinario.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado
from models.schemas import ResultadoAgente

SYSTEM = """Eres un corrector de estilo experto en documentos jurídicos colombianos.
Tu única función es evaluar los aspectos formales de escritura: ortografía, concordancia
gramatical (género, número, persona verbal), puntuación, uso de signos ortográficos y espaciado.
No analices el contenido jurídico. Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

Evalúa EXCLUSIVAMENTE los aspectos de FORMA:
- Ortografía: palabras mal escritas, tildes ausentes o incorrectas (incluye tildes diacríticas)
- Concordancia: discordancia de género (el/la), número (singular/plural) o persona verbal
- Puntuación: comas, puntos, punto y coma, dos puntos mal usados u omitidos
- Signos ortográficos: comillas, paréntesis, guiones, corchetes sin cierre o mal empleados
- Espaciado: dobles espacios, espacios antes de signos de puntuación, falta de espacio tras punto

Para cada error encontrado, indica la frase o fragmento donde ocurre.

Responde con este JSON exacto:
```json
{{
  "puntaje": <número entre 0 y 100, donde 100 = sin errores formales>,
  "resumen": "<párrafo conciso describiendo el estado formal del documento>",
  "errores": ["<descripción del error con fragmento del texto>", ...],
  "fortalezas": ["<aspecto formal bien ejecutado>", ...],
  "recomendaciones": ["<corrección específica recomendada>", ...]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("FORMA", datos)
    except Exception as exc:
        return construir_resultado("FORMA", {
            "puntaje": 0,
            "resumen": f"Error al procesar el agente de forma: {exc}",
            "errores": [str(exc)],
            "fortalezas": [],
            "recomendaciones": ["Revisar manualmente ortografía, puntuación y espaciado"],
        })
