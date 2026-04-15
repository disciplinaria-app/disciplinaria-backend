from pydantic import BaseModel, Field
from typing import Literal


class AnalisisRequest(BaseModel):
    texto: str = Field(..., min_length=50, description="Texto completo del documento jurídico disciplinario")
    norma: Literal["1123", "1952", "734"] = Field(..., description="Código de la norma aplicable")

    model_config = {
        "json_schema_extra": {
            "example": {
                "texto": "FALLO DISCIPLINARIO. Expediente N.° 2023-XXX...",
                "norma": "1952",
            }
        }
    }


class ResultadoAgente(BaseModel):
    agente: str
    puntaje: float = Field(..., ge=0, le=100)
    resumen: str
    errores: list[str]
    fortalezas: list[str]
    recomendaciones: list[str]


class Estadisticas(BaseModel):
    total_agentes: int
    agentes_exitosos: int
    puntaje_promedio: float
    puntaje_maximo: float
    puntaje_minimo: float
    norma_aplicada: str
    distribucion_puntajes: dict[str, float]


class AnalisisResponse(BaseModel):
    puntaje: float = Field(..., ge=0, le=100, description="Puntaje global de 0 a 100")
    nivel: str = Field(..., description="Nivel de calidad: DEFICIENTE / REGULAR / ACEPTABLE / BUENO / EXCELENTE")
    resumen: str = Field(..., description="Resumen ejecutivo consolidado")
    errores: list[str] = Field(..., description="Lista de errores o irregularidades detectadas")
    fortalezas: list[str] = Field(..., description="Aspectos positivos del documento")
    recomendaciones: list[str] = Field(..., description="Acciones correctivas recomendadas")
    estadisticas: Estadisticas
    detalle_agentes: list[ResultadoAgente] = Field(..., description="Resultado individual por cada agente")
