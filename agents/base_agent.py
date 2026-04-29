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
        # lt_offset / lt_length solo existen en hallazgos de LanguageTool;
        # para los del LLM el dict no los incluye → get() retorna None.
        raw_offset = h.get("lt_offset")
        raw_length = h.get("lt_length")
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
            lt_offset=int(raw_offset) if raw_offset is not None else None,
            lt_length=int(raw_length) if raw_length is not None else None,
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


def split_chunks(texto: str, chunk_words: int = 3000, overlap_words: int = 200) -> list[str]:
    """Divide el texto en fragmentos de chunk_words palabras con solapamiento."""
    words = texto.split()
    if len(words) <= chunk_words:
        return [texto]
    chunks: list[str] = []
    step = chunk_words - overlap_words
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_words])
        chunks.append(chunk)
        if i + chunk_words >= len(words):
            break
    return chunks


def deduplicar_hallazgos(hallazgos: list[dict]) -> list[dict]:
    """Elimina hallazgos duplicados usando los primeros 60 caracteres de ubicacion como clave."""
    vistos: set[str] = set()
    resultado: list[dict] = []
    for h in hallazgos:
        key = h.get("ubicacion", "")[:60].lower()
        if key not in vistos:
            vistos.add(key)
            resultado.append(h)
    return resultado


async def llamar_por_chunks(
    system_prompt: str,
    build_prompt,
    texto: str,
    max_tokens: int = 4000,
) -> dict:
    """Llama al LLM en chunks de 3000 palabras con 200 de solapamiento y consolida hallazgos."""
    chunks = split_chunks(texto)
    todos_hallazgos: list[dict] = []
    puntajes: list[float] = []
    ultimo_resumen = ""
    fortalezas: list[str] = []
    recomendaciones: list[str] = []

    for chunk in chunks:
        prompt = build_prompt(chunk)
        try:
            raw = await llamar_openrouter(system_prompt, prompt, max_tokens=max_tokens)
            datos = extraer_json_respuesta(raw)
            todos_hallazgos.extend(datos.get("hallazgos", []))
            puntajes.append(float(datos.get("puntaje", 50)))
            ultimo_resumen = datos.get("resumen", ultimo_resumen)
            fortalezas.extend(datos.get("fortalezas", []))
            recomendaciones.extend(datos.get("recomendaciones", []))
        except Exception:
            pass

    return {
        "puntaje": sum(puntajes) / len(puntajes) if puntajes else 50.0,
        "resumen": ultimo_resumen,
        "hallazgos": deduplicar_hallazgos(todos_hallazgos)[:10],
        "fortalezas": list(dict.fromkeys(fortalezas))[:5],
        "recomendaciones": list(dict.fromkeys(recomendaciones))[:5],
    }


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
