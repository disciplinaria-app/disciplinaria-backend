"""
Agente 2 — ESTILO (v3.0)
Subagentes:
  SA2.1 — Registro y conectores: M6 (gerundios), M7 (mayúsculas RAE), M9 (latinismos),
           CEDIA-010 (capitalización jurídica genérica), CEDIA-012 (alerta temprana global)
  SA2.2 — Adverbios y denominación: CEDIA-011 (adverbios -mente por folio), M14 (sinonimia)

Detección determinista de folio (SA2.1 + SA2.2): M6 y CEDIA-011 se cuentan por
bloque de ~300 palabras sin llamada LLM — resultado siempre reproducible.
"""

import re

from .base_agent import llamar_por_chunks, construir_resultado, construir_resultado_error
from models.schemas import ResultadoAgente

# ── SA2.1 + SA2.2 determinista: gerundios y adverbios -mente por folio ────────

_RE_MENTE  = re.compile(r"\b\w+mente\b", re.IGNORECASE)
_RE_GERUND = re.compile(r"\b\w+[aáe]ndo\b", re.IGNORECASE)
_PALABRAS_POR_FOLIO = 300

# Nombres propios colombianos que terminan en -ando/-endo y no son gerundios.
# Sin este filtro el regex los clasifica como gerundios (falsos positivos).
_NOMBRES_NO_GERUNDIO = frozenset({
    "armando", "fernando", "orlando", "hernando", "rolando",
    "alejandro", "bernardo", "leonardo", "gerardo", "eduardo",
    "ricardo", "gustavo", "roberto", "alberto", "ernando",
})


def _analizar_folios(texto: str) -> list[dict]:
    """Cuenta gerundios (M6) y adverbios -mente (CEDIA-011) por folio virtual."""
    palabras = texto.split()
    hallazgos: list[dict] = []
    folio = 1

    for inicio in range(0, len(palabras), _PALABRAS_POR_FOLIO):
        chunk = " ".join(palabras[inicio: inicio + _PALABRAS_POR_FOLIO])

        adverbios = _RE_MENTE.findall(chunk)
        if len(adverbios) > 1:
            primeros = ", ".join(adverbios[:3])
            hallazgos.append({
                "modulo": "CEDIA-011",
                "ubicacion": primeros[:80],
                "error": (
                    f"Folio {folio}: {len(adverbios)} adverbios en -mente "
                    f"({primeros}). Máximo permitido: 1 por folio."
                ),
                "justificacion": "CEDIA-011: el exceso de adverbios en -mente debilita la contundencia judicial.",
                "correccion": "Reemplazar los adverbios en -mente sobrantes por 'con + sustantivo abstracto'.",
                "severidad": "media",
            })

        gerundios = [
            g for g in _RE_GERUND.findall(chunk)
            if g.lower() not in _NOMBRES_NO_GERUNDIO
        ]
        if len(gerundios) > 1:
            primeros_g = ", ".join(gerundios[:3])
            hallazgos.append({
                "modulo": "M6",
                "ubicacion": primeros_g[:80],
                "error": (
                    f"Folio {folio}: {len(gerundios)} gerundios "
                    f"({primeros_g}). Máximo recomendado: 1 por folio."
                ),
                "justificacion": "M6: el exceso de gerundios oscurece el sujeto de la acción judicial.",
                "correccion": "Sustituir los gerundios adicionales por verbos conjugados en el tiempo correspondiente.",
                "severidad": "baja",
            })

        folio += 1

    return hallazgos


def _deduplicar(llm: list[dict], det: list[dict]) -> list[dict]:
    vistos = {h["ubicacion"].lower().strip() for h in llm}
    return llm + [h for h in det if h["ubicacion"].lower().strip() not in vistos]


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM = """Eres CEDIA-ESTILO, experto en registro jurídico-forense colombiano.
Evalúas únicamente el uso correcto del lenguaje forense: mayúsculas, gerundios,
adverbios en -mente, latinismos y denominación formal de sujetos.
No corriges ortografía (Agente 1). No evalúas argumentos (Agente 4).
Solo evalúas si el lenguaje es apropiado para una providencia judicial colombiana.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

PLANTILLA = """Analiza el siguiente fragmento de un documento jurídico disciplinario colombiano.
No corrijas ortografía. Solo evalúa registro, tono y estilo judicial.

DOCUMENTO:
{texto}

SA2.1 — REGISTRO Y CONECTORES

M6 — GERUNDIOS (por folio, ~300 palabras)
Regla: máximo UN gerundio por folio. El exceso oscurece el sujeto de la acción.
Detectar: segundo gerundio en el mismo folio — reportar folio y cantidad.
Gerundios INCORRECTOS a reportar:
- Copulativo como predicado principal: "resolviendo" en lugar de "resolvió" → ALTA
- Posterioridad: gerundio que describe acción posterior a la principal → MEDIA
Gerundios CORRECTOS (no reportar): simultaneidad ("caminando llegó"),
perífrasis verbales ("estaba analizando"), participios en nexo ("siendo así").

M7 — MAYÚSCULAS RAE 2010
Cargos SIEMPRE en minúscula: magistrado, juez, disciplinado, quejoso, defensor,
ponente, instructor, fiscal, secretario — con o sin artículo que los preceda.
  INCORRECTO: "el Magistrado", "la Juez", "el Disciplinado", "el Quejoso".
  CORRECTO: "el magistrado", "la juez", "el disciplinado", "el quejoso".
Instituciones específicas en MAYÚSCULA: Estado, Comisión Nacional de Disciplina
Judicial, Consejo de Estado, Congreso, Procuraduría General de la Nación, Ejército.
Ley en MAYÚSCULA solo en nombre propio: "Ley 1123 de 2007", "Ley 1952 de 2019".
En uso genérico MINÚSCULA: "la ley establece", "según la ley vigente".
Severidad: ALTA en la parte resolutiva; MEDIA en consideraciones; BAJA en antecedentes.

CEDIA-010 — CAPITALIZACIÓN DE CONCEPTOS JURÍDICOS GENÉRICOS
Detectar uso incorrecto de mayúscula inicial en conceptos genéricos:
  "la Falta Disciplinaria" → "la falta disciplinaria"
  "el Proceso Disciplinario" → "el proceso disciplinario"
  "la Sanción Disciplinaria" → "la sanción disciplinaria"
  "el Deber Funcional" → "el deber funcional"
  "falta Gravísima" → "falta gravísima"
  "el Artículo 28" (uso genérico) → "el artículo 28°"
Severidad: MEDIA.

M9 — LATINISMOS EN CURSIVA
Todo latinismo jurídico debe ir en cursiva según RAE y Manual de la CSJ.
Si aparece en redonda (texto plano sin cursiva) → hallazgo BAJA.
Lista canónica obligatoria: a quo, a quem, in dubio pro disciplinado, in dubio pro reo,
prima facie, ratio decidendi, obiter dictum, per se, ex officio, ibidem, supra, infra,
mutatis mutandis, ad hoc, ab initio, inter alia, ex ante, ex post.
Latinismo innecesario cuando existe equivalente castellano más claro → MEDIA.
Latinismo empleado con sentido equivocado → ALTA.

CEDIA-012 — SEÑALES DE ALERTA TEMPRANA (diagnóstico global del fragmento)
Detectar a nivel de todo el fragmento, no por párrafo:
- Más del 70% del texto es síntesis fáctica y menos del 20% es análisis jurídico → MEDIA.
- Ausencia total de análisis jurídico en la sección CONSIDERACIONES → MEDIA.
- Primera persona singular en providencia: "yo considero", "a mi juicio",
  "encuentro que", "me parece" → MEDIA.
  Corrección: "se considera", "la Sala advierte", "se encuentra que".

SA2.2 — ADVERBIOS Y DENOMINACIÓN

CEDIA-011 — ADVERBIOS EN -MENTE (por folio, ~300 palabras)
Regla: máximo UN adverbio en -mente por folio.
Detectar DOS O MÁS en el mismo folio: "claramente", "evidentemente", "notoriamente",
"jurídicamente", "cabalmente", "diligentemente", "debidamente", "inmediatamente".
Severidad: MEDIA si 2 por folio; ALTA si 3 o más en el mismo párrafo.
Sugerir alternativa sin -mente: "con claridad", "con diligencia", "en debida forma",
"de inmediato", "de forma evidente", "con sustento normativo".
CRÍTICO: la alternativa propuesta NO puede contener otro adverbio en -mente.

M14 — UNIFICACIÓN NOMINAL (SA2.2 — sinonimia contextual)
Detectar en el MISMO PÁRRAFO dos o más denominaciones distintas referidas al mismo sujeto:
  disciplinado / abogado / letrado / togado / encartado / investigado / profesional
→ Alertar: inconsistencia nominal — el redactor debe elegir UNA denominación y mantenerla.
Bajo Ley 1123/2007: preferir "togado" o "abogado" — nunca mezclar en el mismo párrafo.
Bajo Ley 1952/2019: preferir "disciplinado" — nunca mezclar con "encartado" o "investigado".

Denominación de personas naturales:
Primera mención: nombre completo. Siguientes: siempre el mismo apellido compuesto.
INCORRECTO: "Diego Armando Henao Montes", luego "Diego Henao", luego "Diego Armando".
CORRECTO: primera mención completa; después siempre "Henao Montes".

Personas jurídicas: denominación completa con naturaleza jurídica siempre idéntica.
INCORRECTO: "Service S.A.S." y "Service S.A.S. EPS" para la misma entidad.

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: error que afecta la validez del acto o identifica incorrectamente un sujeto
- Media: debilita la contundencia judicial o contradice el registro forense estándar
- Baja: error de estilo corregible sin impacto sustancial

REGLA OBLIGATORIA CAMPO "correccion":
Si el párrafo ya contiene un adverbio en -mente, la corrección NO puede introducir otro.
Usar "con + sustantivo abstracto": "técnicamente" → "con rigor técnico".

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{
  "puntaje": <0-100; 100=estilo judicial impecable>,
  "resumen": "<párrafo conciso sobre el nivel de estilo judicial>",
  "hallazgos": [
    {{
      "modulo": "<M6|M7|M9|CEDIA-010|CEDIA-011|CEDIA-012|M14>",
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
    folio_hallazgos = _analizar_folios(texto)
    try:
        datos = await llamar_por_chunks(SYSTEM, lambda chunk: PLANTILLA.format(texto=chunk), texto=texto)
        llm_hallazgos = datos.get("hallazgos", [])
        datos["hallazgos"] = _deduplicar(llm_hallazgos, folio_hallazgos)
        return construir_resultado("ESTILO", datos)
    except Exception as exc:
        return construir_resultado_error("ESTILO", exc)
