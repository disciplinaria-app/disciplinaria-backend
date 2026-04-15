"""
Agente 4 — FONDO ARGUMENTATIVO
Evalúa la solidez de la argumentación: unificación nominal de sujetos,
cronología de los hechos, exactitud de las citas normativas y omisión de palabras.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado
from models.schemas import ResultadoAgente

SYSTEM = """Eres un experto en argumentación jurídica disciplinaria colombiana.
Evalúas la consistencia argumentativa del documento: si los sujetos son identificados
de manera uniforme, si la cronología es coherente, si las citas normativas son exactas
y si hay palabras omitidas que alteran el sentido jurídico.
Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

Evalúa EXCLUSIVAMENTE los aspectos de FONDO ARGUMENTATIVO:
- Unificación nominal: el disciplinado, el quejoso, los testigos y las entidades deben ser denominados de manera uniforme a lo largo del documento; detecta variaciones que generen confusión (p. ej. "el señor Pérez" / "el investigado" / "el servidor" referidos a la misma persona sin criterio claro)
- Cronología de hechos: inconsistencias en el orden temporal de los hechos narrados; fechas que contradicen la secuencia lógica de los eventos disciplinarios
- Citas normativas: artículos citados sin número exacto, citas de normas derogadas sin indicar ultraactividad, referencias incompletas (p. ej. "el artículo mencionado" sin especificar cuál), transposición de números de artículo
- Omisión de palabras: palabras faltantes que alteran el sentido jurídico de una oración (negaciones omitidas, verbos ausentes, conectores faltantes que invierten el argumento)
- Solidez de la argumentación: premisas que no conducen lógicamente a la conclusión, saltos argumentativos no justificados

Responde con este JSON exacto:
```json
{{
  "puntaje": <número entre 0 y 100, donde 100 = argumentación sólida y consistente>,
  "resumen": "<párrafo conciso sobre la calidad argumentativa del documento>",
  "errores": ["<descripción del problema con fragmento del texto>", ...],
  "fortalezas": ["<aspecto argumentativo bien logrado>", ...],
  "recomendaciones": ["<corrección específica para fortalecer el argumento>", ...]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("FONDO ARGUMENTATIVO", datos)
    except Exception as exc:
        return construir_resultado("FONDO ARGUMENTATIVO", {
            "puntaje": 0,
            "resumen": f"Error al procesar el agente de fondo argumentativo: {exc}",
            "errores": [str(exc)],
            "fortalezas": [],
            "recomendaciones": ["Revisar manualmente cronología y citas normativas"],
        })
