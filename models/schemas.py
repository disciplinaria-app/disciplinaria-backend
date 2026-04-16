from pydantic import BaseModel, Field
from typing import Literal


class AnalisisRequest(BaseModel):
    texto: str = Field(..., min_length=50, description="Texto completo del documento jurídico disciplinario")
    norma: Literal["ley_1123", "ley_1952", "1123", "1952", "734"] = Field(
        ..., description="Norma aplicable: 'ley_1123' o 'ley_1952' (frontend) / '1123', '1952', '734' (API directa)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "texto": "FALLO DISCIPLINARIO. Expediente N.° 2023-XXX...",
                "norma": "ley_1952",
            }
        }
    }


class Hallazgo(BaseModel):
    """Unidad atómica de hallazgo devuelta por cada agente."""
    id: int
    modulo: str = Field(..., description="Código del criterio: 'M14', 'CEDIA-013', etc.")
    agente: str = Field(..., description="Agente que lo detectó: FORMA | ESTILO | COHERENCIA | FONDO | NORMATIVO")
    ubicacion: str = Field(..., description="Cita textual breve del fragmento problemático")
    error: str = Field(..., description="Descripción del error detectado")
    justificacion: str = Field(..., description="Por qué es un error — regla, principio o criterio")
    correccion: str = Field(..., description="Redacción corregida o sugerencia concreta")
    severidad: Literal["alta", "media", "baja"]
    nivel_severidad: int = Field(..., description="3=alta · 2=media · 1=baja — para ordenar")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "modulo": "CEDIA-007",
                "agente": "FORMA",
                "ubicacion": "incurrio en falta",
                "error": "Falta tilde en 'incurrió'",
                "justificacion": "Verbo en pretérito perfecto simple lleva tilde según RAE 2010",
                "correccion": "incurrió",
                "severidad": "media",
                "nivel_severidad": 2,
            }
        }
    }


class ResultadoAgente(BaseModel):
    agente: str
    puntaje: float = Field(..., ge=0, le=100)
    resumen: str
    hallazgos: list[Hallazgo] = Field(default_factory=list)
    fortalezas: list[str] = Field(default_factory=list)
    recomendaciones: list[str] = Field(default_factory=list)


class Estadisticas(BaseModel):
    total_agentes: int
    agentes_exitosos: int
    puntaje_promedio: float
    puntaje_maximo: float
    puntaje_minimo: float
    norma_aplicada: str
    distribucion_puntajes: dict[str, float]
    conteo_severidad: dict[str, int] = Field(default_factory=dict)


class AnalisisResponse(BaseModel):
    puntaje: float = Field(..., ge=0, le=100, description="Puntaje global de 0 a 100")
    nivel: str = Field(..., description="DEFICIENTE / REGULAR / ACEPTABLE / BUENO / EXCELENTE")
    resumen: str = Field(..., description="Resumen ejecutivo consolidado")
    errores: list[str] = Field(..., description="Errores más graves en texto plano (para copiar)")
    hallazgos: list[Hallazgo] = Field(..., description="Todos los hallazgos ordenados por nivel_severidad desc")
    fortalezas: list[str]
    recomendaciones: list[str]
    estadisticas: Estadisticas
    detalle_agentes: list[ResultadoAgente]
