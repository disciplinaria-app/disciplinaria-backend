import json
import re
import httpx
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL
from models.schemas import Hallazgo, ResultadoAgente

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


async def llamar_openrouter(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Realiza una llamada async a la API de OpenRouter."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://disciplinaria.app",
        "X-Title": "DISCIPLINAR[IA]",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def extraer_json_respuesta(raw: str) -> dict:
    """Extrae el bloque JSON de la respuesta del modelo."""
    match = re.search(r"```json\s*([\s\S]*?)\s*```", raw)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No se encontró JSON válido en la respuesta: {raw[:200]}")


def _nivel_severidad(sev: str) -> int:
    return {"alta": 3, "media": 2, "baja": 1}.get(sev, 1)


def _construir_hallazgos(nombre_agente: str, raw_hallazgos: list[dict]) -> list[Hallazgo]:
    """Convierte la lista cruda del LLM en objetos Hallazgo validados."""
    hallazgos = []
    for i, h in enumerate(raw_hallazgos, start=1):
        sev = str(h.get("severidad", "baja")).lower()
        if sev not in ("alta", "media", "baja"):
            sev = "baja"
        hallazgos.append(Hallazgo(
            id=i,
            modulo=str(h.get("modulo", "M0")),
            agente=nombre_agente,
            ubicacion=str(h.get("ubicacion", "")),
            error=str(h.get("error", "")),
            justificacion=str(h.get("justificacion", "")),
            correccion=str(h.get("correccion", "")),
            severidad=sev,
            nivel_severidad=_nivel_severidad(sev),
        ))
    return hallazgos


def construir_resultado(nombre_agente: str, datos: dict) -> ResultadoAgente:
    hallazgos = _construir_hallazgos(nombre_agente, datos.get("hallazgos", []))
    return ResultadoAgente(
        agente=nombre_agente,
        puntaje=float(datos.get("puntaje", 50)),
        resumen=datos.get("resumen", ""),
        hallazgos=hallazgos,
        fortalezas=datos.get("fortalezas", []),
        recomendaciones=datos.get("recomendaciones", []),
    )


def construir_resultado_error(nombre_agente: str, exc: Exception) -> ResultadoAgente:
    """Retorna un resultado de fallo graceful cuando el agente falla."""
    return ResultadoAgente(
        agente=nombre_agente,
        puntaje=0.0,
        resumen=f"Error al procesar el agente {nombre_agente}: {exc}",
        hallazgos=[
            Hallazgo(
                id=1,
                modulo="ERROR",
                agente=nombre_agente,
                ubicacion="–",
                error=str(exc),
                justificacion="El agente no pudo completar el análisis.",
                correccion="Reintentar o revisar manualmente.",
                severidad="alta",
                nivel_severidad=3,
            )
        ],
        fortalezas=[],
        recomendaciones=["Revisar manualmente este aspecto del documento."],
    )
