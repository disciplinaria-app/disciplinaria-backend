"""Extracción, normalización y segmentación de texto oficial.

Todo lo que aquí se calcula es determinista: no hay modelo de lenguaje.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .modelos import RolTextual

# --- Normalización -----------------------------------------------------------

_ESPACIOS = re.compile(r"[ \t ]+")
_SALTOS = re.compile(r"\n{3,}")


def quitar_tildes(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def normalizar(s: str) -> str:
    """Minúsculas, sin tildes, sin puntuación redundante, espacios simples."""
    s = quitar_tildes(s or "").lower()
    s = re.sub(r"[^\w\s/-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def limpiar_texto(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _ESPACIOS.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _SALTOS.sub("\n\n", s)
    return s.strip()


# --- Extracción --------------------------------------------------------------

def html_a_texto(html: str) -> tuple[str, dict[str, str]]:
    """Devuelve (texto, metadatos) a partir de HTML. Los metadatos son los
    <meta> y el <title>, útiles para la ficha de relatoría."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()
    meta: dict[str, str] = {}
    if soup.title and soup.title.string:
        meta["title"] = soup.title.string.strip()
    for m in soup.find_all("meta"):
        nombre = m.get("name") or m.get("property")
        if nombre and m.get("content"):
            meta[nombre.lower()] = m["content"].strip()
    # Conservar saltos de párrafo.
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5"]):
        p.append("\n")
    return limpiar_texto(soup.get_text()), meta


def pdf_a_texto(datos: bytes) -> tuple[str, dict[str, str]]:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(datos))
    paginas = []
    for i, pagina in enumerate(lector.pages, start=1):
        try:
            t = pagina.extract_text() or ""
        except Exception:  # pragma: no cover - pypdf puede fallar en PDF corruptos
            t = ""
        paginas.append(f"[[pág. {i}]]\n{t}")
    meta = {k.strip("/").lower(): str(v) for k, v in (lector.metadata or {}).items()}
    meta["paginas"] = str(len(lector.pages))
    return limpiar_texto("\n\n".join(paginas)), meta


# --- Segmentación y roles ----------------------------------------------------

_ENCABEZADOS_ROL: list[tuple[re.Pattern[str], RolTextual]] = [
    (re.compile(r"^\s*(salvamento|salvamentos)\s+(parcial\s+)?de\s+voto", re.I), "salvamento"),
    (re.compile(r"^\s*aclaraci[oó]n(es)?\s+de\s+voto", re.I), "aclaracion"),
    (re.compile(r"^\s*(iii?\.?|iv\.?|v\.?|vi\.?)?\s*(decisi[oó]n|resuelve|parte\s+resolutiva)\s*[:.]?\s*$", re.I), "resolutiva"),
    (re.compile(r"^\s*(ii?\.?|iii\.?|iv\.?)?\s*(consideraciones|fundamentos\s+(jur[ií]dicos|de\s+la\s+decisi[oó]n)|consideraciones\s+de\s+la\s+(corte|sala|comisi[oó]n))", re.I), "mayoria_motiva"),
    (re.compile(r"^\s*(i\.?|ii\.?)?\s*(antecedentes|hechos|la\s+demanda|la\s+solicitud|el\s+recurso|la\s+impugnaci[oó]n|intervenciones|alegatos|argumentos\s+de\s+la\s+parte|sustentaci[oó]n)", re.I), "argumento_parte"),
    (re.compile(r"^\s*(la\s+)?(sentencia|decisi[oó]n|providencia|fallo)\s+(impugnad[ao]|de\s+primera\s+instancia|recurrid[ao]|objeto\s+de\s+revisi[oó]n)", re.I), "decision_resenada"),
]


@dataclass
class Bloque:
    indice: int
    texto: str
    rol: RolTextual
    localizador: str


def segmentar(texto: str, tamano: int = 3500) -> list[Bloque]:
    """Divide el texto en bloques por párrafos, anotando el rol textual de la
    sección en la que caen (mayoría, resolutiva, salvamento, etc.) según el
    último encabezado reconocido. El rol es una estimación estructural y se
    informa como tal: la skill debe leer el contexto.
    """
    parrafos = [p for p in texto.split("\n\n") if p.strip()]
    bloques: list[Bloque] = []
    rol_actual: RolTextual = "desconocido"
    actual: list[str] = []
    rol_bloque = rol_actual
    pagina = ""
    inicio_parrafo = 0

    def cerrar(idx_parrafo: int) -> None:
        nonlocal actual, rol_bloque
        if actual:
            loc = f"párr. {inicio_parrafo + 1}-{idx_parrafo}" + (f" · {pagina}" if pagina else "")
            bloques.append(Bloque(len(bloques), "\n\n".join(actual), rol_bloque, loc))
            actual = []

    for i, p in enumerate(parrafos):
        m_pag = re.search(r"\[\[p[aá]g\. (\d+)\]\]", p)
        if m_pag:
            pagina = f"pág. {m_pag.group(1)}"
        primera_linea = p.strip().split("\n", 1)[0][:160]
        for patron, rol in _ENCABEZADOS_ROL:
            if patron.search(primera_linea):
                cerrar(i)
                rol_actual = rol
                break
        if not actual:
            rol_bloque = rol_actual
            inicio_parrafo = i
        if sum(len(x) for x in actual) + len(p) > tamano and actual:
            cerrar(i)
            rol_bloque = rol_actual
            inicio_parrafo = i
        actual.append(p)
    cerrar(len(parrafos))
    return bloques


def rol_en_posicion(bloques: list[Bloque], pos: int) -> RolTextual:
    """Rol del bloque que contiene la posición de carácter `pos` (los bloques
    se reconstruyen unidos por dos saltos de línea)."""
    if pos < 0:
        return "desconocido"
    acumulado = 0
    for b in bloques:
        acumulado += len(b.texto) + 2
        if pos < acumulado:
            return b.rol
    return bloques[-1].rol if bloques else "desconocido"


def rol_de_posicion(bloques: list[Bloque], indice: int) -> RolTextual:
    return bloques[indice].rol if 0 <= indice < len(bloques) else "desconocido"


# --- Localización de pasajes -------------------------------------------------

def _tokens(s: str) -> set[str]:
    return {t for t in normalizar(s).split() if len(t) > 3}


def similitud(a: str, b: str) -> float:
    """Jaccard sobre tokens normalizados; 1.0 = mismos términos."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def localizar_pasaje(texto: str, consulta: str, ventana: int = 900) -> tuple[str, int, float]:
    """Busca el fragmento del texto más parecido a `consulta`.

    Devuelve (fragmento, posición_caracter, similitud). Primero intenta
    coincidencia literal normalizada; si no, la mejor ventana por tokens.
    """
    if not consulta.strip():
        return "", -1, 0.0
    texto_n, consulta_n = normalizar(texto), normalizar(consulta)
    pos = texto_n.find(consulta_n)
    if pos >= 0:
        # Mapear a posición aproximada en el texto original. La posición que se
        # devuelve es la del hallazgo, no la del inicio de la ventana.
        ratio = len(texto) / max(len(texto_n), 1)
        p = int(pos * ratio)
        ini, fin = max(0, p - ventana // 2), min(len(texto), p + ventana // 2)
        return texto[ini:fin], p, 1.0
    mejor = ("", -1, 0.0)
    paso = max(ventana // 2, 1)
    for ini in range(0, max(len(texto) - ventana, 0) + 1, paso):
        frag = texto[ini:ini + ventana]
        s = similitud(frag, consulta)
        if s > mejor[2]:
            mejor = (frag, ini + ventana // 2, s)
    return mejor


def posicion_a_localizador(texto: str, pos: int) -> str:
    if pos < 0:
        return "no localizado"
    pagina = None
    for m in re.finditer(r"\[\[p[aá]g\. (\d+)\]\]", texto[:pos]):
        pagina = m.group(1)
    parrafo = texto[:pos].count("\n\n") + 1
    return f"párr. {parrafo}" + (f" · pág. {pagina}" if pagina else "")
