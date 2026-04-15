"""
Agente 5 — NORMATIVO
Valida la correcta aplicación e invocación de artículos de la Ley 1123 de 2007
(Código Disciplinario del Abogado) y la Ley 1952 de 2019 (Código General Disciplinario).
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado
from models.schemas import ResultadoAgente

SYSTEM = """Eres un experto en el régimen disciplinario colombiano con dominio exhaustivo de la
Ley 1123 de 2007 (Código Disciplinario del Abogado) y la Ley 1952 de 2019 (Código General
Disciplinario). Validas que cada artículo citado exista, corresponda al contenido invocado
y esté vigente. Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano bajo la {norma}.

DOCUMENTO:
{texto}

Evalúa EXCLUSIVAMENTE la correcta aplicación de la NORMATIVA DISCIPLINARIA:

PARA LEY 1123 DE 2007 (si aplica):
- Verifica que los artículos citados del Código Disciplinario del Abogado existan y correspondan al contenido invocado
- Detecta artículos citados erróneamente (p. ej. invocar el art. 35 cuando el deber está en el art. 37)
- Identifica deberes profesionales mal calificados o normas de conducta del abogado inaplicadas

PARA LEY 1952 DE 2019 (si aplica):
- Verifica que los artículos citados del Código General Disciplinario existan y correspondan
- Detecta confusiones con la Ley 734 de 2002 (norma anterior, ultraactiva solo para hechos anteriores al 29/06/2021)
- Verifica la correcta invocación de: principios rectores (arts. 4-21), faltas (arts. 48-54), sanciones (arts. 44-47), términos (arts. 101-132)
- Identifica si se aplica correctamente la favorabilidad cuando concurren ambas leyes

PARA AMBAS NORMAS:
- Citas de artículos con numeración incorrecta
- Invocación de normas derogadas sin justificación de ultraactividad
- Ausencia de cita normativa donde la ley la exige expresamente
- Aplicación de norma equivocada para el tipo de servidor o profesional investigado

Responde con este JSON exacto:
```json
{{
  "puntaje": <número entre 0 y 100, donde 100 = aplicación normativa impecable>,
  "resumen": "<párrafo conciso sobre la corrección normativa del documento>",
  "errores": ["<artículo o norma mal aplicada con explicación>", ...],
  "fortalezas": ["<aspecto normativo correctamente aplicado>", ...],
  "recomendaciones": ["<corrección normativa específica recomendada>", ...]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(norma=norma, texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("NORMATIVO", datos)
    except Exception as exc:
        return construir_resultado("NORMATIVO", {
            "puntaje": 0,
            "resumen": f"Error al procesar el agente normativo: {exc}",
            "errores": [str(exc)],
            "fortalezas": [],
            "recomendaciones": ["Revisar manualmente la invocación de artículos de la Ley 1123 y 1952"],
        })
