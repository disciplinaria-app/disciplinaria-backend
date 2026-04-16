"""
Agente 3 — COHERENCIA NARRATIVA
Cubre: CEDIA-001 (contradicción testimonial), CEDIA-002 (construcción circular),
       CEDIA-006 (referente pronominal ambiguo), M14 componente de coherencia
       (misma persona referida de modo que afecta la comprensión del razonamiento),
       M15 (continuidad cronológica procesal), M16 (identificación redundante
       o ambigua de personas y roles).
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

SYSTEM = """Eres CEDIA-COHERENCIA, analista experto en discurso jurídico disciplinario colombiano.
Tu misión es detectar contradicciones, ambigüedades referenciales, rupturas narrativas y lagunas
en la progresión cronológica del texto. Principio fundamental: el redactor DEPURA las
contradicciones de los testigos, no las transcribe como hechos probados.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

CRITERIOS DE ANÁLISIS:

CEDIA-001 · CONTRADICCIÓN TESTIMONIAL (M11):
Síntesis fáctica que contiene afirmaciones incompatibles sobre el mismo hecho:
- "Nunca hubo contacto" y "sí hubo reunión en agosto" en el mismo párrafo
- Atribución de dolo y culpa simultáneamente a la misma conducta (son excluyentes
  según la estructura de responsabilidad disciplinaria)
- Hechos descritos como probados que luego se contradicen en las consideraciones
- Severidad: alta si la contradicción afecta la subsunción típica; media si es narrativa

CEDIA-002 · CONSTRUCCIÓN CIRCULAR (M11 variante):
- Argumento circular heredado del testigo: usar verbos distintos para el mismo argumento
  sin agregar información nueva ("increpó / preguntó / cuestionó" para la misma acción)
- Reafirmación sin avance: repetir la conclusión con palabras distintas como si fuera
  una segunda premisa ("actuó de mala fe, lo que demuestra su mala fe")
- Insuficiencia explicativa: hechos procesales no evidentes para el lector no especializado
  mencionados sin contexto ("como consta en el expediente" sin citar qué consta)
- Severidad: media (debilita; rara vez invalida por sí solo)

CEDIA-006 · REFERENTE PRONOMINAL AMBIGUO (M12, M13):
Pureza del discurso indirecto:
- Pronombre sobrante cuando el sujeto ya fue nombrado y no hay ambigüedad
- Pronombre ambiguo ("ella", "este") cuando puede referirse a más de un sujeto
  en el mismo párrafo
- Filtración de primera persona en narración de tercera: "me dijo que él había dicho"
- Ambigüedad posesiva: "el togado tenía su número celular" — ¿de quién?
- Contexto de mayor riesgo: párrafos con múltiples actores simultáneos
  (investigado, quejoso, testigo, juez, defensor)
- Severidad: alta si la ambigüedad genera confusión sobre quién cometió el hecho;
  media si es sobre roles secundarios

M14 COMPONENTE DE COHERENCIA — consistencia referencial argumental:
Detecta cuando la referencia al mismo sujeto dentro de un MISMO argumento
(no solo en el documento completo) genera confusión del razonamiento:
- "El señor Pérez" (quejoso) y "el denunciante" en la misma oración argumental
  bajo Ley 1123 donde el término técnico es "quejoso"
- Mismo sujeto con denominaciones que implican roles procesales distintos
  en la misma cadena argumentativa

M15 · CONTINUIDAD CRONOLÓGICA PROCESAL:
- Saltos ordinales sin justificación: pasar de "primera sesión" a "tercera sesión"
  sin mencionar la segunda genera laguna probatoria atacable en recurso
- Excepción válida: omisión justificada expresamente ("en la segunda sesión no
  se practicaron pruebas de relevancia")
- Referencias temporales contradictorias: fecha A posterior a fecha B cuando
  debería ser anterior según la secuencia procesal
- Severidad: alta si la laguna afecta la cadena probatoria; media si es narrativa

M16 · IDENTIFICACIÓN REDUNDANTE O AMBIGUA:
- Misma persona referida con dos relaciones distintas sin aclaración:
  "madre del denunciante" y "hermana del quejoso" para la misma persona
- Confusión de roles procesales: testigo que declara y testigo que debió ser citado
  en el mismo párrafo sin distinción
- Severidad: media

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: contradicción o ambigüedad que puede generar un recurso exitoso de nulidad
- Media: debilita la narrativa o crea ambigüedad interpretable por la defensa
- Baja: imprecisión sin impacto en el fondo

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{
  "puntaje": <0-100; 100=narrativa perfectamente coherente>,
  "resumen": "<párrafo conciso sobre la coherencia narrativa del documento>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-001|CEDIA-002|CEDIA-006|M14|M15|M16>",
      "ubicacion": "<cita textual breve del fragmento, máx 80 caracteres>",
      "error": "<descripción de la contradicción, ambigüedad o ruptura>",
      "justificacion": "<principio discursivo o criterio CEDIA incumplido>",
      "correccion": "<redacción corregida o restructuración sugerida>",
      "severidad": "<alta|media|baja>"
    }}
  ],
  "fortalezas": ["<aspectos narrativos bien logrados>"],
  "recomendaciones": ["<mejoras de coherencia prioritarias>"]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:8000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("COHERENCIA NARRATIVA", datos)
    except Exception as exc:
        return construir_resultado_error("COHERENCIA NARRATIVA", exc)
