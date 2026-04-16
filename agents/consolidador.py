"""
Consolidador — Combina los resultados de los 5 agentes en un análisis unificado.
Pondera los puntajes, agrega todos los hallazgos (re-asigna IDs secuenciales,
ordena por nivel_severidad desc) y genera el resumen ejecutivo final mediante
una llamada adicional al LLM.
"""

import asyncio
from .base_agent import llamar_openrouter, extraer_json_respuesta
from models.schemas import Hallazgo, ResultadoAgente, AnalisisResponse, Estadisticas
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


def _agregar_hallazgos(resultados: list[ResultadoAgente]) -> list[Hallazgo]:
    """Recoge todos los hallazgos de los 5 agentes, los ordena por severidad desc
    y les reasigna IDs secuenciales globales."""
    todos: list[Hallazgo] = []
    for r in resultados:
        todos.extend(r.hallazgos)

    # Ordenar: alta (3) → media (2) → baja (1)
    todos.sort(key=lambda h: h.nivel_severidad, reverse=True)

    # Reasignar IDs secuenciales
    return [
        Hallazgo(**{**h.model_dump(), "id": i})
        for i, h in enumerate(todos, 1)
    ]


def _construir_estadisticas(
    resultados: list[ResultadoAgente],
    norma: str,
    hallazgos: list[Hallazgo],
) -> Estadisticas:
    puntajes = [r.puntaje for r in resultados]
    exitosos = [r for r in resultados if r.puntaje > 0 or (r.resumen and "Error" not in r.resumen)]
    distribucion = {r.agente: r.puntaje for r in resultados}
    conteo_severidad = {
        "alta": sum(1 for h in hallazgos if h.severidad == "alta"),
        "media": sum(1 for h in hallazgos if h.severidad == "media"),
        "baja": sum(1 for h in hallazgos if h.severidad == "baja"),
    }
    return Estadisticas(
        total_agentes=len(resultados),
        agentes_exitosos=len(exitosos),
        puntaje_promedio=round(sum(puntajes) / len(puntajes), 1) if puntajes else 0,
        puntaje_maximo=max(puntajes) if puntajes else 0,
        puntaje_minimo=min(puntajes) if puntajes else 0,
        norma_aplicada=NORMAS.get(norma, norma),
        distribucion_puntajes=distribucion,
        conteo_severidad=conteo_severidad,
    )


async def _generar_resumen_ejecutivo(
    resultados: list[ResultadoAgente], norma: str
) -> tuple[str, list[str], list[str], list[str]]:
    """Llama al LLM para generar resumen, errores top, fortalezas y recomendaciones consolidados."""
    agentes_txt = "\n\n".join(
        f"### {r.agente} (Puntaje: {r.puntaje}/100)\n"
        f"Resumen: {r.resumen}\n"
        f"Hallazgos de alta severidad: "
        f"{'; '.join(h.error for h in r.hallazgos if h.severidad == 'alta') or 'Ninguno'}\n"
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
3. Priorice los errores más graves (alta severidad primero)
4. Formule recomendaciones accionables y específicas

Responde con este JSON exacto:
```json
{{
  "resumen": "<resumen ejecutivo consolidado de 3-5 oraciones>",
  "errores": ["<error crítico 1>", "<error crítico 2>", "<error crítico 3>", "<error crítico 4>", "<error crítico 5>"],
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
    except Exception:
        # Fallback sin LLM: construir desde hallazgos directamente
        errores_top = list(dict.fromkeys(
            h.error for r in resultados
            for h in r.hallazgos if h.severidad == "alta"
        ))[:5]
        todas_fortalezas = list(dict.fromkeys(
            f for r in resultados for f in r.fortalezas
        ))[:3]
        todas_recs = list(dict.fromkeys(
            rec for r in resultados for rec in r.recomendaciones
        ))[:4]
        resumen = " | ".join(r.resumen for r in resultados if r.resumen)[:500]
        return resumen, errores_top, todas_fortalezas, todas_recs


async def consolidar(resultados: list[ResultadoAgente], norma: str) -> AnalisisResponse:
    puntaje = _puntaje_ponderado(resultados)
    nivel = _calcular_nivel(puntaje)
    hallazgos = _agregar_hallazgos(resultados)
    estadisticas = _construir_estadisticas(resultados, norma, hallazgos)

    resumen, errores, fortalezas, recomendaciones = await _generar_resumen_ejecutivo(
        resultados, norma
    )

    return AnalisisResponse(
        puntaje=puntaje,
        nivel=nivel,
        resumen=resumen,
        errores=errores,
        hallazgos=hallazgos,
        fortalezas=fortalezas,
        recomendaciones=recomendaciones,
        estadisticas=estadisticas,
        detalle_agentes=resultados,
    )
