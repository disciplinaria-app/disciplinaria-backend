"""
Detección determinista de FORMA — reglas mecánicas migradas del prompt LLM.
Cada regla aquí es 100% reproducible, gratis (0 tokens) e infalible dentro
de su alcance. Solo se incluyen patrones sin ambigüedad contextual:
si una forma puede ser válida en algún contexto realista de providencia,
NO se detecta aquí (se deja al LLM).

Reglas cubiertas:
  M1-DET     — Tildes en pretéritos cuya forma sin tilde NO es palabra válida
  ESP-DET    — Espaciado en fechas y referencias numéricas (Ley1123, 31de…)
  O-DET      — Letra O usada como cero en cifras (1O → 10)
  UNION-DET  — Palabras unidas sin espacio (QuinteroAriza → Quintero Ariza)
  CEDIA-018  — Redundancias fijas (el día lunes → el lunes)
  REG-DET    — Régimen preposicional (de acuerdo a → de acuerdo con)
  DEQ-DET    — Dequeísmo con verbos que nunca rigen «de» (consideró de que…)
"""

import re

_MAX_HALLAZGOS = 12
_MAX_POR_REGLA = 4

# ── M1-DET: pretéritos sin tilde cuya forma átona no existe en español ────────
# Solo formas que SIN tilde no son palabra válida (ni presente 1ª persona,
# ni sustantivo, ni adjetivo). "considero", "ordeno", "señalo" NO están aquí
# porque son presentes válidos — esos los evalúa el LLM con contexto.
_TILDES = {
    "incurrio": "incurrió",
    "resolvio": "resolvió",
    "advirtio": "advirtió",
    "profirio": "profirió",
    "absolvio": "absolvió",
    "decidio": "decidió",
    "admitio": "admitió",
    "asumio": "asumió",
    "cumplio": "cumplió",
    "incumplio": "incumplió",
    "omitio": "omitió",
    "acudio": "acudió",
    "respondio": "respondió",
    "recibio": "recibió",
    "procedio": "procedió",
    "remitio": "remitió",
    "dirigio": "dirigió",
    "ejercio": "ejerció",
    "conocio": "conoció",
    "consistio": "consistió",
    "manifesto": "manifestó",
    "juridico": "jurídico",
    "juridica": "jurídica",
    "tecnico": "técnico",
    "tecnica": "técnica",
    "articulo": "artículo",
    "paragrafo": "parágrafo",
}
_RE_TILDES = re.compile(
    r"\b(" + "|".join(_TILDES) + r")\b", re.IGNORECASE
)

# ── ESP-DET: espaciado en referencias numéricas ───────────────────────────────
_RE_DIGITO_DE = re.compile(r"\b(\d{1,2})(de)\b")                      # 31de → 31 de
_RE_DE_ANIO   = re.compile(r"\b(de)(\d{4})\b")                        # de2025 → de 2025
_RE_REF_NUM   = re.compile(
    r"\b([Aa]rt[íi]culo|[Nn]umeral|[Ff]olio|[Ll]iteral|[Ll]ey|[Pp]ar[áa]grafo)(\d+)"
)                                                                      # Ley1123 → Ley 1123

# ── O-DET: letra O mayúscula usada como cero ─────────────────────────────────
_RE_O_CERO = re.compile(r"\b(\d+)O\b")                                # 1O → 10

# ── UNION-DET: minúscula seguida de mayúscula dentro de la misma palabra ─────
# El primer grupo admite mayúscula inicial para capturar "QuinteroAriza" completo.
_RE_UNION = re.compile(r"\b([A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]{2,})([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b")

# ── CEDIA-018: redundancias fijas ────────────────────────────────────────────
_DIAS = "lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo"
_MESES = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
_REDUNDANCIAS = [
    (re.compile(rf"\bel d[íi]a ({_DIAS})\b", re.IGNORECASE), r"el \1"),
    (re.compile(rf"\bel mes de ({_MESES})\b", re.IGNORECASE), r"\1"),
    (re.compile(r"\bresultado final\b", re.IGNORECASE), "resultado"),
    (re.compile(r"\bregresar de nuevo\b", re.IGNORECASE), "regresar"),
    (re.compile(r"\bsubir arriba\b", re.IGNORECASE), "subir"),
]

# ── REG-DET: régimen preposicional ───────────────────────────────────────────
_REGIMEN = [
    (re.compile(r"\bde acuerdo a\b", re.IGNORECASE), "de acuerdo con"),
    (re.compile(r"\ben raz[óo]n a\b", re.IGNORECASE), "en razón de"),
    (re.compile(r"\bacorde a\b", re.IGNORECASE), "acorde con"),
]

# ── DEQ-DET: dequeísmo con verbos que nunca rigen «de» ───────────────────────
# NO incluye "informó de que" ni "advirtió de que" (régimen válido según RAE).
_RE_DEQUEISMO = re.compile(
    r"\b(consider[óo]|concluy[óo]|manifest[óo]|señal[óo]|pidi[óo]|explic[óo]|sostuvo|afirm[óo]) de que\b",
    re.IGNORECASE,
)


def _h(modulo: str, ubicacion: str, error: str, justificacion: str,
       correccion: str, severidad: str) -> dict:
    return {
        "modulo": modulo,
        "ubicacion": ubicacion[:80],
        "error": error,
        "justificacion": justificacion,
        "correccion": correccion,
        "severidad": severidad,
    }


def _contexto(texto: str, inicio: int, fin: int, ventana: int = 25) -> str:
    """Extrae el fragmento con algo de contexto, sin partir palabras."""
    a = max(0, inicio - ventana)
    b = min(len(texto), fin + ventana)
    frag = texto[a:b]
    # Recortar a límites de palabra
    if a > 0:
        frag = frag.split(" ", 1)[-1]
    if b < len(texto):
        frag = frag.rsplit(" ", 1)[0]
    return frag.strip()


def analizar_deterministico(texto: str) -> list[dict]:
    """Aplica todas las reglas mecánicas y retorna hallazgos formato dict."""
    hallazgos: list[dict] = []

    # M1-DET — tildes
    n = 0
    for m in _RE_TILDES.finditer(texto):
        if n >= _MAX_POR_REGLA:
            break
        palabra = m.group(1)
        correcta = _TILDES[palabra.lower()]
        if palabra[0].isupper():
            correcta = correcta.capitalize()
        hallazgos.append(_h(
            "M1", _contexto(texto, m.start(), m.end()),
            f"Falta tilde: «{palabra}» debe ser «{correcta}»",
            "La forma sin tilde no es palabra válida en español (RAE 2010).",
            correcta, "media",
        ))
        n += 1

    # ESP-DET — espaciado numérico
    n = 0
    for regex, sep in ((_RE_DIGITO_DE, "{0} {1}"), (_RE_DE_ANIO, "{0} {1}"), (_RE_REF_NUM, "{0} {1}")):
        for m in regex.finditer(texto):
            if n >= _MAX_POR_REGLA:
                break
            original = m.group(0)
            g1 = m.group(1)
            # Si la palabra además carece de tilde (articulo28), corregir ambos errores
            if g1.lower() in _TILDES:
                acentuada = _TILDES[g1.lower()]
                g1 = acentuada.capitalize() if g1[0].isupper() else acentuada
            correccion = sep.format(g1, m.group(2))
            hallazgos.append(_h(
                "CEDIA-011", original,
                f"Falta espacio: «{original}» debe ser «{correccion}»",
                "Espaciado obligatorio en fechas y referencias numéricas (RAE 2010).",
                correccion, "media",
            ))
            n += 1

    # O-DET — letra O como cero
    n = 0
    for m in _RE_O_CERO.finditer(texto):
        if n >= _MAX_POR_REGLA:
            break
        original = m.group(0)
        correccion = m.group(1) + "0"
        hallazgos.append(_h(
            "M1", original,
            f"Letra «O» usada como cero: «{original}» debe ser «{correccion}»",
            "Confusión tipográfica entre la letra O y el dígito 0.",
            correccion, "alta",
        ))
        n += 1

    # UNION-DET — palabras unidas
    n = 0
    for m in _RE_UNION.finditer(texto):
        if n >= _MAX_POR_REGLA:
            break
        original = m.group(0)
        correccion = f"{m.group(1)} {m.group(2)}"
        hallazgos.append(_h(
            "M1", original,
            f"Palabras unidas sin espacio: «{original}» debe ser «{correccion}»",
            "Omisión de espacio entre palabras.",
            correccion, "media",
        ))
        n += 1

    # CEDIA-018 — redundancias
    n = 0
    for regex, reemplazo in _REDUNDANCIAS:
        for m in regex.finditer(texto):
            if n >= _MAX_POR_REGLA:
                break
            original = m.group(0)
            correccion = m.expand(reemplazo) if "\\" in repr(reemplazo) or "\\1" in reemplazo else reemplazo
            hallazgos.append(_h(
                "CEDIA-018", original,
                f"Redundancia: «{original}» debe ser «{correccion}»",
                "CEDIA-018: redundancia léxica fija.",
                correccion, "baja",
            ))
            n += 1

    # REG-DET — régimen preposicional
    n = 0
    for regex, correccion in _REGIMEN:
        for m in regex.finditer(texto):
            if n >= _MAX_POR_REGLA:
                break
            original = m.group(0)
            hallazgos.append(_h(
                "M1", original,
                f"Régimen preposicional incorrecto: «{original}» debe ser «{correccion}»",
                "Régimen preposicional según RAE: locución con preposición fija.",
                correccion, "baja",
            ))
            n += 1

    # DEQ-DET — dequeísmo
    n = 0
    for m in _RE_DEQUEISMO.finditer(texto):
        if n >= _MAX_POR_REGLA:
            break
        original = m.group(0)
        correccion = original.replace(" de que", " que").replace(" De que", " Que")
        hallazgos.append(_h(
            "CEDIA-017", original,
            f"Dequeísmo: «{original}» debe ser «{correccion}»",
            "El verbo rige complemento directo sin preposición «de».",
            correccion, "media",
        ))
        n += 1

    # Priorizar por severidad antes de aplicar el tope global
    _ORDEN = {"alta": 0, "media": 1, "baja": 2}
    hallazgos.sort(key=lambda h: _ORDEN[h["severidad"]])
    return hallazgos[:_MAX_HALLAZGOS]
