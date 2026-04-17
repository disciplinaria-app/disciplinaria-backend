"""
Script de carga de articulos de las Leyes 1123/2007 y 1952/2019 en Supabase.

Estrategia de embeddings (en cascada):
  1. OpenRouter  /v1/embeddings  openai/text-embedding-3-small  (1536 dims)
  2. sentence-transformers local  all-mpnet-base-v2              (768 dims -> padded)
  3. Zeros  [0.0]*1536  — solo para verificar que Supabase recibe datos

Uso:
    python scripts/cargar_leyes.py

Variables en .env (raiz del proyecto):
    OPENROUTER_API_KEY
    SUPABASE_URL
    SUPABASE_SERVICE_KEY    <- JWT service_role (empieza con eyJ)

Archivos en scripts/:
    L1123-2007 (CDA).docx
    L1952-2019 (CGD).docx
"""

import os
import re
import sys
import time
from pathlib import Path

# Stdout sin buffering, UTF-8, para ver prints en tiempo real
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Dependencias obligatorias ─────────────────────────────────────────────────
try:
    import httpx
    from supabase import create_client
    from docx import Document
except ImportError as e:
    print(f"[ERROR] Dependencia faltante: {e}", flush=True)
    print("Ejecuta: pip install supabase python-docx python-dotenv httpx", flush=True)
    sys.exit(1)

# ── Credenciales ──────────────────────────────────────────────────────────────
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_URL   = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY   = os.getenv("SUPABASE_SERVICE_KEY", "")

if not all([OPENROUTER_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("[ERROR] Faltan variables de entorno en .env:", flush=True)
    if not OPENROUTER_KEY: print("  - OPENROUTER_API_KEY", flush=True)
    if not SUPABASE_URL:   print("  - SUPABASE_URL", flush=True)
    if not SUPABASE_KEY:   print("  - SUPABASE_SERVICE_KEY", flush=True)
    sys.exit(1)

supabase   = create_client(SUPABASE_URL, SUPABASE_KEY)
SCRIPTS_DIR = Path(__file__).parent
EMBED_DIM   = 1536

log = lambda msg: print(msg, flush=True)


# ── Estrategias de embedding ──────────────────────────────────────────────────

def _embedding_openrouter(texto: str) -> list[float]:
    """Intento 1: OpenRouter /v1/embeddings."""
    log("    [embed] Llamando OpenRouter...")
    resp = httpx.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://disciplinaria.app",
        },
        json={"model": "openai/text-embedding-3-small", "input": texto[:8000]},
        timeout=30.0,
    )
    log(f"    [embed] Respuesta OpenRouter: HTTP {resp.status_code}")
    if resp.status_code != 200:
        log(f"    [embed] Body: {resp.text[:300]}")
        resp.raise_for_status()
    data = resp.json()
    if "data" not in data:
        raise ValueError(f"Respuesta inesperada: {str(data)[:200]}")
    log("    [embed] OpenRouter OK")
    return data["data"][0]["embedding"]


def _embedding_local(texto: str) -> list[float]:
    """Intento 2: sentence-transformers local (si esta instalado)."""
    from sentence_transformers import SentenceTransformer
    log("    [embed] Usando sentence-transformers local...")
    model = SentenceTransformer("all-mpnet-base-v2")  # 768 dims
    vec = model.encode(texto[:2000]).tolist()
    # Pad a 1536 dims para coincidir con la columna de Supabase
    padded = vec + [0.0] * (EMBED_DIM - len(vec))
    log(f"    [embed] Local OK ({len(vec)} dims, padded a {EMBED_DIM})")
    return padded


def _embedding_zeros() -> list[float]:
    """Intento 3: zeros — solo para verificar el pipeline de Supabase."""
    log("    [embed] ADVERTENCIA: usando embedding de ceros (solo para test de pipeline)")
    return [0.0] * EMBED_DIM


def generar_embedding(texto: str) -> list[float]:
    """Cascada: OpenRouter -> sentence-transformers -> zeros."""
    # Intento 1: OpenRouter
    try:
        return _embedding_openrouter(texto)
    except Exception as e:
        log(f"    [embed] OpenRouter fallo: {e}")

    # Intento 2: sentence-transformers local
    try:
        return _embedding_local(texto)
    except ImportError:
        log("    [embed] sentence-transformers no instalado (pip install sentence-transformers)")
    except Exception as e:
        log(f"    [embed] Local fallo: {e}")

    # Intento 3: zeros (permite verificar que Supabase recibe los datos)
    return _embedding_zeros()


# ── Test rapido de conectividad antes de empezar ──────────────────────────────

def test_conexiones() -> bool:
    log("\n[TEST] Verificando conexiones...")

    # Test OpenRouter embeddings
    log("[TEST] OpenRouter /v1/embeddings...")
    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "openai/text-embedding-3-small", "input": "test"},
            timeout=15.0,
        )
        log(f"       HTTP {resp.status_code}")
        if resp.status_code == 200:
            dims = len(resp.json()["data"][0]["embedding"])
            log(f"       OK — dims={dims}")
        else:
            log(f"       FALLO — {resp.text[:200]}")
    except Exception as e:
        log(f"       ERROR — {e}")

    # Test Supabase (lectura simple)
    log("[TEST] Supabase conexion...")
    try:
        result = supabase.table("articulos_legales").select("id").limit(1).execute()
        log(f"       OK — tabla accesible")
    except Exception as e:
        log(f"       ERROR — {e}")
        log("       Verifica que la tabla 'articulos_legales' exista en Supabase")
        return False

    log("")
    return True


# ── Carga a Supabase ──────────────────────────────────────────────────────────

def insertar_articulo(ley: str, numero: str, titulo: str, contenido: str) -> None:
    emb = generar_embedding(f"Articulo {numero} {titulo}: {contenido}")
    supabase.table("articulos_legales").upsert(
        {
            "ley": ley,
            "numero_articulo": numero,
            "titulo": titulo,
            "contenido": contenido,
            "embedding": emb,
        },
        on_conflict="ley,numero_articulo",
    ).execute()


def texto_desde_docx(ruta: Path) -> str:
    doc = Document(str(ruta))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extraer_articulos(texto: str) -> list[tuple[str, str, str]]:
    patron = (
        r"Art[íi]culo\s+(\d+[°o]?[a-z]?)\.?\s*"
        r"([^.\n]{0,150}\.?)"
        r"(.+?)(?=Art[íi]culo\s+\d+[°o]?|\Z)"
    )
    resultado = []
    for numero, titulo, contenido in re.findall(patron, texto, re.DOTALL | re.IGNORECASE):
        numero    = numero.strip().rstrip("°o")
        titulo    = titulo.strip()[:150]
        contenido = contenido.strip()[:4000]
        if len(contenido) >= 10:
            resultado.append((numero, titulo, contenido))
    return resultado


def cargar_articulos(ley: str, articulos: list[tuple[str, str, str]], esperados: int) -> None:
    cargados = errors = 0
    for i, (numero, titulo, contenido) in enumerate(articulos, 1):
        log(f"  [{i}/{len(articulos)}] Ley {ley} Art. {numero}...")
        try:
            insertar_articulo(ley, numero, titulo, contenido)
            log(f"    OK")
            cargados += 1
        except Exception as exc:
            log(f"    ERROR: {exc}")
            errors += 1
        time.sleep(0.2)
    log(f"\n  => Ley {ley}: {cargados} OK, {errors} errores (esperados ~{esperados})\n")


# ── Procesadores por ley ──────────────────────────────────────────────────────

def procesar_ley(ley_id: str, nombre_archivo: str, esperados: int) -> None:
    ruta = SCRIPTS_DIR / nombre_archivo
    log(f"\nProcesando {nombre_archivo}...")
    if not ruta.exists():
        log(f"  [WARN] Archivo no encontrado: {ruta}")
        return
    log(f"  Leyendo DOCX...")
    texto = texto_desde_docx(ruta)
    log(f"  Texto extraido: {len(texto)} caracteres")
    articulos = extraer_articulos(texto)
    log(f"  Articulos encontrados: {len(articulos)}")
    if not articulos:
        log("  [WARN] Sin articulos — revisa el formato del archivo")
        return
    cargar_articulos(ley_id, articulos, esperados)


# ── Punto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("=" * 58)
    log("  DISCIPLINAR[IA] -- Carga de biblioteca normativa")
    log("=" * 58)

    if not test_conexiones():
        log("[ABORT] Corrige los errores de conexion antes de continuar.")
        sys.exit(1)

    procesar_ley("1123", "L1123-2007 (CDA).docx", esperados=104)
    procesar_ley("1952", "L1952-2019 (CGD).docx", esperados=263)

    log("Carga completa.")
