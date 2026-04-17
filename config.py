import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenRouter ──────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-sonnet-4-5"

# ── Embeddings (via OpenRouter) ─────────────────────────────────────────────
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIM = 1536

# ── Supabase (biblioteca normativa vectorial) ────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── CORS ─────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "https://disciplinaria.app",
    "https://www.disciplinaria.app",
    "https://disciplinaria-app.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5500",
]

# ── Normas ───────────────────────────────────────────────────────────────────
NORMAS = {
    # Valores enviados por el frontend
    "ley_1123": "Ley 1123 de 2007 - Código Disciplinario del Abogado",
    "ley_1952": "Ley 1952 de 2019 - Código General Disciplinario (vigente desde 2021)",
    # Valores legacy / uso directo de la API
    "1123": "Ley 1123 de 2007 - Código Disciplinario del Abogado",
    "1952": "Ley 1952 de 2019 - Código General Disciplinario (vigente desde 2021)",
    "734": "Ley 734 de 2002 - Código Disciplinario Único (complementario)",
}
