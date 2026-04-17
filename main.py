import asyncio
import io
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

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


# ── Almacenamiento temporal de documentos procesados ─────────────────────────
# { archivo_id: (docx_bytes, timestamp, nombre_original) }
_archivos_temp: dict[str, tuple[bytes, float, str]] = {}
_EXPIRA_SEG = 3600  # 1 hora


def _limpiar_expirados() -> None:
    ahora = time.monotonic()
    for k in [k for k, (_, ts, _) in _archivos_temp.items() if ahora - ts > _EXPIRA_SEG]:
        del _archivos_temp[k]


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

    resultados = await asyncio.gather(
        agente_forma.ejecutar(request.texto, request.norma),
        agente_estilo_judicial.ejecutar(request.texto, request.norma),
        agente_coherencia_narrativa.ejecutar(request.texto, request.norma),
        agente_fondo_argumentativo.ejecutar(request.texto, request.norma),
        agente_normativo.ejecutar(request.texto, request.norma),
        return_exceptions=False,
    )

    respuesta = await consolidador.consolidar(list(resultados), request.norma)

    duracion = round(time.monotonic() - inicio, 2)
    respuesta.estadisticas.distribucion_puntajes["_duracion_segundos"] = duracion

    return respuesta


@app.post(
    "/analizar-archivo",
    response_model=AnalisisResponse,
    summary="Analizar .docx y generar documento revisado con control de cambios",
)
async def analizar_archivo(
    archivo: UploadFile = File(...),
    norma: str = Form(...),
) -> AnalisisResponse:
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Servicio de IA no configurado.")

    nombre = archivo.filename or "documento.docx"
    if not nombre.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")

    docx_bytes = await archivo.read()
    if len(docx_bytes) < 100:
        raise HTTPException(status_code=400, detail="El archivo está vacío o es inválido.")

    # Extraer texto del .docx
    from docx import Document as _DocxDoc
    try:
        doc_tmp = _DocxDoc(io.BytesIO(docx_bytes))
        texto = "\n".join(p.text for p in doc_tmp.paragraphs if p.text.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el .docx: {exc}")

    if len(texto) < 50:
        raise HTTPException(status_code=400, detail="El documento no contiene suficiente texto.")

    inicio = time.monotonic()

    resultados = await asyncio.gather(
        agente_forma.ejecutar(texto, norma),
        agente_estilo_judicial.ejecutar(texto, norma),
        agente_coherencia_narrativa.ejecutar(texto, norma),
        agente_fondo_argumentativo.ejecutar(texto, norma),
        agente_normativo.ejecutar(texto, norma),
        return_exceptions=False,
    )

    respuesta = await consolidador.consolidar(list(resultados), norma)

    # Generar .docx con control de cambios
    from agents.track_changes import generar_documento_revisado
    try:
        docx_revisado = generar_documento_revisado(docx_bytes, respuesta.hallazgos)
    except Exception:
        docx_revisado = docx_bytes  # fallback: retornar original sin modificar

    # Almacenar temporalmente
    from pathlib import Path as _Path
    archivo_id = str(uuid.uuid4())
    nombre_stem = _Path(nombre).stem
    _limpiar_expirados()
    _archivos_temp[archivo_id] = (docx_revisado, time.monotonic(), nombre_stem)

    duracion = round(time.monotonic() - inicio, 2)
    respuesta.estadisticas.distribucion_puntajes["_duracion_segundos"] = duracion
    respuesta.archivo_id = archivo_id

    return respuesta


@app.get("/descargar/{archivo_id}", summary="Descargar .docx revisado con control de cambios")
async def descargar_archivo(archivo_id: str) -> Response:
    _limpiar_expirados()
    if archivo_id not in _archivos_temp:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado (1 hora).")

    docx_bytes, _, nombre_stem = _archivos_temp[archivo_id]
    nombre_descarga = f"{nombre_stem}_DISCIPLINARIA_revisado.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nombre_descarga}"'},
    )
