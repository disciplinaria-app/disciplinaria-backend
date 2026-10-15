"""Comparación determinista de los datos identificadores de una cita.

Cada campo se compara por separado y produce `confirmado`, `discrepante`,
`no_hallado` o `no_suministrado`. Nunca se completa un valor por inferencia.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .modelos import Campo
from .texto import normalizar, quitar_tildes

# --- Identificadores ---------------------------------------------------------

# Sentencias de la Corte Constitucional: T-123/19, T-123 de 2019, SU-107/2024, C-1-93, A-045/21
_RE_CC = re.compile(
    r"\b(?P<tipo>SU|T|C|A|SL)\s*-?\s*(?P<num>\d{1,4})\s*(?:/|-|\s+de\s+|\s+del\s+)\s*(?P<anio>\d{2,4})\b",
    re.I,
)
# Radicados con dígitos largos (CSJ, CE, CNDJ): 11001-03-15-000-2019-01234-00, 110010315000201901234
_RE_RADICADO = re.compile(r"\b\d{5}(?:[-\s]?\d{2}){2}[-\s]?\d{3}[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}\b|\b\d{23}\b")
# Números internos CSJ: SP1234-2021, STP12345-2022, AP1234-2020, SL1234-2019
_RE_CSJ_INTERNO = re.compile(r"\b(?P<tipo>SP|STP|AP|SL|STL|SC|STC|AC|AL|CSJ)\s*-?\s*(?P<num>\d{1,6})\s*-\s*(?P<anio>\d{4})\b", re.I)
# Radicados CSJ cortos: 52.345, 45678
_RE_CSJ_RAD = re.compile(r"\b(?:rad(?:icado|icación)?\.?\s*(?:n[°º.]?\s*)?)(?P<num>\d{1,3}(?:\.\d{3})+|\d{4,6})\b", re.I)


def _anio4(a: str) -> str:
    if len(a) == 4:
        return a
    n = int(a)
    return str(1900 + n if n >= 90 else 2000 + n)


def canonizar_identificador(valor: str) -> str:
    """Forma canónica para comparar: 'SU-107/2024', 'SP1234-2021', radicado sin
    separadores. Si no reconoce el patrón, devuelve el texto normalizado."""
    v = valor.strip()
    m = _RE_CC.search(v)
    if m:
        return f"{m.group('tipo').upper()}-{int(m.group('num'))}/{_anio4(m.group('anio'))}"
    m = _RE_CSJ_INTERNO.search(v)
    if m:
        return f"{m.group('tipo').upper()}{int(m.group('num'))}-{m.group('anio')}"
    m = _RE_RADICADO.search(v)
    if m:
        return re.sub(r"[-\s]", "", m.group(0))
    m = _RE_CSJ_RAD.search(v)
    if m:
        return m.group("num").replace(".", "")
    return normalizar(v)


def identificadores_en_texto(texto: str) -> set[str]:
    """Todos los identificadores canónicos que aparecen en un texto."""
    encontrados: set[str] = set()
    for m in _RE_CC.finditer(texto):
        encontrados.add(canonizar_identificador(m.group(0)))
    for m in _RE_CSJ_INTERNO.finditer(texto):
        encontrados.add(canonizar_identificador(m.group(0)))
    for m in _RE_RADICADO.finditer(texto):
        encontrados.add(canonizar_identificador(m.group(0)))
    return encontrados


# --- Fechas -----------------------------------------------------------------

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_RE_FECHA_LARGA = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?:de\s+)?(?P<m>[a-záé]+)\s+(?:de\s+|del\s+)?(?P<a>\d{4})\b", re.I
)
_RE_FECHA_ISO = re.compile(r"\b(?P<a>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_RE_FECHA_NUM = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<a>\d{4})\b")


def parsear_fecha(valor: str) -> Optional[date]:
    v = quitar_tildes(valor.strip().lower())
    m = _RE_FECHA_ISO.search(v)
    if m:
        try:
            return date(int(m["a"]), int(m["m"]), int(m["d"]))
        except ValueError:
            return None
    m = _RE_FECHA_NUM.search(v)
    if m:
        try:
            return date(int(m["a"]), int(m["m"]), int(m["d"]))
        except ValueError:
            return None
    m = _RE_FECHA_LARGA.search(v)
    if m and m["m"] in _MESES:
        try:
            return date(int(m["a"]), _MESES[m["m"]], int(m["d"]))
        except ValueError:
            return None
    return None


def fechas_en_texto(texto: str, limite: int = 60) -> list[tuple[date, int]]:
    """Fechas con su posición, en orden de aparición (hasta `limite`)."""
    salida: list[tuple[date, int]] = []
    t = quitar_tildes(texto.lower())
    for patron in (_RE_FECHA_LARGA, _RE_FECHA_ISO, _RE_FECHA_NUM):
        for m in patron.finditer(t):
            f = parsear_fecha(m.group(0))
            if f:
                salida.append((f, m.start()))
            if len(salida) >= limite:
                break
    return sorted(salida, key=lambda x: x[1])


# --- Ponentes ----------------------------------------------------------------

_RE_PONENTE = re.compile(
    r"(?:magistrad[oa]\s+ponente|magistrad[oa]\s+sustanciador[a]?|m\.?\s?p\.?|ponente)\s*[:.]?\s*"
    r"(?:dr[a]?\.?\s+)?(?P<nombre>[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’.-]+(?:\s+(?:de\s+|del\s+|la\s+)?[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'’.-]+){1,5})",
)


def apellidos(nombre: str) -> set[str]:
    partes = [p for p in normalizar(nombre).split() if p not in {"de", "del", "la", "las", "los", "y", "dr", "dra"}]
    return set(partes)


def ponente_coincide(suministrado: str, oficial: str) -> bool:
    """Coincidencia robusta: al menos dos partes del nombre en común, o todas
    las partes suministradas si son menos de dos."""
    a, b = apellidos(suministrado), apellidos(oficial)
    if not a or not b:
        return False
    comunes = a & b
    return len(comunes) >= min(2, len(a))


def ponentes_en_texto(texto: str, limite: int = 10) -> list[str]:
    nombres: list[str] = []
    for m in _RE_PONENTE.finditer(texto[:20000]):
        n = m.group("nombre").strip(" .")
        # Cortar en palabras que delatan el final del nombre.
        n = re.split(r"\s+(?:Bogot[aá]|Sentencia|Radicaci[oó]n|Expediente|Referencia|Asunto|Proceso)\b", n)[0]
        if n and n not in nombres:
            nombres.append(n)
        if len(nombres) >= limite:
            break
    return nombres


# --- Comparación por campo ----------------------------------------------------

def comparar_identificador(suministrado: Optional[str], texto: str, titulo: str = "") -> Campo:
    if not suministrado:
        return Campo(estado="no_suministrado")
    can = canonizar_identificador(suministrado)
    en_doc = identificadores_en_texto(titulo + "\n" + texto[:6000])
    if can in en_doc:
        return Campo(estado="confirmado", valor_suministrado=suministrado, valor_oficial=can,
                     evidencia="identificador presente en el encabezado del documento oficial", localizador="encabezado")
    if en_doc:
        return Campo(estado="discrepante", valor_suministrado=suministrado,
                     valor_oficial=", ".join(sorted(en_doc)[:5]),
                     evidencia="el encabezado del documento oficial muestra otro(s) identificador(es)", localizador="encabezado")
    return Campo(estado="no_hallado", valor_suministrado=suministrado,
                 evidencia="no se reconoció identificador en el encabezado del documento")


def comparar_ponente(suministrado: Optional[str], texto: str) -> Campo:
    if not suministrado:
        return Campo(estado="no_suministrado")
    oficiales = ponentes_en_texto(texto)
    for o in oficiales:
        if ponente_coincide(suministrado, o):
            return Campo(estado="confirmado", valor_suministrado=suministrado, valor_oficial=o,
                         evidencia="nombre del ponente hallado en el documento oficial", localizador="encabezado")
    if oficiales:
        return Campo(estado="discrepante", valor_suministrado=suministrado, valor_oficial="; ".join(oficiales[:3]),
                     evidencia="el documento oficial identifica otro ponente", localizador="encabezado")
    return Campo(estado="no_hallado", valor_suministrado=suministrado,
                 evidencia="no se reconoció la mención del ponente en el documento")


def comparar_fecha(suministrado: Optional[str], texto: str) -> Campo:
    if not suministrado:
        return Campo(estado="no_suministrado")
    f = parsear_fecha(suministrado)
    if not f:
        return Campo(estado="no_hallado", valor_suministrado=suministrado,
                     evidencia="la fecha suministrada no es interpretable")
    encontradas = fechas_en_texto(texto[:8000])
    if any(ff == f for ff, _ in encontradas):
        return Campo(estado="confirmado", valor_suministrado=suministrado, valor_oficial=f.isoformat(),
                     evidencia="fecha presente en el encabezado del documento oficial", localizador="encabezado")
    if encontradas:
        candidatas = sorted({ff.isoformat() for ff, _ in encontradas[:6]})
        return Campo(estado="discrepante", valor_suministrado=suministrado, valor_oficial=", ".join(candidatas),
                     evidencia="el encabezado muestra otras fechas; verificar cuál es la de la decisión", localizador="encabezado")
    return Campo(estado="no_hallado", valor_suministrado=suministrado,
                 evidencia="no se reconoció fecha en el encabezado del documento")


def comparar_sala(suministrado: Optional[str], texto: str) -> Campo:
    if not suministrado:
        return Campo(estado="no_suministrado")
    s = normalizar(suministrado)
    t = normalizar(texto[:8000])
    claves = [k for k in s.split() if k not in {"sala", "de", "la", "seccion", "subseccion"}]
    if s in t or (claves and all(k in t for k in claves)):
        return Campo(estado="confirmado", valor_suministrado=suministrado, valor_oficial=suministrado,
                     evidencia="denominación de la sala/sección presente en el encabezado", localizador="encabezado")
    m = re.search(r"(sala\s+(?:plena|de\s+casaci[oó]n\s+\w+|\w+\s+de\s+revisi[oó]n|jurisdiccional\s+disciplinaria|\w+)|secci[oó]n\s+\w+)", texto[:8000], re.I)
    if m:
        return Campo(estado="discrepante", valor_suministrado=suministrado, valor_oficial=m.group(0),
                     evidencia="el encabezado menciona otra sala/sección", localizador="encabezado")
    return Campo(estado="no_hallado", valor_suministrado=suministrado,
                 evidencia="no se reconoció la sala/sección en el encabezado")
