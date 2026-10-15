"""Corpus local de documentos oficiales recuperados.

Cada documento se guarda con su URL, fecha de consulta, hash y texto. El
corpus acelera la lectura y la comparación, pero nunca sustituye una
búsqueda de actualización: la fecha de recuperación viaja con el documento.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .modelos import DocumentoOficial

DIAS_CACHE_POR_DEFECTO = int(os.getenv("CORPUS_DIAS_CACHE", "30"))


def sha256(datos: bytes | str) -> str:
    if isinstance(datos, str):
        datos = datos.encode("utf-8")
    return hashlib.sha256(datos).hexdigest()


def _clave(corporacion: str, identificador: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", f"{corporacion}_{identificador}".lower()).strip("_")
    return base[:120] or "doc"


class Corpus:
    def __init__(self, directorio: Optional[str] = None, dias: int = DIAS_CACHE_POR_DEFECTO):
        self.dir = Path(directorio or os.getenv("CORPUS_DIR", "/tmp/redactar2-corpus"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.dias = dias

    def _ruta(self, corporacion: str, identificador: str) -> Path:
        return self.dir / f"{_clave(corporacion, identificador)}.json"

    def guardar(self, doc: DocumentoOficial) -> None:
        ruta = self._ruta(doc.corporacion.value, doc.identificador)
        ruta.write_text(doc.model_dump_json(), encoding="utf-8")

    def obtener(self, corporacion: str, identificador: str, max_dias: Optional[int] = None) -> Optional[DocumentoOficial]:
        ruta = self._ruta(corporacion, identificador)
        if not ruta.exists():
            return None
        try:
            doc = DocumentoOficial.model_validate_json(ruta.read_text(encoding="utf-8"))
        except Exception:
            return None
        limite = timedelta(days=self.dias if max_dias is None else max_dias)
        consultada = doc.consultada_en
        if consultada.tzinfo is None:
            consultada = consultada.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - consultada > limite:
            return None
        return doc

    def buscar_texto(self, terminos: list[str], corporacion: Optional[str] = None, limite: int = 20) -> list[DocumentoOficial]:
        """Búsqueda simple por términos en el corpus local (canal 0)."""
        terminos_n = [t.lower() for t in terminos if t.strip()]
        if not terminos_n:
            return []
        salida: list[tuple[int, DocumentoOficial]] = []
        for ruta in self.dir.glob("*.json"):
            if corporacion and not ruta.name.startswith(corporacion.lower()):
                continue
            try:
                doc = DocumentoOficial.model_validate_json(ruta.read_text(encoding="utf-8"))
            except Exception:
                continue
            texto = doc.texto.lower()
            puntaje = sum(texto.count(t) for t in terminos_n)
            if puntaje:
                salida.append((puntaje, doc))
        salida.sort(key=lambda x: -x[0])
        return [d for _, d in salida[:limite]]

    def listar(self) -> list[dict]:
        items = []
        for ruta in self.dir.glob("*.json"):
            try:
                d = json.loads(ruta.read_text(encoding="utf-8"))
                items.append({"corporacion": d["corporacion"], "identificador": d["identificador"],
                              "consultada_en": d["consultada_en"], "sha256": d["sha256"]})
            except Exception:
                continue
        return items
