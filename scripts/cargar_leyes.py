"""
Script de carga de artículos de las Leyes 1123/2007 y 1952/2019 en Supabase
con embeddings vectoriales (text-embedding-3-small, 1536 dims).

Uso:
    pip install supabase openai python-docx python-dotenv pypdf
    python scripts/cargar_leyes.py

Variables de entorno requeridas (.env en la raíz del proyecto):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    OPENAI_API_KEY

Archivos esperados en scripts/:
    LEY_1123_DE_2007.pdf   (PDF con texto seleccionable)   ← o .doc HTML UTF-16
    L1952-2019__CGD_.docx  (Word estándar)
"""

import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (un nivel arriba de scripts/)
load_dotenv(Path(__file__).parent.parent / ".env")

try:
    from supabase import create_client
    from openai import OpenAI
    from docx import Document
except ImportError as e:
    print(f"Dependencia faltante: {e}")
    print("Ejecuta: pip install supabase openai python-docx python-dotenv pypdf")
    sys.exit(1)

# ── Clientes ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_KEY]):
    print("❌  Faltan variables de entorno. Revisa el archivo .env en la raíz del proyecto.")
    print("    Necesarias: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY")
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
    emb = generar_embedding(f"Artículo {numero} - {titulo}: {contenido}")
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


def extraer_articulos(texto: str) -> list[tuple[str, str, str]]:
    """Extrae (numero, titulo, contenido) de un texto normativo plano."""
    patron = (
        r"Art[íi]culo\s+(\d+[°o]?[a-z]?)\.?\s*"   # número
        r"([^.\n]{0,150}\.?)"                        # título opcional
        r"(.+?)(?=Art[íi]culo\s+\d+[°o]?|\Z)"       # contenido
    )
    matches = re.findall(patron, texto, re.DOTALL | re.IGNORECASE)
    resultado = []
    for numero, titulo, contenido in matches:
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
            print(f"  [Ley {ley}] Artículo {numero} — OK")
            cargados += 1
            time.sleep(0.3)   # evitar rate-limit de OpenAI embeddings
        except Exception as exc:
            print(f"  [Ley {ley}] Artículo {numero} — ERROR: {exc}")
    print(f"✅  Ley {ley}: {cargados} artículos cargados (esperados ~{esperados})\n")


# ── Ley 1123/2007 ─────────────────────────────────────────────────────────────

def _texto_desde_pdf(ruta: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            print("  ⚠️  pypdf no instalado. Ejecuta: pip install pypdf")
            return ""
    reader = PdfReader(str(ruta))
    paginas = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            paginas.append(t)
    return "\n".join(paginas)


def _texto_desde_doc_html(ruta: Path) -> str:
    with open(ruta, encoding="utf-16") as f:
        content = f.read()
    texto = re.sub(r"<[^>]+>", " ", content)
    texto = re.sub(r"&nbsp;",  " ", texto)
    texto = re.sub(r"&amp;",   "&", texto)
    texto = re.sub(r"&lt;",    "<", texto)
    texto = re.sub(r"&gt;",    ">", texto)
    return re.sub(r"\s+", " ", texto).strip()


def procesar_ley_1123() -> None:
    print("📖  Procesando Ley 1123 de 2007...")

    texto = ""
    ruta_pdf = SCRIPTS_DIR / "LEY_1123_DE_2007.pdf"
    ruta_doc = SCRIPTS_DIR / "LEY_1123_DE_2007.doc"

    if ruta_pdf.exists():
        print(f"  → Leyendo PDF: {ruta_pdf.name}")
        texto = _texto_desde_pdf(ruta_pdf)
    elif ruta_doc.exists():
        print(f"  → Leyendo DOC HTML (UTF-16): {ruta_doc.name}")
        texto = _texto_desde_doc_html(ruta_doc)
    else:
        print("  ⚠️  No se encontró LEY_1123_DE_2007.pdf ni .doc — saltando")
        return

    if not texto:
        print("  ⚠️  No se pudo extraer texto del archivo — saltando")
        return

    articulos = extraer_articulos(texto)
    if not articulos:
        print("  ⚠️  No se encontraron artículos en el texto extraído")
        return

    cargar_articulos("1123", articulos, esperados=104)


# ── Ley 1952/2019 ─────────────────────────────────────────────────────────────

def procesar_ley_1952() -> None:
    print("📖  Procesando Ley 1952 de 2019...")

    # Acepta el nombre canónico o cualquier variante L1952*.docx
    ruta = SCRIPTS_DIR / "L1952-2019__CGD_.docx"
    if not ruta.exists():
        candidatos = sorted(SCRIPTS_DIR.glob("L1952*.docx"))
        if candidatos:
            ruta = candidatos[0]
        else:
            print("  ⚠️  No se encontró L1952-2019__CGD_.docx — saltando")
            return

    print(f"  → Leyendo DOCX: {ruta.name}")
    doc   = Document(str(ruta))
    texto = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    articulos = extraer_articulos(texto)
    if not articulos:
        print("  ⚠️  No se encontraron artículos en el archivo")
        return

    cargar_articulos("1952", articulos, esperados=263)


# ── Punto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("═" * 58)
    print("  DISCIPLINAR[IA] — Carga de biblioteca normativa")
    print("═" * 58)
    procesar_ley_1123()
    procesar_ley_1952()
    print("🏁  Carga completa.")
