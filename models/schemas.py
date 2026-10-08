from pydantic import BaseModel, Field, model_validator
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


# ---------------------------------------------------------------------------
# Triage de correspondencia recibida (correo institucional + adjuntos PDF)
# ---------------------------------------------------------------------------

Severidad = Literal["ALTA", "MEDIA", "BAJA"]


class Alerta(BaseModel):
    codigo: str = Field(..., description="Código estable de la alerta, p. ej. ENTIDAD_DISTINTA")
    descripcion: str = Field(..., description="Explicación concreta del hallazgo")
    severidad: Severidad
    origen: Literal["COTEJO", "MODELO", "AMBOS"] = Field(
        ...,
        description=(
            "COTEJO: verificación determinista sobre el texto. MODELO: lectura del agente. "
            "AMBOS: ambas fuentes concurren, lo que eleva la confiabilidad del hallazgo."
        ),
    )


class Termino(BaseModel):
    fecha_limite: str | None = Field(None, description="Fecha límite en formato AAAA-MM-DD, si el documento la expresa")
    dias_restantes: int | None = Field(None, description="Días que restan hasta la fecha límite")
    fundamento: str | None = Field(None, description="Fragmento o norma en que se apoya el término")


class ContextoEnvio(BaseModel):
    """Lo que el usuario esperaba, para poder cotejarlo contra lo que llegó."""

    entidad_interpelada: str | None = Field(
        None, description="Entidad a la que se dirigió la comunicación original"
    )
    radicado_enviado: str | None = Field(
        None, description="Radicado u oficio con el que se remitió la comunicación original"
    )
    asunto_enviado: str | None = Field(None, description="Asunto de la comunicación original")


class AdjuntoEntrada(BaseModel):
    """
    Adjunto remitido por la capa de ingesta, en cualquiera de las dos formas.

    `contenido_base64` traslada el PDF íntegro y deja la extracción —incluido
    el reconocimiento óptico— en el servidor. Es la forma que conviene a un
    flujo de Power Automate, que no sabe leer PDF. `texto` sirve a una ingesta
    que ya extrajo el contenido por su cuenta.
    """

    nombre: str
    texto: str | None = None
    contenido_base64: str | None = Field(
        None, description="PDF completo codificado en base64; el servidor extrae el texto"
    )

    @model_validator(mode="after")
    def _exigir_una_forma(self) -> "AdjuntoEntrada":
        if not self.texto and not self.contenido_base64:
            raise ValueError(
                "Cada adjunto debe traer «texto» o «contenido_base64»."
            )
        return self


class TriageRequest(BaseModel):
    remitente: str = Field(..., description="Dirección o nombre del remitente del correo")
    asunto: str = Field("", description="Asunto del correo, que con frecuencia no refleja la materia real")
    cuerpo: str = Field("", description="Cuerpo del correo; puede venir en HTML o con la cadena de respuestas anidada")
    fecha_recepcion: str | None = Field(None, description="Fecha de recepción en formato AAAA-MM-DD")
    contexto: ContextoEnvio | None = None
    adjuntos: list[AdjuntoEntrada] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "remitente": "notificaciones@previsora.gov.co",
                "asunto": "RE: Oficio CNDJ-2025-0412",
                "cuerpo": "Cordial saludo, adjunto damos respuesta a su comunicación.",
                "fecha_recepcion": "2025-10-01",
                "contexto": {
                    "entidad_interpelada": "Fiduprevisora S.A.",
                    "radicado_enviado": "CNDJ-2025-0412",
                },
                "adjuntos": [
                    {
                        "nombre": "respuesta.pdf",
                        "texto": "LA PREVISORA S.A. COMPAÑÍA DE SEGUROS ...",
                    }
                ],
            }
        }
    }


class DocumentoProcesado(BaseModel):
    """Trazabilidad de cómo se obtuvo el texto de cada adjunto."""

    nombre: str
    paginas: int = Field(0, description="Páginas del documento")
    paginas_procesadas: int = Field(0, description="Páginas de las que efectivamente se extrajo texto")
    metodo: Literal["TEXTO_NATIVO", "OCR", "MIXTO", "NINGUNO"] = Field(
        "NINGUNO",
        description="TEXTO_NATIVO: PDF digital. OCR: documento escaneado reconocido. MIXTO: ambos. NINGUNO: sin texto recuperable.",
    )
    caracteres: int = 0
    advertencias: list[str] = Field(default_factory=list)
    texto: str = Field("", exclude=True, description="Texto extraído; no se incluye en la respuesta")


class ResultadoCotejo(BaseModel):
    """Verificación determinista, reproducible y ajena al modelo de lenguaje."""

    entidad_estado: Literal["COINCIDE", "DIFIERE", "INDETERMINADO"] = "INDETERMINADO"
    entidad_esperada_normalizada: str | None = None
    entidad_recibida_normalizada: str | None = None
    radicado_estado: Literal["COINCIDE", "NO_COINCIDE", "INDETERMINADO"] = "INDETERMINADO"
    radicados_esperados: list[str] = Field(default_factory=list)
    radicados_hallados: list[str] = Field(default_factory=list)


class TriageResponse(BaseModel):
    entidad_remitente: str | None = Field(None, description="Entidad que suscribe la comunicación recibida")
    tipo_acto: str = Field(..., description="Naturaleza del documento recibido")
    materia: str = Field(..., description="De qué trata realmente el documento, no lo que anuncia el asunto")
    resumen: str = Field(..., description="Síntesis breve de la comunicación")
    radicados: list[str] = Field(default_factory=list)
    expedientes: list[str] = Field(default_factory=list)
    requiere_actuacion: bool = False
    actuacion_sugerida: str | None = None
    termino: Termino | None = None
    alertas: list[Alerta] = Field(default_factory=list)
    urgencia: Severidad = "BAJA"
    documentos: list[DocumentoProcesado] = Field(default_factory=list)
    cotejo: ResultadoCotejo = Field(default_factory=ResultadoCotejo)
    advertencias: list[str] = Field(
        default_factory=list,
        description="Limitaciones del procesamiento que el lector debe conocer antes de confiar en la ficha",
    )


class DiagnosticoTriage(BaseModel):
    ocr_disponible: bool
    idioma_espanol_disponible: bool
    componentes_faltantes: list[str]
    limite_paginas_ocr: int
    limite_bytes_adjunto: int
