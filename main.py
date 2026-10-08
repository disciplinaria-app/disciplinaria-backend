import asyncio
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGINS, OPENROUTER_API_KEY
from models.schemas import (
    AnalisisRequest,
    AnalisisResponse,
    ContextoEnvio,
    DiagnosticoTriage,
    TriageRequest,
    TriageResponse,
)
from agents import (
    agente_forma,
    agente_estilo_judicial,
    agente_coherencia_narrativa,
    agente_fondo_argumentativo,
    agente_normativo,
    consolidador,
)
from services import extraccion_pdf, triage

MAX_ADJUNTOS = 10
MAX_BYTES_SOLICITUD = 40 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENROUTER_API_KEY:
        print("ADVERTENCIA: OPENROUTER_API_KEY no está configurada.")
    disponible, espanol, faltantes = extraccion_pdf.diagnosticar_ocr()
    if not disponible:
        print(
            "ADVERTENCIA: el reconocimiento óptico no está disponible; los PDF "
            f"escaneados no podrán analizarse. Falta: {', '.join(faltantes)}"
        )
    elif not espanol:
        print(
            "ADVERTENCIA: el diccionario español de tesseract no está instalado; "
            "el reconocimiento óptico operará en inglés."
        )
    yield


app = FastAPI(
    title="DISCIPLINAR[IA] API",
    description=(
        "Plataforma de revisión inteligente de documentos jurídicos disciplinarios colombianos. "
        "Analiza fallos, pliegos de cargos, autos de archivo y demás actuaciones mediante "
        "5 agentes IA especializados que operan en paralelo, y clasifica la correspondencia "
        "recibida en el correo institucional mediante un agente de triage."
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {str(exc)}"},
    )


def _exigir_ia_configurada() -> None:
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está configurado. Contacte al administrador.",
        )


@app.get("/", summary="Estado del servicio")
async def raiz():
    return {
        "servicio": "DISCIPLINAR[IA] API",
        "version": "1.1.0",
        "estado": "activo",
        "descripcion": "Análisis inteligente de documentos disciplinarios colombianos",
    }


@app.get("/health", summary="Health check para Railway")
async def health():
    return {"status": "ok"}


@app.post(
    "/analizar",
    response_model=AnalisisResponse,
    summary="Analizar documento disciplinario",
    description=(
        "Recibe el texto de un documento jurídico disciplinario colombiano y la norma aplicable. "
        "Lanza 5 agentes IA en paralelo (FORMA, ESTILO JUDICIAL, COHERENCIA NARRATIVA, "
        "FONDO ARGUMENTATIVO, NORMATIVO) y retorna un análisis consolidado con puntaje, errores, "
        "fortalezas y recomendaciones."
    ),
)
async def analizar(request: AnalisisRequest) -> AnalisisResponse:
    _exigir_ia_configurada()

    inicio = time.monotonic()

    # Ejecutar los 5 agentes en paralelo con asyncio.gather
    resultados = await asyncio.gather(
        agente_forma.ejecutar(request.texto, request.norma),
        agente_estilo_judicial.ejecutar(request.texto, request.norma),
        agente_coherencia_narrativa.ejecutar(request.texto, request.norma),
        agente_fondo_argumentativo.ejecutar(request.texto, request.norma),
        agente_normativo.ejecutar(request.texto, request.norma),
        return_exceptions=False,
    )

    # Consolidar los resultados en un único análisis
    respuesta = await consolidador.consolidar(list(resultados), request.norma)

    duracion = round(time.monotonic() - inicio, 2)
    respuesta.estadisticas.distribucion_puntajes["_duracion_segundos"] = duracion

    return respuesta


@app.get(
    "/correo/diagnostico",
    response_model=DiagnosticoTriage,
    summary="Verificar las dependencias del triage de correspondencia",
    description=(
        "Informa si el reconocimiento óptico está instalado en el entorno. Sin él, los PDF "
        "escaneados —que son buena parte de la correspondencia institucional— no pueden "
        "analizarse. Conviene consultarlo tras cada despliegue."
    ),
)
async def diagnostico_triage() -> DiagnosticoTriage:
    disponible, espanol, faltantes = extraccion_pdf.diagnosticar_ocr()
    return DiagnosticoTriage(
        ocr_disponible=disponible,
        idioma_espanol_disponible=espanol,
        componentes_faltantes=list(faltantes),
        limite_paginas_ocr=extraccion_pdf.MAX_PAGINAS_OCR,
        limite_bytes_adjunto=extraccion_pdf.MAX_BYTES_ADJUNTO,
    )


@app.post(
    "/correo/triage",
    response_model=TriageResponse,
    summary="Clasificar un correo recibido con sus adjuntos PDF",
    description=(
        "Recibe los datos del correo y sus adjuntos PDF. Extrae el texto de cada documento "
        "—con reconocimiento óptico cuando viene escaneado—, lo coteja contra la entidad y el "
        "radicado que el despacho había remitido, y devuelve una ficha con la materia real del "
        "documento, el término que fija y las incongruencias detectadas.\n\n"
        "El texto de los adjuntos no se devuelve ni se almacena: solo la ficha estructurada."
    ),
)
async def triage_correo(
    remitente: Annotated[str, Form(description="Dirección o nombre del remitente")],
    asunto: Annotated[str, Form(description="Asunto del correo")] = "",
    cuerpo: Annotated[str, Form(description="Cuerpo del correo, en texto plano o HTML")] = "",
    fecha_recepcion: Annotated[str | None, Form(description="Fecha de recepción AAAA-MM-DD")] = None,
    entidad_interpelada: Annotated[
        str | None, Form(description="Entidad a la que se dirigió la comunicación original")
    ] = None,
    radicado_enviado: Annotated[
        str | None, Form(description="Radicado con que se remitió la comunicación original")
    ] = None,
    asunto_enviado: Annotated[
        str | None, Form(description="Asunto de la comunicación original")
    ] = None,
    aplicar_ocr: Annotated[
        bool, Form(description="Aplicar reconocimiento óptico a los PDF escaneados")
    ] = True,
    archivos: Annotated[list[UploadFile], File(description="Adjuntos PDF del correo")] = [],
) -> TriageResponse:
    _exigir_ia_configurada()

    if len(archivos) > MAX_ADJUNTOS:
        raise HTTPException(
            status_code=413,
            detail=f"Se admiten como máximo {MAX_ADJUNTOS} adjuntos por correo.",
        )

    leidos: list[tuple[str, bytes]] = []
    acumulado = 0
    for archivo in archivos:
        contenido = await archivo.read()
        acumulado += len(contenido)
        if acumulado > MAX_BYTES_SOLICITUD:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Los adjuntos superan en conjunto el límite de "
                    f"{MAX_BYTES_SOLICITUD // (1024 * 1024)} MB."
                ),
            )
        leidos.append((archivo.filename or "adjunto.pdf", contenido))

    return await triage.procesar(
        remitente=remitente,
        asunto=asunto,
        cuerpo=cuerpo,
        fecha_recepcion=fecha_recepcion,
        contexto=ContextoEnvio(
            entidad_interpelada=entidad_interpelada,
            radicado_enviado=radicado_enviado,
            asunto_enviado=asunto_enviado,
        ),
        archivos=leidos,
        permitir_ocr=aplicar_ocr,
    )


@app.post(
    "/correo/triage/json",
    response_model=TriageResponse,
    summary="Clasificar un correo recibido, en una sola solicitud JSON",
    description=(
        "Variante en JSON para capas de ingesta que no pueden construir una solicitud "
        "multiparte, como un flujo de Power Automate dentro del tenant institucional. "
        "Cada adjunto viaja en base64 —y el servidor lo extrae, con reconocimiento óptico "
        "si viene escaneado— o bien ya convertido a texto. El cotejo y la clasificación son "
        "los mismos de la vía multiparte."
    ),
)
async def triage_correo_json(request: TriageRequest) -> TriageResponse:
    _exigir_ia_configurada()

    if len(request.adjuntos) > MAX_ADJUNTOS:
        raise HTTPException(
            status_code=413,
            detail=f"Se admiten como máximo {MAX_ADJUNTOS} adjuntos por correo.",
        )

    return await triage.procesar(
        remitente=request.remitente,
        asunto=request.asunto,
        cuerpo=request.cuerpo,
        fecha_recepcion=request.fecha_recepcion,
        contexto=request.contexto,
        adjuntos=request.adjuntos,
    )
