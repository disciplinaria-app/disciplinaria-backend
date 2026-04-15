"""
Consolidador — Combina los resultados de los 5 agentes en un análisis unificado.
Pondera los puntajes, deduplica hallazgos y genera el resumen ejecutivo final
mediante una llamada adicional al LLM.
"""

import asyncio
from .base_agent import llamar_openrouter, extraer_json_respuesta
from models.schemas import ResultadoAgente, AnalisisResponse, Estadisticas
from config import NORMAS

SYSTEM_CONSOLIDADOR = """Eres el consolidador de un sistema multiagente de revisión de documentos
jurídicos disciplinarios colombianos. Recibirás los análisis de 5 agentes especializados en forma,
estilo judicial, coherencia narrativa, fondo argumentativo y normativa. Produce un resumen ejecutivo
integrado, coherente y accionable. Responde ÚNICAMENTE con un bloque JSON válido."""

PESOS = {
    "FORMA": 0.15,
    "ESTILO JUDICIAL": 0.15,
    "COHERENCIA NARRATIVA": 0.20,
    "FONDO ARGUMENTATIVO": 0.25,
    "NORMATIVO": 0.25,
}


def _calcular_nivel(puntaje: float) -> str:
    if puntaje >= 85:
        return "EXCELENTE"
    elif puntaje >= 70:
        return "BUENO"
    elif puntaje >= 55:
        return "ACEPTABLE"
    elif puntaje >= 40:
        return "REGULAR"
    return "DEFICIENTE"


def _puntaje_ponderado(resultados: list[ResultadoAgente]) -> float:
    total_peso = 0.0
    puntaje_acumulado = 0.0
    for r in resultados:
        peso = PESOS.get(r.agente, 0.20)
        puntaje_acumulado += r.puntaje * peso
        total_peso += peso
    if total_peso == 0:
        return 0.0
    return round(puntaje_acumulado / total_peso, 1)


def _construir_estadisticas(
    resultados: list[ResultadoAgente], norma: str
) -> Estadisticas:
    puntajes = [r.puntaje for r in resultados]
    exitosos = [r for r in resultados if r.puntaje > 0 or r.resumen and "Error" not in r.resumen]
    distribucion = {r.agente: r.puntaje for r in resultados}
    return Estadisticas(
        total_agentes=len(resultados),
        agentes_exitosos=len(exitosos),
        puntaje_promedio=round(sum(puntajes) / len(puntajes), 1) if puntajes else 0,
        puntaje_maximo=max(puntajes) if puntajes else 0,
        puntaje_minimo=min(puntajes) if puntajes else 0,
        norma_aplicada=NORMAS.get(norma, norma),
        distribucion_puntajes=distribucion,
    )


async def _generar_resumen_ejecutivo(resultados: list[ResultadoAgente], norma: str) -> tuple[str, list[str], list[str], list[str]]:
    """Llama al LLM para generar resumen, errores, fortalezas y recomendaciones consolidados."""
    agentes_txt = "\n\n".join(
        f"### {r.agente} (Puntaje: {r.puntaje}/100)\n"
        f"Resumen: {r.resumen}\n"
        f"Errores: {'; '.join(r.errores) or 'Ninguno'}\n"
        f"Fortalezas: {'; '.join(r.fortalezas) or 'Ninguna'}\n"
        f"Recomendaciones: {'; '.join(r.recomendaciones) or 'Ninguna'}"
        for r in resultados
    )
    prompt = f"""Consolida los siguientes análisis de 5 agentes especializados sobre un documento
disciplinario colombiano bajo la {NORMAS.get(norma, norma)}:

{agentes_txt}

Genera una consolidación inteligente que:
1. Integre los hallazgos más importantes de todos los agentes
2. Elimine duplicados y agrupe hallazgos relacionados
3. Priorice los errores más graves
4. Formule recomendaciones accionables y específicas

Responde con este JSON exacto:
```json
{{
  "resumen": "<resumen ejecutivo consolidado de 3-5 oraciones>",
  "errores": ["<top error 1>", "<top error 2>", "<top error 3>", "<top error 4>", "<top error 5>"],
  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>", "<fortaleza 3>"],
  "recomendaciones": ["<recomendación 1>", "<recomendación 2>", "<recomendación 3>", "<recomendación 4>"]
}}
```"""
    try:
        raw = await llamar_openrouter(SYSTEM_CONSOLIDADOR, prompt)
        datos = extraer_json_respuesta(raw)
        return (
            datos.get("resumen", ""),
            datos.get("errores", []),
            datos.get("fortalezas", []),
            datos.get("recomendaciones", []),
        )
    except Exception as exc:
        # Fallback: agregar resultados crudos
        todos_errores = list({e for r in resultados for e in r.errores})[:5]
        todas_fortalezas = list({f for r in resultados for f in r.fortalezas})[:3]
        todas_recs = list({rec for r in resultados for rec in r.recomendaciones})[:4]
        resumen = " | ".join(r.resumen for r in resultados if r.resumen)[:500]
        return resumen, todos_errores, todas_fortalezas, todas_recs


async def consolidar(resultados: list[ResultadoAgente], norma: str) -> AnalisisResponse:
    puntaje = _puntaje_ponderado(resultados)
    nivel = _calcular_nivel(puntaje)
    estadisticas = _construir_estadisticas(resultados, norma)

    resumen, errores, fortalezas, recomendaciones = await _generar_resumen_ejecutivo(
        resultados, norma
    )

    return AnalisisResponse(
        puntaje=puntaje,
        nivel=nivel,
        resumen=resumen,
        errores=errores,
        fortalezas=fortalezas,
        recomendaciones=recomendaciones,
        estadisticas=estadisticas,
        detalle_agentes=resultados,
    )
