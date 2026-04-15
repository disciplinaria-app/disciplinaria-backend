import json
import re
import httpx
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL
from models.schemas import ResultadoAgente

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


async def llamar_openrouter(system_prompt: str, user_prompt: str) -> str:
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
        "max_tokens": 2000,
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
    # Intentar encontrar bloque ```json ... ```
    match = re.search(r"```json\s*([\s\S]*?)\s*```", raw)
    if match:
        return json.loads(match.group(1))
    # Intentar encontrar JSON directo entre llaves
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No se encontró JSON válido en la respuesta: {raw[:200]}")


def construir_resultado(nombre_agente: str, datos: dict) -> ResultadoAgente:
    return ResultadoAgente(
        agente=nombre_agente,
        puntaje=float(datos.get("puntaje", 50)),
        resumen=datos.get("resumen", ""),
        errores=datos.get("errores", []),
        fortalezas=datos.get("fortalezas", []),
        recomendaciones=datos.get("recomendaciones", []),
    )
