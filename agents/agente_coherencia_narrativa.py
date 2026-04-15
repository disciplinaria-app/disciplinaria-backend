"""
Agente 3 — COHERENCIA NARRATIVA
Evalúa la consistencia lógica del relato: contradicciones entre testimonios,
manejo del discurso indirecto, claridad de referentes pronominales y progresión temática.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado
from models.schemas import ResultadoAgente

SYSTEM = """Eres un experto en análisis del discurso jurídico colombiano especializado en coherencia
narrativa de documentos disciplinarios. Detectas contradicciones, ambigüedades referenciales y
rupturas en la progresión temática del texto. No analices el fondo jurídico.
Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

Evalúa EXCLUSIVAMENTE los aspectos de COHERENCIA NARRATIVA:
- Contradicciones testimoniales: afirmaciones en distintas partes del documento que se contradicen entre sí (fechas, lugares, personas, hechos narrados)
- Discurso indirecto: introducción incorrecta o inconsistente del estilo indirecto al citar declaraciones ("manifestó que...", "señaló que..."); cambios abruptos de estilo directo a indirecto sin marcación
- Referentes pronominales ambiguos: pronombres (él, ella, este, aquel, mismo) cuyo antecedente es ambiguo o incorrecto, generando confusión sobre quién hace qué acción
- Progresión temática: párrafos que interrumpen el hilo narrativo, ideas que aparecen sin preparación o que quedan inconclusas
- Cohesión textual: ausencia de conectores lógicos, repetición innecesaria de sustantivos donde debería usarse un pronombre, o viceversa

Responde con este JSON exacto:
```json
{{
  "puntaje": <número entre 0 y 100, donde 100 = narrativa perfectamente coherente>,
  "resumen": "<párrafo conciso sobre la coherencia narrativa del documento>",
  "errores": ["<descripción de la contradicción o ruptura con fragmento del texto>", ...],
  "fortalezas": ["<aspecto narrativo bien logrado>", ...],
  "recomendaciones": ["<sugerencia específica para mejorar la coherencia>", ...]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("COHERENCIA NARRATIVA", datos)
    except Exception as exc:
        return construir_resultado("COHERENCIA NARRATIVA", {
            "puntaje": 0,
            "resumen": f"Error al procesar el agente de coherencia narrativa: {exc}",
            "errores": [str(exc)],
            "fortalezas": [],
            "recomendaciones": ["Revisar manualmente contradicciones y referentes pronominales"],
        })
