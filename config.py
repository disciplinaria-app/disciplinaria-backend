import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-sonnet-4-5"

# El triage de correspondencia es una tarea de extracción, no de valoración
# jurídica, y admite un modelo más económico. Se mantiene por defecto el mismo
# modelo para no degradar la detección de incongruencias sin medirla antes.
MODEL_TRIAGE = os.getenv("MODEL_TRIAGE", MODEL)

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


# ---------------------------------------------------------------------------
# Ingesta por reenvío a un buzón propio
# ---------------------------------------------------------------------------


def _entero(nombre: str, defecto: int) -> int:
    """Lee un entero del entorno sin que un valor mal escrito tumbe el proceso."""
    try:
        return int(os.getenv(nombre, "") or defecto)
    except ValueError:
        return defecto


def _booleano(nombre: str, defecto: bool) -> bool:
    valor = (os.getenv(nombre, "") or "").strip().lower()
    if not valor:
        return defecto
    return valor in {"1", "true", "si", "sí", "yes", "on"}


def _direcciones(nombre: str) -> frozenset[str]:
    crudo = os.getenv(nombre, "") or ""
    return frozenset(d.strip().lower() for d in crudo.split(",") if d.strip())


# Claves que autorizan el uso de los endpoints de triage. Se admiten varias,
# separadas por comas, para poder rotarlas sin interrumpir el servicio. Si no
# hay ninguna configurada, los endpoints rechazan toda solicitud: una API que
# consume el modelo y lee correspondencia no puede quedar abierta.
TRIAGE_API_KEYS = frozenset(
    clave.strip() for clave in (os.getenv("TRIAGE_API_KEYS", "") or "").split(",") if clave.strip()
)

# Límites del reconocimiento óptico. Importan en la ruta de Power Automate: su
# acción HTTP agota la espera a los 120 segundos, y el reconocimiento de muchas
# páginas a alta resolución puede excederlos.
MAX_PAGINAS_OCR = _entero("MAX_PAGINAS_OCR", 20)
DPI_OCR = _entero("DPI_OCR", 300)


# --- Ingesta por reenvío a un buzón propio ---------------------------------

# Buzones del propio usuario. Un correo que provenga de alguno de ellos se
# presume reenviado, y el worker intenta recuperar el remitente original.
DIRECCIONES_PROPIAS = _direcciones("DIRECCIONES_PROPIAS")

IMAP_SERVIDOR = os.getenv("IMAP_SERVIDOR", "")
IMAP_PUERTO = _entero("IMAP_PUERTO", 993)
IMAP_USUARIO = os.getenv("IMAP_USUARIO", "")
IMAP_CLAVE = os.getenv("IMAP_CLAVE", "")
IMAP_CARPETA = os.getenv("IMAP_CARPETA", "INBOX")
IMAP_SSL = _booleano("IMAP_SSL", True)

SMTP_SERVIDOR = os.getenv("SMTP_SERVIDOR", "")
SMTP_PUERTO = _entero("SMTP_PUERTO", 587)
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
SMTP_CLAVE = os.getenv("SMTP_CLAVE", "")
SMTP_STARTTLS = _booleano("SMTP_STARTTLS", True)
SMTP_REMITENTE = os.getenv("SMTP_REMITENTE", "") or SMTP_USUARIO

# Buzón al que se remiten las fichas. Si se omite, se usa el del propio worker.
DESTINATARIO_FICHAS = os.getenv("DESTINATARIO_FICHAS", "") or IMAP_USUARIO

# Registro de lo ya procesado. En Railway el disco es efímero y este archivo se
# pierde al redesplegar; es un resguardo secundario, pues la marca de leído del
# propio buzón IMAP es lo que evita reprocesar.
ESTADO_INGESTA = os.getenv("ESTADO_INGESTA", "estado_ingesta.json")

INTERVALO_SONDEO = _entero("INTERVALO_SONDEO", 300)
MAX_CORREOS_POR_CICLO = _entero("MAX_CORREOS_POR_CICLO", 20)

# Tras este número de intentos fallidos, el correo se da por procesado y se
# avisa al destinatario: nunca se descarta en silencio ni se reintenta sin fin.
MAX_INTENTOS_POR_CORREO = _entero("MAX_INTENTOS_POR_CORREO", 3)
