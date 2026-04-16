"""
Script de carga de artículos de las Leyes 1123/2007 y 1952/2019 en Supabase
con embeddings vectoriales (text-embedding-3-small, 1536 dims).

Uso:
    pip install supabase openai python-docx python-dotenv
    python scripts/cargar_leyes.py

Variables de entorno requeridas:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    OPENAI_API_KEY

Archivos esperados en scripts/:
    LEY_1123_DE_2007.doc    (HTML con encoding UTF-16)
    L1952-2019__CGD_.docx   (Word estándar)
"""

import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import create_client
    from openai import OpenAI
    from docx import Document
except ImportError as e:
    print(f"Dependencia faltante: {e}")
    print("Ejecuta: pip install supabase openai python-docx python-dotenv")
    sys.exit(1)

# ── Clientes ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_KEY]):
    print("❌ Faltan variables de entorno: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai   = OpenAI(api_key=OPENAI_KEY)

SCRIPTS_DIR = Path(__file__).parent


def generar_embedding(texto: str) -> list[float]:
    resp = openai.embeddings.create(
        model="text-embedding-3-small",
        input=texto[:8000],
    )
    return resp.data[0].embedding


def insertar_articulo(ley: str, numero: str, titulo: str, contenido: str) -> bool:
    embedding = generar_embedding(f"Artículo {numero} - {titulo}: {contenido}")
    supabase.table("articulos_legales").upsert({
        "ley": ley,
        "numero_articulo": numero,
        "titulo": titulo,
        "contenido": contenido,
        "embedding": embedding,
    }, on_conflict="ley,numero_articulo").execute()
    return True


# ── Ley 1123/2007 (HTML UTF-16 en .doc) ──────────────────────────────────────

def procesar_ley_1123():
    ruta = SCRIPTS_DIR / "LEY_1123_DE_2007.doc"
    if not ruta.exists():
        print(f"⚠️  No se encontró {ruta} — saltando Ley 1123")
        return

    print("\n📖 Procesando Ley 1123 de 2007...")
    with open(ruta, encoding="utf-16") as f:
        content = f.read()

    # Limpiar HTML
    texto = re.sub(r"<[^>]+>", " ", content)
    texto = re.sub(r"&nbsp;",  " ", texto)
    texto = re.sub(r"&amp;",   "&", texto)
    texto = re.sub(r"&lt;",    "<", texto)
    texto = re.sub(r"&gt;",    ">", texto)
    texto = re.sub(r"\s+",     " ", texto).strip()

    # Extraer artículos  (patrón: "Artículo N°. Título. Contenido")
    patron = r"Art[íi]culo\s+(\d+[°o]?[a-z]?)\.?\s*([^.]{0,120}\.?)(.+?)(?=Art[íi]culo\s+\d+[°o]?|$)"
    articulos = re.findall(patron, texto, re.DOTALL | re.IGNORECASE)

    cargados = 0
    for numero, titulo, contenido in articulos:
        numero   = numero.strip().rstrip("°o")
        titulo   = titulo.strip()[:120]
        contenido = contenido.strip()[:4000]
        if len(contenido) < 10:
            continue
        try:
            insertar_articulo("1123", numero, titulo, contenido)
            print(f"  [Ley 1123] Artículo {numero} — OK")
            cargados += 1
            time.sleep(0.3)   # evitar rate-limit de OpenAI
        except Exception as e:
            print(f"  [Ley 1123] Artículo {numero} — ERROR: {e}")

    print(f"✅ Ley 1123: {cargados} artículos cargados (esperados ~104)")


# ── Ley 1952/2019 (.docx estándar) ───────────────────────────────────────────

def procesar_ley_1952():
    ruta = SCRIPTS_DIR / "L1952-2019__CGD_.docx"
    if not ruta.exists():
        print(f"⚠️  No se encontró {ruta} — saltando Ley 1952")
        return

    print("\n📖 Procesando Ley 1952 de 2019...")
    doc  = Document(ruta)
    texto = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    patron = r"Art[íi]culo\s+(\d+[°o]?[a-z]?)\.?\s*([^.\n]{0,120}\.?)(.+?)(?=Art[íi]culo\s+\d+[°o]?|\Z)"
    articulos = re.findall(patron, texto, re.DOTALL | re.IGNORECASE)

    cargados = 0
    for numero, titulo, contenido in articulos:
        numero    = numero.strip().rstrip("°o")
        titulo    = titulo.strip()[:120]
        contenido = contenido.strip()[:4000]
        if len(contenido) < 10:
            continue
        try:
            insertar_articulo("1952", numero, titulo, contenido)
            print(f"  [Ley 1952] Artículo {numero} — OK")
            cargados += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  [Ley 1952] Artículo {numero} — ERROR: {e}")

    print(f"✅ Ley 1952: {cargados} artículos cargados (esperados ~263)")


if __name__ == "__main__":
    print("═" * 55)
    print("  DISCIPLINAR[IA] — Carga de biblioteca normativa")
    print("═" * 55)
    procesar_ley_1123()
    procesar_ley_1952()
    print("\n🏁 Carga completa.")
