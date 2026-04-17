"""
Script de carga de articulos de las Leyes 1123/2007 y 1952/2019 en Supabase
con embeddings vectoriales (text-embedding-3-small, 1536 dims).

Uso:
    pip install supabase openai python-docx python-dotenv pypdf
    python scripts/cargar_leyes.py

Variables de entorno requeridas (.env en la raiz del proyecto):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY    <- JWT service_role de Supabase (empieza con eyJ)
    OPENAI_API_KEY

Archivos requeridos en scripts/:
    L1123-2007 (CDA).docx   <- Ley 1123/2007, formato Word (.docx)
    L1952-2019 (CGD).docx   <- Ley 1952/2019, formato Word (.docx)
"""

import io
import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Forzar UTF-8 en stdout (evita errores cp1252 en Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Cargar .env desde la raiz del proyecto
load_dotenv(Path(__file__).parent.parent / ".env")

try:
    from supabase import create_client
    from openai import OpenAI
    from docx import Document
except ImportError as e:
    print(f"Dependencia faltante: {e}")
    print("Ejecuta: pip install supabase openai python-docx python-dotenv")
    sys.exit(1)

# ── Clientes ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_KEY]):
    print("[ERROR] Faltan variables de entorno.")
    print("  Crea .env en la raiz del proyecto con:")
    print("  SUPABASE_URL=https://xxxx.supabase.co")
    print("  SUPABASE_SERVICE_KEY=eyJ...  (service_role JWT, no la anon key)")
    print("  OPENAI_API_KEY=sk-...")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_c = OpenAI(api_key=OPENAI_KEY)

SCRIPTS_DIR = Path(__file__).parent


# ── Utilidades ────────────────────────────────────────────────────────────────

def generar_embedding(texto: str) -> list[float]:
    resp = openai_c.embeddings.create(
        model="text-embedding-3-small",
        input=texto[:8000],
    )
    return resp.data[0].embedding


def insertar_articulo(ley: str, numero: str, titulo: str, contenido: str) -> None:
    emb = generar_embedding(f"Articulo {numero} - {titulo}: {contenido}")
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
    """Extrae (numero, titulo, contenido) de texto normativo plano."""
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
    cargados = 0
    for numero, titulo, contenido in articulos:
        try:
            insertar_articulo(ley, numero, titulo, contenido)
            print(f"  [Ley {ley}] Articulo {numero} -- OK")
            cargados += 1
            time.sleep(0.3)  # evitar rate-limit de OpenAI embeddings
        except Exception as exc:
            print(f"  [Ley {ley}] Articulo {numero} -- ERROR: {exc}")
    print(f"  => Ley {ley}: {cargados} articulos cargados (esperados ~{esperados})\n")


# ── Ley 1123/2007 ─────────────────────────────────────────────────────────────

def procesar_ley_1123() -> None:
    print("Procesando Ley 1123 de 2007...")
    ruta = SCRIPTS_DIR / "L1123-2007 (CDA).docx"
    if not ruta.exists():
        print(f"  [WARN] No se encontro: {ruta.name}")
        print("  Convierte L1123-2007 (CDA).doc a .docx: Word > Guardar como > Documento Word")
        return
    print(f"  -> Leyendo: {ruta.name}")
    texto = texto_desde_docx(ruta)
    articulos = extraer_articulos(texto)
    if not articulos:
        print("  [WARN] No se encontraron articulos en el archivo")
        return
    print(f"  -> {len(articulos)} articulos encontrados. Subiendo a Supabase...")
    cargar_articulos("1123", articulos, esperados=104)


# ── Ley 1952/2019 ─────────────────────────────────────────────────────────────

def procesar_ley_1952() -> None:
    print("Procesando Ley 1952 de 2019...")
    ruta = SCRIPTS_DIR / "L1952-2019 (CGD).docx"
    if not ruta.exists():
        print(f"  [WARN] No se encontro: {ruta.name}")
        return
    print(f"  -> Leyendo: {ruta.name}")
    texto = texto_desde_docx(ruta)
    articulos = extraer_articulos(texto)
    if not articulos:
        print("  [WARN] No se encontraron articulos en el archivo")
        return
    print(f"  -> {len(articulos)} articulos encontrados. Subiendo a Supabase...")
    cargar_articulos("1952", articulos, esperados=263)


# ── Punto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 58)
    print("  DISCIPLINAR[IA] -- Carga de biblioteca normativa")
    print("=" * 58)
    procesar_ley_1123()
    procesar_ley_1952()
    print("Carga completa.")
