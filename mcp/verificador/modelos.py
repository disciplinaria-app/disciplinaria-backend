from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Corporacion(str, Enum):
    CORTE_CONSTITUCIONAL = "corte_constitucional"
    CORTE_SUPREMA = "corte_suprema"
    CONSEJO_ESTADO = "consejo_estado"
    CNDJ = "cndj"


ALIAS_CORPORACION: dict[str, Corporacion] = {
    "corte constitucional": Corporacion.CORTE_CONSTITUCIONAL,
    "cc": Corporacion.CORTE_CONSTITUCIONAL,
    "corte suprema": Corporacion.CORTE_SUPREMA,
    "corte suprema de justicia": Corporacion.CORTE_SUPREMA,
    "csj": Corporacion.CORTE_SUPREMA,
    "consejo de estado": Corporacion.CONSEJO_ESTADO,
    "ce": Corporacion.CONSEJO_ESTADO,
    "cndj": Corporacion.CNDJ,
    "comision nacional de disciplina judicial": Corporacion.CNDJ,
    "comisión nacional de disciplina judicial": Corporacion.CNDJ,
}


def normalizar_corporacion(valor: str | Corporacion) -> Corporacion:
    if isinstance(valor, Corporacion):
        return valor
    clave = valor.strip().lower().replace("_", " ")
    if clave in ALIAS_CORPORACION:
        return ALIAS_CORPORACION[clave]
    for c in Corporacion:
        if c.value == clave.replace(" ", "_"):
            return c
    raise ValueError(f"Corporación no reconocida: {valor!r}")


# Estados técnicos distintos, según el principio 6 de la especificación.
EstadoConsulta = Literal[
    "ok", "sin_resultados", "no_hallada", "discrepante",
    "portal_no_disponible", "bloqueada", "timeout", "parcial", "confirmada",
]
EstadoCampo = Literal["confirmado", "discrepante", "no_hallado", "no_aplica", "no_suministrado"]
RolTextual = Literal[
    "mayoria_motiva", "resolutiva", "salvamento", "aclaracion",
    "argumento_parte", "decision_resenada", "desconocido",
]
Canal = Literal["corpus", "http", "buscador", "playwright", "web_restringida", "expansion"]


class Procedencia(BaseModel):
    url_inicial: Optional[str] = None
    url_final: Optional[str] = None
    codigo_http: Optional[int] = None
    consultada_en: datetime
    sha256: Optional[str] = None
    canal: Canal
    estado: EstadoConsulta
    detalle: Optional[str] = None


class Candidato(BaseModel):
    corporacion: Corporacion
    identificador: str
    url_oficial: Optional[str] = None
    titulo: Optional[str] = None
    fecha: Optional[date] = None
    ponente: Optional[str] = None
    sala: Optional[str] = None
    fragmento_descubrimiento: Optional[str] = None
    canales: list[Canal] = Field(default_factory=list)
    verificado: bool = False  # siempre False al salir de la búsqueda


class Campo(BaseModel):
    estado: EstadoCampo
    valor_suministrado: Optional[str] = None
    valor_oficial: Optional[str] = None
    evidencia: Optional[str] = None
    localizador: Optional[str] = None


class Pasaje(BaseModel):
    texto: str
    rol: RolTextual
    localizador: str
    similitud: float


class DocumentoOficial(BaseModel):
    corporacion: Corporacion
    identificador: str
    url_oficial: str
    texto: str
    sha256: str
    consultada_en: datetime
    canal: Canal
    tipo_contenido: Literal["html", "pdf", "texto"]
    metadatos: dict[str, str] = Field(default_factory=dict)


class ResultadoVerificacion(BaseModel):
    estado_global: EstadoConsulta
    corporacion: Corporacion
    campos: dict[str, Campo]
    url_oficial: Optional[str] = None
    procedencia: Optional[Procedencia] = None
    pasaje: Optional[Pasaje] = None
    solo_en_salvamento: bool = False
    advertencias: list[str] = Field(default_factory=list)
    limite: str = (
        "El servidor compara texto y metadatos; no califica la pertinencia ni la "
        "fuerza jurídica del precedente. Un estado 'confirmada' acredita identidad, "
        "no que la providencia respalde la tesis."
    )


class ResultadoBusqueda(BaseModel):
    estado: EstadoConsulta
    candidatos: list[Candidato]
    canales_ejecutados: list[dict]
    coverage_status: Literal["completa", "parcial", "insuficiente"]
    advertencias: list[str] = Field(default_factory=list)
    trabajo_id: Optional[str] = None


class Segmento(BaseModel):
    indice: int
    total: int
    texto: str
    localizador: str
    rol_estimado: RolTextual


class ResultadoLectura(BaseModel):
    estado: EstadoConsulta
    documento: Optional[dict] = None
    segmento: Optional[Segmento] = None
    advertencias: list[str] = Field(default_factory=list)


class EstadoPortal(BaseModel):
    corporacion: Corporacion
    url: str
    estado: EstadoConsulta
    codigo_http: Optional[int] = None
    latencia_ms: Optional[int] = None
    detalle: Optional[str] = None
    comprobado_en: datetime
