"""
Agente 4 — FONDO ARGUMENTATIVO
Arquitectura de tres niveles:
  Nivel 1 — Lógica formal (principios de no contradicción, razón suficiente,
             petición de principio, tipo de razonamiento)
  Nivel 2 — Estructura toulminiana (aseveración, fundamentos, garantía,
             respaldo, refutación)
  Nivel 3 — Enfoque argumentativo (demostrativo/dialéctico/retórico)
Cubre: CEDIA-013 (hipótesis como prueba) + M17 completo.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

SYSTEM = """Eres CEDIA-FONDO, experto en argumentación jurídica disciplinaria colombiana con
formación en lógica formal y teoría de la argumentación (modelo toulminiano).
Evalúas la solidez lógica, la estructura argumental y la proporción de los tres enfoques
argumentativos. Una providencia vulnerable tiene >70% demostrativo y <15% dialéctico.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.

DOCUMENTO:
{texto}

═══════════════════════════════════════════════════
NIVEL 1 — LÓGICA FORMAL
═══════════════════════════════════════════════════

PRINCIPIO DE NO CONTRADICCIÓN:
- Afirmaciones mutuamente excluyentes en el mismo documento
- Ejemplo crítico: "comportamiento negligente" Y "con el propósito de dilatar" para
  la misma conducta — culpa y dolo son excluyentes en derecho disciplinario
- También: contradecir en la motivación lo afirmado en los antecedentes

PRINCIPIO DE RAZÓN SUFICIENTE:
- Conclusiones presentadas sin fundamento probatorio que las sostenga
- La queja y la versión libre NO demuestran por sí solos (CEDIA-013): solo la
  práctica de pruebas verifica. Alertar cuando se equipara queja con prueba.
- Generalización apresurada: regla general extraída de casos insuficientes
- Argumento de autoridad sin soporte: "como lo ha establecido reiteradamente
  la jurisprudencia" sin cita de radicado, fecha y corporación

PETICIÓN DE PRINCIPIO:
- Asumir como premisa lo que se quiere concluir
- Ejemplo: "actuó de mala fe, lo que demuestra su mala fe"
- Ejemplo: "la falta es gravísima porque afecta gravemente el servicio" sin análisis

TIPO DE RAZONAMIENTO:
- Identificar si el documento usa deducción (norma → hecho → consecuencia),
  inducción (casos → regla) o analogía (caso similar)
- Reportar si existe contradicción entre el tipo de razonamiento declarado y el
  realmente usado (e.g., declara deducir pero en realidad induce)

FALSA DICOTOMÍA:
- Culpa leve vs. dolo omitiendo culpa grave como tercera opción
- Otras falsas dicotomías que simplifican indebidamente la calificación jurídica

═══════════════════════════════════════════════════
NIVEL 2 — ESTRUCTURA TOULMINIANA
═══════════════════════════════════════════════════
Para cada argumento central identificado en el documento, evaluar:

ASEVERACIÓN (claim): ¿está claramente formulada la tesis del documento?
- Error: tesis implícita o dispersa en varios párrafos sin formulación explícita

FUNDAMENTOS (grounds): ¿los hechos probados sostienen la aseveración?
- Error: fundamentos hipotéticos presentados como probados
- Error: fundamentos ausentes (la conclusión flota sin soporte fáctico)

GARANTÍA (warrant): ¿la norma o principio jurídico invocado es aplicable al caso?
- Error: norma citada cuyo supuesto no se corresponde con los hechos probados
- Error: garantía implícita — el argumento asume una regla sin enunciarla

RESPALDO (backing): ¿el soporte fáctico-jurídico es suficiente o es genérico?
- Error: respaldo genérico ("la jurisprudencia uniforme") sin cita específica
- Error: respaldo insuficiente para la gravedad de la sanción impuesta

REFUTACIÓN ANTICIPADA: ¿el documento responde los descargos del disciplinado?
- Error crítico (alta): el documento ignora completamente los descargos
- Error medio: los descargos se mencionan pero no se rebaten con argumentos

═══════════════════════════════════════════════════
NIVEL 3 — ENFOQUE ARGUMENTATIVO
═══════════════════════════════════════════════════
Evalúa la proporción de los tres enfoques:

DEMOSTRATIVO: ¿prueba lógicamente la responsabilidad con hechos y normas?
DIALÉCTICO: ¿responde los argumentos de la defensa? (mínimo 20% saludable)
RETÓRICO/PERSUASIVO: ¿construye convicción o solo describe hechos?

ALERTA VULNERABILIDAD: si el análisis muestra >70% demostrativo y <15% dialéctico,
reportar como hallazgo de severidad ALTA: "Providencia vulnerable por déficit dialéctico"

M17 CALIDAD LÓGICA ARGUMENTATIVA — criterios adicionales:
- M14 componente argumentativo: inconsistencia en referencia al mismo sujeto que
  afecte la cadena argumental (no solo la coherencia superficial)
- Proporción fáctica vs. jurídica: alertar cuando >70% del documento es síntesis
  fáctica y <20% es análisis jurídico — severidad media

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: vicio lógico que puede generar recurso exitoso o nulidad del fallo
- Media: debilidad argumentativa que puede ser explotada por la defensa
- Baja: imprecisión argumental sin consecuencia procesal directa

Responde con este JSON exacto (máximo 12 hallazgos):
```json
{{
  "puntaje": <0-100; 100=argumentación lógicamente impecable>,
  "resumen": "<párrafo conciso sobre la calidad argumentativa y el perfil toulminiano>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-013|M17|M17-TULMIN|M17-ENFOQUE|M17-PROPORCION|M14>",
      "ubicacion": "<cita textual breve del fragmento, máx 80 caracteres>",
      "error": "<descripción precisa del vicio lógico o argumental>",
      "justificacion": "<principio de lógica formal o criterio toulminiano incumplido>",
      "correccion": "<cómo corregir o fortalecer el argumento>",
      "severidad": "<alta|media|baja>"
    }}
  ],
  "fortalezas": ["<aspectos argumentativos bien logrados>"],
  "recomendaciones": ["<mejoras argumentativas prioritarias>"]
}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    prompt = PLANTILLA.format(texto=texto[:9000])
    try:
        raw = await llamar_openrouter(SYSTEM, prompt, max_tokens=5000)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("FONDO ARGUMENTATIVO", datos)
    except Exception as exc:
        return construir_resultado_error("FONDO ARGUMENTATIVO", exc)
