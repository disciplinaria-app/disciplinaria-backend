"""
Consolidador — Combina los resultados de los 5 agentes en un análisis unificado.
Pondera los puntajes, agrega todos los hallazgos (re-asigna IDs secuenciales,
ordena por nivel_severidad desc) y genera el resumen ejecutivo final mediante
una llamada adicional al LLM.
"""

import asyncio
from .base_agent import extraer_json_respuesta
from models.schemas import Hallazgo, ResultadoAgente, AnalisisResponse, Estadisticas
from config import NORMAS

SYSTEM_CONSOLIDADOR = """Eres el consolidador de un sistema multiagente de revisión de documentos
jurídicos disciplinarios colombianos. Recibirás los análisis de 5 agentes especializados en forma,
estilo judicial, coherencia narrativa, fondo argumentativo y normativa. Produce un resumen ejecutivo
integrado, coherente y accionable. Responde ÚNICAMENTE con un bloque JSON válido."""

PESOS = {
    "FORMA": 0.15,
    "ESTILO": 0.15,
    "COHERENCIA NARRATIVA": 0.20,
    "ARGUMENTACIÓN": 0.25,
    "NORMATIVO": 0.25,
}


PENALIDAD = {"alta": 15, "media": 7, "baja": 2}


def calcular_score_determinista(hallazgos: list[Hallazgo]) -> float:
    """Puntaje global reproducible: 100 − Σ penalidades − penalidad extra por debilidad argumentativa."""
    penalizacion = sum(PENALIDAD.get(h.severidad, 0) for h in hallazgos)
    # Penalidad adicional de 10 pts por cada hallazgo ALTA del agente de argumentación
    alta_arg = sum(1 for h in hallazgos if h.agente == "ARGUMENTACIÓN" and h.severidad == "alta")
    penalizacion += alta_arg * 10
    return max(0.0, round(100.0 - penalizacion, 1))


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


def _generar_resumen_ejecutivo(
    resultados: list[ResultadoAgente], norma: str
) -> tuple[str, list[str], list[str], list[str]]:
    """Construye resumen, errores top, fortalezas y recomendaciones de forma determinista
    desde los datos ya producidos por los 5 agentes — sin llamada LLM adicional."""
    # Errores: primero altas, luego medias; deduplicados por texto exacto
    errores_top = list(dict.fromkeys(
        h.error for r in resultados
        for h in sorted(r.hallazgos, key=lambda h: h.nivel_severidad, reverse=True)
        if h.severidad in ("alta", "media")
    ))[:5]

    # Fortalezas: una por agente, en orden de puntaje descendente
    agentes_ord = sorted(resultados, key=lambda r: r.puntaje, reverse=True)
    todas_fortalezas = list(dict.fromkeys(
        f for r in agentes_ord for f in r.fortalezas
    ))[:3]

    # Recomendaciones: de los agentes con menor puntaje primero
    agentes_asc = sorted(resultados, key=lambda r: r.puntaje)
    todas_recs = list(dict.fromkeys(
        rec for r in agentes_asc for rec in r.recomendaciones
    ))[:4]

    # Resumen: agente con menor puntaje da el tono + conteo de hallazgos por severidad
    alta = sum(1 for r in resultados for h in r.hallazgos if h.severidad == "alta")
    media = sum(1 for r in resultados for h in r.hallazgos if h.severidad == "media")
    baja = sum(1 for r in resultados for h in r.hallazgos if h.severidad == "baja")
    critico = agentes_asc[0] if agentes_asc else None
    base = critico.resumen if critico and critico.resumen else ""
    resumen = (
        f"{base} "
        f"Se detectaron {alta} hallazgo(s) de alta severidad, {media} de media y {baja} de baja "
        f"en los cinco módulos de revisión (forma, estilo, coherencia, argumentación y normativo)."
    ).strip()

    return resumen, errores_top, todas_fortalezas, todas_recs


async def consolidar(resultados: list[ResultadoAgente], norma: str) -> AnalisisResponse:
    hallazgos = _agregar_hallazgos(resultados)
    puntaje = _puntaje_ponderado(resultados)
    nivel = _calcular_nivel(puntaje)
    estadisticas = _construir_estadisticas(resultados, norma, hallazgos)

    resumen, errores, fortalezas, recomendaciones = _generar_resumen_ejecutivo(
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
