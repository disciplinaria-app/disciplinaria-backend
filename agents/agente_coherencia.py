"""
Agente 3 — COHERENCIA NARRATIVA (v3.0)
Subagentes:
  SA3.1 — Contradicciones: CEDIA-001 (proceso en ausencia), CEDIA-002 (sesiones),
           CEDIA-006 (construcción circular), M11 (síntesis con afirmaciones incompatibles)
  SA3.2 — Referentes y discurso: M12 (discurso indirecto contaminado),
           M13 (referente pronominal ambiguo), M15 (continuidad cronológica), M16 (identif. ambigua)

Principio absoluto: el redactor DEPURA las contradicciones de los testigos — no las
transcribe como hechos probados. Reportar error del REDACTOR, nunca del testigo.
"""

from .base_agent import llamar_por_chunks, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

SYSTEM = """Eres CEDIA-COHERENCIA, analista experto en discurso jurídico disciplinario colombiano.
Detectas contradicciones, ambigüedades referenciales, rupturas narrativas y lagunas
cronológicas. Principio absoluto: el redactor DEPURA — no transcribe. Solo reportas
errores del REDACTOR, nunca del testigo que declaró algo incoherente.
REGLA CRÍTICA — campo "ubicacion":
El campo "ubicacion" debe ser texto copiado literalmente del documento, entre 5 y 25 palabras.
PROHIBIDO: descripciones, títulos de sección, meta-referencias abstractas.
INCORRECTO: '"primera fecha" → "tercera sesión" sin referencia a segunda'
CORRECTO: "en la primera fecha de audiencia el procesado no compareció"
Si no puedes citar texto literal → omite el hallazgo completamente.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente fragmento de un documento jurídico disciplinario colombiano.
REGLA ABSOLUTA: reportar solo errores del REDACTOR. Si el testigo declaró algo contradictorio,
eso es proceso normal — el error es que el REDACTOR lo haya reproducido sin depurar.

DOCUMENTO:
{texto}

SA3.1 — CONTRADICCIONES

CEDIA-001 — PROCESO PENAL EN AUSENCIA
NO es una contradicción narrativa. La condena en ausencia es procesalmente válida.
Si el procesado fue juzgado sin comparecer, el redactor debe contextualizarlo brevemente
para el lector no especializado — pero NO es error del redactor si no lo hace.
NUNCA reportar la ausencia del procesado como contradicción o laguna.

CEDIA-002 — SESIONES SIN ACTIVIDAD PROBATORIA
No todas las sesiones producen actividad probatoria relevante.
Laguna cronológica = error SOLO si genera duda sobre la completitud del análisis.
  — Si la sesión sin actividad está brevemente referenciada → no es error.
  — Salto ordinal sin mención: "primera fecha" → "tercera sesión" sin referencia
    a la segunda → SÍ es error (MEDIA): laguna probatoria atacable en recurso.
  — Excepción: "en la segunda sesión no se practicaron pruebas relevantes" → OK.

CEDIA-006 — CONSTRUCCIÓN CIRCULAR DEL TESTIGO
Detectar cuando el REDACTOR reproduce el argumento del testigo en varias formas
distintas con verbos distintos (increpó, preguntó, cuestionó, requirió) para la
MISMA acción sin añadir información nueva.
Error del redactor: debió sintetizar en una sola oración, no repetir con sinónimos.
Severidad: MEDIA — debilita la narrativa pero rara vez invalida por sí solo.

M11 — SÍNTESIS TESTIMONIAL CON AFIRMACIONES INCOMPATIBLES
Síntesis que contiene afirmaciones mutuamente excluyentes sobre el mismo hecho:
"nunca hubo contacto" Y "se comunicaron en agosto" en el mismo texto.
"actuó de manera negligente" Y "con el propósito de dilatar" para el mismo hecho
— culpa y dolo son excluyentes bajo el régimen de responsabilidad disciplinaria.
  — Si la contradicción es relevante para la decisión → ALTA.
  — Si es irrelevante para el fondo, el redactor debió omitirla → MEDIA.

SA3.2 — REFERENTES Y DISCURSO

M12 — DISCURSO INDIRECTO CONTAMINADO
Detectar en la narración del redactor (no en citas textuales):
- Pronombre sobrante: sujeto ya nombrado + pronombre redundante.
  "él comunicó que él vendría" → "comunicó que vendría".
- Filtración de primera persona: "señaló que considera" (presente de 1ª persona
  disfrazado) → "señaló que consideraba" (concordancia temporal correcta).
- Ambigüedad posesiva: "el togado tenía su número celular" cuando hay dos sujetos
  posibles en el párrafo y no queda claro de quién es el número.
Severidad: ALTA si genera confusión sobre quién actuó; MEDIA en roles secundarios.

M13 — REFERENTE PRONOMINAL AMBIGUO
Detectar pronombre (él, ella, ellos, este, ese, aquél) con más de un referente
posible en el mismo párrafo. Reportar el pronombre y los posibles referentes.
Contexto de mayor riesgo: párrafos con múltiples actores simultáneos
(disciplinado, quejoso, testigo, magistrado, defensor).
Severidad: ALTA si la ambigüedad recae sobre quién cometió la conducta disciplinada.

M15 — CONTINUIDAD CRONOLÓGICA PROCESAL
Detectar saltos en la secuencia ordinal de sesiones o fechas sin justificación:
"primera fecha" → "tercera sesión" sin mención de la segunda → laguna.
Excepción válida: "en la segunda sesión no se practicaron pruebas relevantes" →
mención explícita que justifica la ausencia.
Referencias temporales contradictorias: fecha A posterior a fecha B cuando la
secuencia procesal indica que A debería ser anterior.
Severidad: ALTA si la laguna afecta la cadena probatoria; MEDIA si es solo narrativa.

M16 — IDENTIFICACIÓN REDUNDANTE O AMBIGUA
Misma persona descrita con dos relaciones distintas sin aclaración:
"madre del denunciante" y "hermana del quejoso" en el mismo párrafo — ¿es la misma?
Confusión de roles procesales: testigo que declara Y testigo que debió ser citado
en el mismo párrafo sin distinción clara entre ambos estados.
Mismo sujeto presentado en dos roles incompatibles sin señalarlo: "el quejoso,
quien también actuó como testigo" — si no se aclara puede dar nulidad.
Severidad: MEDIA; ALTA si la confusión afecta la validez de una prueba.

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: contradicción o ambigüedad que puede generar recurso exitoso de nulidad
- Media: debilita la narrativa o crea ambigüedad interpretable por la defensa
- Baja: imprecisión estilística sin impacto en el fondo

REGLA OBLIGATORIA CAMPO "correccion":
Si el párrafo ya contiene un adverbio en -mente, la corrección NO puede introducir otro.
Usar "con + sustantivo abstracto": "claramente" → "con claridad", "expresamente" → "de forma expresa".

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{
  "puntaje": <0-100; 100=narrativa perfectamente coherente>,
  "resumen": "<párrafo conciso sobre la coherencia narrativa del documento>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-001|CEDIA-002|CEDIA-006|M11|M12|M13|M15|M16>",
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
    try:
        datos = await llamar_por_chunks(SYSTEM, lambda chunk: PLANTILLA.format(texto=chunk), texto=texto)
        return construir_resultado("COHERENCIA NARRATIVA", datos)
    except Exception as exc:
        return construir_resultado_error("COHERENCIA NARRATIVA", exc)
