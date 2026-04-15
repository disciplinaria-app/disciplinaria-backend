import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-sonnet-4-5"

ALLOWED_ORIGINS = [
    "https://disciplinaria.app",
    "https://www.disciplinaria.app",
    "http://localhost:3000",
    "http://localhost:5173",
]

NORMAS = {
    "1123": "Ley 1123 de 2007 - Código Disciplinario del Abogado",
    "1952": "Ley 1952 de 2019 - Código General Disciplinario (vigente desde 2021)",
    "734": "Ley 734 de 2002 - Código Disciplinario Único (complementario)",
}
