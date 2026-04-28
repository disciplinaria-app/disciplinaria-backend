"""
Agente 4 — ARGUMENTACIÓN (v3.0)
Tres niveles de análisis:
  SA4.1 — Lógica formal: CEDIA-013, M17-A (no contradicción), M17-B (razón suficiente),
           M17-C (petición de principio), M17-D (falsa dicotomía), M17-E (tipo razonamiento)
  SA4.2 — Estructura toulminiana: 5 elementos explícitos + verificación descargos
  SA4.3 — Enfoque argumentativo: proporción demostrativo/dialéctico/retórico
"""

import re

from .base_agent import llamar_por_chunks, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente


# ── Extracción de sección CONSIDERACIONES ─────────────────────────────────────

_RE_CONSID = re.compile(
    r"(?:^|\n)\s*(?:C[oO][nN][sS][iI][dD][eE][rR][aA][cC][iI][oO][nN][eE][sS]"
    r"|CONSIDERACIONES|C\s*O\s*N\s*S\s*I\s*D\s*E\s*R\s*A\s*C\s*I\s*O\s*N\s*E\s*S)"
    r"\s*[:\n]",
    re.IGNORECASE | re.MULTILINE,
)
_RE_SIGUIENTE_SECCION = re.compile(
    r"(?:^|\n)\s*(?:RESUELVE|DECIDE|PARTE\s+RESOLUTIVA|SE\s+RESUELVE|ORDEN[AE]|SANCIONES?)\s*[:\n]",
    re.IGNORECASE | re.MULTILINE,
)


def _extraer_consideraciones(texto: str) -> str:
    m_inicio = _RE_CONSID.search(texto)
    if not m_inicio:
        return texto
    inicio = m_inicio.end()
    m_fin = _RE_SIGUIENTE_SECCION.search(texto, inicio)
    fin = m_fin.start() if m_fin else len(texto)
    seccion = texto[inicio:fin].strip()
    return seccion if seccion else texto


SYSTEM = """Eres CEDIA-ARGUMENTACIÓN, experto en argumentación jurídica disciplinaria colombiana
con formación en lógica formal y teoría de la argumentación (modelo toulminiano).
Evalúas la solidez lógica, la estructura argumental y la proporción de los tres enfoques.
Una providencia vulnerable tiene >70% demostrativo y <15% dialéctico — es reversible en segunda instancia.
No evalúes ortografía ni estilo. Solo evalúa solidez lógica y estructura argumental.
REGLA CRÍTICA — campo "ubicacion":
El campo "ubicacion" debe ser texto copiado literalmente del documento, entre 5 y 25 palabras.
PROHIBIDO: "[Toda la sección CONSIDERACIONES]" / "[Ausencia total en el documento]" / "[Estructura general...]"
CORRECTO: "se concluye que el defensor incumplió su deber de comunicación"
Si el error es una ausencia global (ej. falta elemento Toulmin) → ubicacion = las primeras
15 palabras del párrafo de la sección CONSIDERACIONES donde debería aparecer dicho elemento.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente documento jurídico disciplinario colombiano.
Aplica los tres niveles SOLO en la sección CONSIDERACIONES — no en la síntesis fáctica.

DOCUMENTO COMPLETO:
{texto}

SECCIÓN CONSIDERACIONES (bloque de análisis jurídico extraído):
{consideraciones}

════════════════════════════════════════════════
SA4.1 — LÓGICA FORMAL
════════════════════════════════════════════════

CEDIA-013 — HIPÓTESIS VS PRUEBA (severidad ALTA):
La queja y la versión libre NO demuestran — solo la práctica de pruebas verifica.
Detectar cuando la providencia equipara la queja o la versión del disciplinado
con un hecho probado sin señalar el elemento probatorio que lo corrobora.
Ejemplo de error: "quedó demostrado que el abogado incumplió, según lo relató el quejoso".

M17-A — PRINCIPIO DE NO CONTRADICCIÓN (severidad ALTA cuando es mismo hecho):
Detectar afirmaciones mutuamente excluyentes referidas a la misma conducta o hecho.
Crítico: "comportamiento negligente" Y "con el propósito de dilatar" para la misma
conducta — culpa y dolo son excluyentes según Art. 28 Ley 1952/2019.
También: contradecir en la motivación lo afirmado en los antecedentes del mismo fallo.

M17-B — PRINCIPIO DE RAZÓN SUFICIENTE (severidad MEDIA):
Conclusiones presentadas sin fundamento probatorio que las sostenga.
"Como lo ha establecido reiteradamente la jurisprudencia" sin radicado, fecha y
corporación → argumento de autoridad sin soporte verificable.
Generalización apresurada: regla general extraída de un solo caso o de ninguno.

M17-C — PETICIÓN DE PRINCIPIO:
Asumir como premisa lo que se quiere concluir.
"El abogado actuó de mala fe, lo que demuestra su mala fe".
"La falta es gravísima porque reviste gravedad" sin análisis de los criterios del Art. 43.

M17-D — FALSA DICOTOMÍA:
Presentar solo dos opciones cuando existen más.
Culpa leve vs. dolo omitiendo culpa grave — que tiene consecuencias sancionatorias
distintas bajo el Art. 29 Ley 1952/2019 y puede invalidar la dosificación.

M17-E — TIPO DE RAZONAMIENTO:
Identificar si el documento usa deducción (norma → hecho → consecuencia),
inducción (casos → regla) o analogía (caso similar).
Reportar SOLO si existe contradicción entre el tipo declarado y el realmente usado.

════════════════════════════════════════════════
SA4.2 — ESTRUCTURA TOULMINIANA (5 elementos)
════════════════════════════════════════════════

Verificar en la sección CONSIDERACIONES los 5 elementos. Para cada deficiencia, crear hallazgo:

1. ASEVERACIÓN (claim): tesis principal del fallo.
   Si implícita o dispersa en varios párrafos sin formulación explícita → MEDIA.

2. FUNDAMENTOS (grounds): hechos probatorios que sostienen la aseveración.
   Si se usan quejas o versiones libres sin corroboración como fundamentos (CEDIA-013) → ALTA.
   Si la conclusión aparece sin soporte fáctico alguno → ALTA.

3. GARANTÍA (warrant): norma o principio jurídico que conecta fundamentos con aseveración.
   Si la norma citada no corresponde al supuesto de hecho del caso → ALTA.
   Si la garantía es implícita (el argumento asume una regla sin enunciarla) → MEDIA.

4. RESPALDO (backing): soporte doctrinal/jurisprudencial específico.
   "La jurisprudencia uniforme ha señalado" sin citar radicado, fecha y corporación → MEDIA.
   Respaldo insuficiente para la gravedad de la sanción impuesta → MEDIA.

5. RESPUESTA A DESCARGOS (rebuttal):
   ¿La sección CONSIDERACIONES aborda y rebate los argumentos del disciplinado?
   Señales de descargos en el texto: "el disciplinado alegó", "la defensa sostiene",
   "en sus descargos", "el investigado manifestó", "según el disciplinado".
   — Ausencia total de cualquier referencia a los descargos → ALTA
     (fallo vulnerable a recurso por violación del derecho de defensa y debido proceso).
   — Descargos mencionados pero sin rebate con argumentos concretos → MEDIA.
   — Rebate adecuado → no reportar.

════════════════════════════════════════════════
SA4.3 — ENFOQUE ARGUMENTATIVO
════════════════════════════════════════════════

Evaluar la proporción aproximada de los tres enfoques en la sección CONSIDERACIONES:
- DEMOSTRATIVO: prueba lógicamente la responsabilidad con hechos y normas
- DIALÉCTICO: responde los argumentos de la defensa (mínimo saludable: 20%)
- RETÓRICO/PERSUASIVO: construye convicción sin solo describir hechos

ALERTA VULNERABILIDAD: si >70% es demostrativo y <15% es dialéctico →
hallazgo de severidad ALTA: "Providencia vulnerable — déficit dialéctico: no responde
los descargos de la defensa, exposición a recurso exitoso en segunda instancia."

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: vicio lógico que puede generar recurso exitoso o nulidad del fallo
- Media: debilidad argumental que puede ser explotada por la defensa
- Baja: imprecisión sin consecuencia procesal directa

REGLA OBLIGATORIA CAMPO "correccion":
Si el párrafo ya contiene un adverbio en -mente, la corrección NO puede introducir otro.
Usar "con + sustantivo abstracto": "lógicamente" → "con rigor lógico".

Responde con este JSON exacto (máximo 12 hallazgos):
```json
{{
  "puntaje": <0-100; 100=argumentación impecable>,
  "resumen": "<párrafo conciso sobre calidad argumentativa y perfil toulminiano>",
  "hallazgos": [
    {{
      "modulo": "<CEDIA-013|M17-A|M17-B|M17-C|M17-D|M17-E|M17-TOULMIN|M17-ENFOQUE>",
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
    consideraciones = _extraer_consideraciones(texto)
    consid_fija = consideraciones[:4000]
    try:
        datos = await llamar_por_chunks(
            SYSTEM,
            lambda chunk: PLANTILLA.format(texto=chunk, consideraciones=consid_fija),
            texto=texto,
            max_tokens=5000,
        )
        return construir_resultado("ARGUMENTACIÓN", datos)
    except Exception as exc:
        return construir_resultado_error("ARGUMENTACIÓN", exc)
