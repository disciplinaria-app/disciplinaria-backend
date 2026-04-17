"""
Utilidades de búsqueda vectorial en Supabase para la biblioteca normativa.

REQUISITO: Ejecutar este SQL en el Editor SQL de Supabase antes de usar:

    CREATE OR REPLACE FUNCTION match_articulos(
        query_embedding VECTOR(1536),
        match_ley       TEXT,
        match_count     INT     DEFAULT 5,
        match_threshold FLOAT   DEFAULT 0.75
    )
    RETURNS TABLE (
        numero_articulo TEXT,
        titulo          TEXT,
        contenido       TEXT,
        similitud       FLOAT
    )
    LANGUAGE SQL STABLE AS $$
        SELECT numero_articulo, titulo, contenido,
               1 - (embedding <=> query_embedding) AS similitud
        FROM   articulos_legales
        WHERE  ley = match_ley
          AND  1 - (embedding <=> query_embedding) > match_threshold
        ORDER BY embedding <=> query_embedding
        LIMIT match_count;
    $$;
"""

import httpx
from config import (
    SUPABASE_URL, SUPABASE_SERVICE_KEY,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, EMBEDDING_MODEL,
)

_SUPABASE_DISPONIBLE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY and OPENROUTER_API_KEY)


async def _generar_embedding(texto: str) -> list[float]:
    """Genera un embedding via OpenRouter (openai/text-embedding-3-small)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{OPENROUTER_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": EMBEDDING_MODEL, "input": texto[:8000]},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def buscar_articulos(
    query: str,
    ley: str,
    limite: int = 5,
    umbral: float = 0.75,
) -> list[dict]:
    """
    Busca artículos similares en Supabase mediante búsqueda vectorial.
    Retorna lista de dicts con: numero_articulo, titulo, contenido, similitud.
    Retorna lista vacía si Supabase no está configurado.
    """
    if not _SUPABASE_DISPONIBLE:
        return []

    # Normalizar clave de ley para la tabla
    ley_key = {"ley_1123": "1123", "ley_1952": "1952"}.get(ley, ley)

    try:
        embedding = await _generar_embedding(query)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/match_articulos",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "query_embedding": embedding,
                    "match_ley": ley_key,
                    "match_count": limite,
                    "match_threshold": umbral,
                },
            )
            resp.raise_for_status()
            return resp.json() or []
    except Exception:
        return []


async def verificar_articulo(numero: str, ley: str) -> dict | None:
    """
    Recupera el texto real de un artículo específico por número y ley.
    Retorna None si no se encuentra o Supabase no está disponible.
    """
    if not _SUPABASE_DISPONIBLE:
        return None

    ley_key = {"ley_1123": "1123", "ley_1952": "1952"}.get(ley, ley)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/articulos_legales",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
                params={
                    "ley": f"eq.{ley_key}",
                    "numero_articulo": f"eq.{numero}",
                    "select": "numero_articulo,titulo,contenido",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0] if data else None
    except Exception:
        return None
