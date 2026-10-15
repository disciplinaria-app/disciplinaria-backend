"""Generador de variantes de consulta y filtro de privacidad.

Las variantes son deterministas (sin modelo de lenguaje). El filtro rechaza
entradas que parezcan traer datos del expediente: cédulas, radicados de
proceso, nombres propios de partes, párrafos enteros del borrador.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .texto import normalizar

LIMITE_TEXTO_LIBRE = 2000

_RE_CEDULA = re.compile(r"\b(?:c\.?\s?c\.?|c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|nit|t\.?\s?i\.?)\s*(?:n[°º.]?\s*)?[\d.]{6,15}\b", re.I)
_RE_RADICADO_PROCESO = re.compile(r"\b\d{5}[-\s]?\d{2}[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}\b|\b\d{23}\b")
_RE_PARTES = re.compile(r"\b(?:accionante|accionad[oa]|disciplinad[oa]|quejos[oa]|procesad[oa]|demandante|demandad[oa]|investigad[oa]|señor(?:a)?|doctor(?:a)?)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}")
_RE_DIAGNOSTICO = re.compile(r"\b(?:diagn[oó]stico|historia\s+cl[ií]nica|VIH|c[aá]ncer|epicrisis)\b", re.I)

ADVERSOS = ["excepción", "no procede", "improcedente", "distinguió", "rectificó", "modificó", "apartó", "superó", "cambio de precedente"]

SINONIMOS: dict[str, list[str]] = {
    "ilicitud sustancial": ["afectación del deber funcional", "deber funcional sin justificación"],
    "antijuridicidad": ["afectación injustificada del deber profesional", "deber profesional"],
    "subsidiariedad": ["otro medio de defensa judicial", "mecanismo transitorio", "perjuicio irremediable"],
    "inmediatez": ["plazo razonable", "término razonable interposición"],
    "plazo razonable": ["mora administrativa", "dilación injustificada"],
    "tipicidad": ["adecuación típica", "descripción típica"],
    "culpabilidad": ["dolo", "culpa", "responsabilidad objetiva"],
    "prescripción": ["caducidad", "término prescriptivo"],
}


@dataclass
class Revision:
    aceptada: bool
    texto: str
    motivos: list[str]


def revisar_entrada(texto: str) -> Revision:
    """Sanitiza una consulta abstracta. Rechaza si contiene datos de partes."""
    motivos: list[str] = []
    t = (texto or "").strip()
    if len(t) > LIMITE_TEXTO_LIBRE:
        motivos.append(f"texto de {len(t)} caracteres; el máximo es {LIMITE_TEXTO_LIBRE}")
    if _RE_CEDULA.search(t):
        motivos.append("contiene un número de identificación personal")
    if _RE_RADICADO_PROCESO.search(t):
        motivos.append("contiene un radicado de proceso de 23 dígitos; use solo identificadores de providencias públicas")
    if _RE_PARTES.search(t):
        motivos.append("contiene calidad procesal seguida de un nombre propio")
    if _RE_DIAGNOSTICO.search(t):
        motivos.append("contiene datos de salud")
    if t.count("\n") > 6 or len(t.split()) > 120:
        motivos.append("parece un párrafo del borrador; formule una subregla abstracta")
    return Revision(aceptada=not motivos, texto=t, motivos=motivos)


def variantes(subregla: str, corporacion_nombre: str, desde: int | None, hasta: int | None,
              sentencia_hito: str | None = None, incluir_adversas: bool = True) -> list[dict[str, str]]:
    """Familias de consulta por subregla, sin datos del expediente."""
    base = subregla.strip().strip('"')
    nucleo = " ".join(w for w in normalizar(base).split() if len(w) > 3)[:120]
    salida: list[dict[str, str]] = [
        {"familia": "frase_exacta", "consulta": f'"{base}"'},
        {"familia": "frase_libre", "consulta": base},
        {"familia": "terminos_nucleares", "consulta": nucleo},
        {"familia": "categoria_corporacion", "consulta": f"{base} {corporacion_nombre}"},
    ]
    for clave, sins in SINONIMOS.items():
        if clave in normalizar(base):
            for s in sins[:2]:
                salida.append({"familia": "sinonimo", "consulta": normalizar(base).replace(clave, s)})
    if desde or hasta:
        anios = " ".join(str(a) for a in range(desde or hasta, (hasta or desde) + 1))
        salida.append({"familia": "actualizacion", "consulta": f"{nucleo} {anios}"})
    if incluir_adversas:
        for adv in ADVERSOS[:5]:
            salida.append({"familia": "adversa", "consulta": f"{nucleo} {adv}"})
    if sentencia_hito:
        salida.append({"familia": "citacion_hito", "consulta": sentencia_hito})
    # Deduplicar conservando orden.
    vistos: set[str] = set()
    unicas = []
    for v in salida:
        c = v["consulta"].strip()
        if c and c.lower() not in vistos:
            vistos.add(c.lower())
            unicas.append(v)
    return unicas
