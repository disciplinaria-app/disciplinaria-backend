"""
Agente 5 — NORMATIVO
Cubre: CEDIA-003 (norma sin verificar contenido real), CEDIA-004 (artículo
       inexistente), CEDIA-014 (error de favorabilidad), CEDIA-016 (art. 29
       Ley 1123 = INCOMPATIBILIDADES, no deberes) + M18 (citas jurisprudenciales
       incompletas), M19 patrón 3 (verbo sin objeto directo — "incurrió en
       previsto en..." sin sustantivo rector).

Usa búsqueda vectorial en Supabase para verificar el texto real de los artículos
citados. Si Supabase no está configurado, opera en modo solo-LLM.
"""

import re
from .base_agent import llamar_openrouter, extraer_json_respuesta, construir_resultado, construir_resultado_error
from .supabase_utils import verificar_articulo, buscar_articulos
from models.schemas import ResultadoAgente
from config import NORMAS

SYSTEM = """Eres CEDIA-NORMATIVO, experto verificador de citas normativas en documentos
disciplinarios colombianos. Validas que cada artículo citado EXISTA en la ley indicada,
que el contenido invocado CORRESPONDA al texto real, y que la norma aplicada sea la
CORRECTA para el tipo de sujeto disciplinado.
REGLA ABSOLUTA: jamás inventes el contenido de un artículo. Si no puedes verificarlo,
reporta "artículo no verificado" como hallazgo de severidad media.
Responde ÚNICAMENTE con JSON válido, sin texto adicional."""

_PATRON_ARTICULO = re.compile(
    r"art[íi]culo\s+(\d+[°o]?[a-z]?)\s*(?:de\s+(?:la\s+)?[Ll]ey\s+(\d+))?",
    re.IGNORECASE,
)

_NORMA_CANONICA = {
    "ley_1123": "1123", "1123": "1123",
    "ley_1952": "1952", "1952": "1952",
    "734":      "734",
}


async def _construir_contexto_supabase(texto: str, norma: str) -> str:
    """Extrae referencias normativas del texto y las verifica en Supabase."""
    ley = _NORMA_CANONICA.get(norma, norma)
    refs = _PATRON_ARTICULO.findall(texto[:8000])
    if not refs:
        return ""

    lineas = ["CONTENIDO REAL DE ARTÍCULOS SEGÚN BASE NORMATIVA SUPABASE:"]
    vistos = set()
    for num, ley_ref in refs[:10]:
        ley_buscar = ley_ref if ley_ref else ley
        clave = (num, ley_buscar)
        if clave in vistos:
            continue
        vistos.add(clave)

        art = await verificar_articulo(num, ley_buscar)
        if art:
            lineas.append(
                f"  Art. {art['numero_articulo']} Ley {ley_buscar}: "
                f"{art.get('titulo', '')} — {art.get('contenido', '')[:300]}"
            )
        else:
            lineas.append(f"  Art. {num} Ley {ley_buscar}: NO ENCONTRADO EN BASE NORMATIVA")

    return "\n".join(lineas) if len(lineas) > 1 else ""


def _plantilla(norma_nombre: str, contexto_supabase: str) -> str:
    supabase_bloque = (
        f"\nCONTEXTO VERIFICADO EN BASE NORMATIVA:\n{contexto_supabase}\n"
        if contexto_supabase
        else "\n[Base normativa no disponible — usar conocimiento propio con cautela]\n"
    )
    return f"""Analiza el siguiente documento jurídico disciplinario colombiano bajo la {norma_nombre}.
{supabase_bloque}
DOCUMENTO:
{{texto}}

CRITERIOS DE ANÁLISIS:

CEDIA-004 · ARTÍCULO INEXISTENTE O NUMERACIÓN INCORRECTA:
- Cita de artículo cuyo número no existe en la ley (error de alta severidad)
- Transposición de números: el deber está en art. 28 pero se cita el art. 29
- REGLA CRÍTICA CEDIA-016 · LEY 1123/2007:
  * Artículo 28 = DEBERES PROFESIONALES (21 deberes del abogado)
  * Artículo 29 = INCOMPATIBILIDADES (no deberes) — si se cita como fuente
    de un deber: ERROR DE ALTA SEVERIDAD
  * Artículos 30-39 = tipos de faltas disciplinarias
  * Artículo 40 = sanciones (censura, multa, suspensión, exclusión)
  * Artículo 73 = suspensión (1 a 12 meses) — no el art. 43
  * La Ley 1123 NO tiene faltas gravísimas/graves/leves (solo la Ley 1952/734)
  * Términos exclusivos Ley 1123: QUEJOSO, DEBERES PROFESIONALES, FALTAS ÉTICAS

CEDIA-003 · NORMA SIN VERIFICAR CONTENIDO REAL:
- El artículo existe pero su contenido no corresponde a lo que se invoca
- Ejemplo: citar art. 37 para "debida diligencia" cuando ese artículo regula
  otra materia
- Usar el contexto de Supabase para verificar; si no está disponible, alertar

CEDIA-014 · ERROR DE FAVORABILIDAD NORMATIVA:
- Para hechos anteriores al 29/06/2021: puede aplicarse Ley 734/2002
  (ultraactiva) si es más favorable; no es obligatorio aplicar Ley 1952
- Para hechos posteriores al 29/06/2021: aplica Ley 1952/2019
- Error: aplicar Ley 1952 retroactivamente a hechos anteriores sin análisis
  de favorabilidad
- Error: mezclar artículos de Ley 734 y Ley 1952 sin justificar la transición

M18 · CITAS JURISPRUDENCIALES INCOMPLETAS:
- Sentencias sin número de radicado, fecha O corporación
- "La jurisprudencia ha establecido reiteradamente" sin cita específica
- Artículos sin identificar la ley de origen

M19 PATRÓN 3 · VERBO SIN OBJETO DIRECTO:
- "incurrió en previsto en" sin el sustantivo rector que complete el sentido
- "sancionado según" sin indicar el artículo concreto
- Verbo de imputación sin complemento normativo completo

CRITERIOS DE SEVERIDAD CNDJ:
- Alta: artículo inexistente, norma equivocada para el sujeto disciplinado,
        o confusión art. 28/29 Ley 1123 — generan nulidad o recurso exitoso
- Media: artículo existente pero invocado para materia incorrecta, o cita
         incompleta que debilita la fundamentación
- Baja: cita parcialmente incompleta corregible sin afectar el fondo

Responde con este JSON exacto (máximo 10 hallazgos):
```json
{{{{
  "puntaje": <0-100; 100=aplicación normativa impecable>,
  "resumen": "<párrafo conciso sobre la corrección normativa del documento>",
  "hallazgos": [
    {{{{
      "modulo": "<CEDIA-003|CEDIA-004|CEDIA-014|CEDIA-016|M18|M19>",
      "ubicacion": "<cita textual breve del fragmento, máx 80 caracteres>",
      "error": "<descripción de la discrepancia normativa>",
      "justificacion": "<texto real del artículo según base normativa o criterio CEDIA>",
      "correccion": "<redacción correcta de la cita o artículo correcto a invocar>",
      "severidad": "<alta|media|baja>"
    }}}}
  ],
  "fortalezas": ["<aspectos normativos correctamente aplicados>"],
  "recomendaciones": ["<correcciones normativas prioritarias>"]
}}}}
```"""


async def ejecutar(texto: str, norma: str) -> ResultadoAgente:
    norma_nombre = NORMAS.get(norma, norma)
    contexto_supabase = await _construir_contexto_supabase(texto, norma)
    plantilla = _plantilla(norma_nombre, contexto_supabase)
    prompt = plantilla.format(texto=texto[:8000])

    try:
        raw = await llamar_openrouter(SYSTEM, prompt, max_tokens=4000)
        datos = extraer_json_respuesta(raw)
        return construir_resultado("NORMATIVO", datos)
    except Exception as exc:
        return construir_resultado_error("NORMATIVO", exc)
