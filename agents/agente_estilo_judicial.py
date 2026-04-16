"""
Agente 2 — ESTILO JUDICIAL
Cubre: CEDIA-005 (gerundios incorrectos), CEDIA-012 (adverbios en -mente /
       mayúsculas institucionales), M14 componente de forma (denominación
       formal inconsistente que afecta el registro — no la coherencia
       argumental, que pertenece al Agente 3).
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

SYSTEM = """Eres CEDIA-ESTILO, experto en registro jurídico-forense colombiano.
Evalúas únicamente el uso correcto del lenguaje forense: gerundios, adverbios,
mayúsculas, latinismos y denominación formal de sujetos.
NO analices el contenido sustancial ni la lógica argumentativa.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

CRITERIOS DE ANÁLISIS:

CEDIA-005 · GERUNDIOS (M5c):
- Gerundio copulativo como predicado principal: "resolviendo" / "ordenando" usado como
  verbo principal de la oración → sustituir por verbo conjugado
- Gerundio de posterioridad: describe acción posterior a la principal, incorrecto en español
- Máximo 1 gerundio por página; más de eso → alertar con severidad media
- NO alertar gerundios correctos: gerundio de simultaneidad ("caminando llegó"),
  perífrasis verbales ("estaba analizando")

CEDIA-012 · ADVERBIOS EN -MENTE Y MAYÚSCULAS (M5b, M5d):
Adverbios en -mente:
- Máximo 1 adverbio en -mente por página; acumulación debilita la contundencia judicial
- Alertar en particular: "claramente", "evidentemente", "notoriamente", "obviamente",
  "efectivamente", "reiteradamente" — usados sin sustento probatorio expreso
- Severidad: baja si hay 1 por página, media si hay 2+ en el mismo párrafo

Mayúsculas institucionales (RAE 2010):
- Cargos siempre en MINÚSCULA: magistrado, juez, disciplinado, quejoso, defensor,
  ponente, instructor, fiscal, secretario
- Conceptos jurídicos genéricos en MINÚSCULA: falta disciplinaria, falta gravísima,
  proceso disciplinario, sanción disciplinaria, deber funcional, artículo, numeral
- Instituciones en MAYÚSCULA cuando son entidades específicas: Comisión Nacional
  de Disciplina Judicial, Estado, Congreso, Procuraduría General de la Nación
- "Ley" en MAYÚSCULA solo en nombre propio: Ley 1123, Ley 1952; en uso genérico: "la ley"
- Errores frecuentes: "falta Disciplinaria" → "falta disciplinaria",
  "el Artículo 28" → "el artículo 28", "falta Gravísima" → "falta gravísima"
- Severidad: alta para conceptos jurídicos genéricos mal capitalizados

Latinismos:
- Usar en cursiva: a quo, a quem, in dubio pro disciplinado, prima facie,
  ratio decidendi, obiter dictum, per se, ex officio, ibidem, supra, infra,
  mutatis mutandis, grosso modo, ad hoc, inter alia, ex ante, ex post
- Latinismo innecesario cuando existe equivalente castellano más claro: media
- Latinismo mal empleado: alta

M14 COMPONENTE DE FORMA — denominación formal:
Detecta solo inconsistencias de registro formal (no de coherencia argumental):
- Alternancia de "quejoso" y "denunciante" para el mismo sujeto bajo Ley 1123
  (bajo Ley 1123 el término correcto es QUEJOSO, no "denunciante")
- Alternancia sin patrón claro entre "togado" / "disciplinado" / "investigado" /
  "profesional" cuando podría generar ambigüedad de rol procesal
- Uso de primera persona ("yo considero", "a mi juicio") en providencia:
  sustituir por impersonal o tercera persona

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: error que afecta la validez del acto o introduce ambigüedad interpretable
- Media: debilita la contundencia judicial o es inconsistente con el registro forense
- Baja: error de estilo corregible sin impacto sustancial

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{
  "puntaje": <0-100; 100=estilo judicial impecable>,
  "resumen": "<párrafo conciso sobre el nivel de estilo judicial>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-005|CEDIA-012|M14>",
      "ubicacion": "<cita textual breve, máx 80 caracteres>",
      "error": "<descripción del problema de estilo>",
      "justificacion": "<convención RAE o criterio CEDIA que se incumple>",
      "correccion": "<redacción corregida o sugerencia concreta>",
      "severidad": "<alta|media|baja>"
    }}
  ],
  "fortalezas": ["<aspectos de estilo bien logrados>"],
  "recomendaciones": ["<mejoras de estilo prioritarias>"]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("ESTILO JUDICIAL", datos)
    except Exception as exc:
        return construir_resultado_error("ESTILO JUDICIAL", exc)
