import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import ALLOWED_ORIGINS, OPENROUTER_API_KEY
from models.schemas import AnalisisRequest, AnalisisResponse
from agents import (
    agente_forma,
    agente_estilo_judicial,
    agente_coherencia_narrativa,
    agente_fondo_argumentativo,
    agente_normativo,
    consolidador,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENROUTER_API_KEY:
        print("ADVERTENCIA: OPENROUTER_API_KEY no está configurada.")
    yield


app = FastAPI(
    title="DISCIPLINAR[IA] API",
    description=(
        "Plataforma de revisión inteligente de documentos jurídicos disciplinarios colombianos. "
        "Analiza fallos, pliegos de cargos, autos de archivo y demás actuaciones mediante "
        "5 agentes IA especializados que operan en paralelo."
    ),
    version="1.0.0",
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


@app.get("/", summary="Estado del servicio")
async def raiz():
    return {
        "servicio": "DISCIPLINAR[IA] API",
        "version": "1.0.0",
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
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está configurado. Contacte al administrador.",
        )

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
