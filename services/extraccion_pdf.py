"""
Extracción de texto de adjuntos PDF, con reconocimiento óptico de respaldo.

Buena parte de la correspondencia de las entidades colombianas llega como
oficio suscrito y digitalizado: el PDF no contiene capa de texto y toda
extracción directa devuelve vacío. Omitir el reconocimiento óptico haría que
el sistema fallara justamente con los documentos más relevantes.

El OCR se aplica solo a las páginas cuya capa de texto resulta insuficiente,
y su ausencia en el entorno no interrumpe el procesamiento: se declara como
advertencia explícita, de modo que el lector nunca confunda «el documento no
dice nada» con «no se pudo leer el documento».
"""

import io
import shutil
import subprocess
from functools import lru_cache

from pypdf import PdfReader

from models.schemas import DocumentoProcesado

# Debajo de este número de caracteres útiles se presume página escaneada.
UMBRAL_CARACTERES_POR_PAGINA = 120
MAX_PAGINAS = 80
MAX_PAGINAS_OCR = 20
DPI_OCR = 300
MAX_BYTES_ADJUNTO = 25 * 1024 * 1024
IDIOMA_OCR = "spa"


@lru_cache(maxsize=1)
def diagnosticar_ocr() -> tuple[bool, bool, tuple[str, ...]]:
    """
    Verifica las dependencias del reconocimiento óptico.

    Devuelve (ocr_disponible, idioma_espanol_disponible, componentes_faltantes).
    El resultado se memoriza porque las dependencias del contenedor no cambian
    durante la vida del proceso.
    """
    faltantes: list[str] = []

    if not shutil.which("tesseract"):
        faltantes.append("tesseract-ocr (binario)")
    if not shutil.which("pdftoppm"):
        faltantes.append("poppler-utils (pdftoppm)")
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        faltantes.append("pytesseract (paquete Python)")
    try:
        import pdf2image  # noqa: F401
    except ImportError:
        faltantes.append("pdf2image (paquete Python)")

    disponible = not faltantes

    espanol = False
    if disponible:
        try:
            salida = subprocess.run(
                ["tesseract", "--list-langs"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            espanol = IDIOMA_OCR in salida.stdout.split()
        except (OSError, subprocess.SubprocessError):
            espanol = False
        if not espanol:
            faltantes.append(f"tesseract-ocr-{IDIOMA_OCR} (diccionario español)")

    return disponible, espanol, tuple(faltantes)


def _ocr_pagina(contenido: bytes, numero_pagina: int, idioma: str) -> str:
    """Reconoce el texto de una sola página. El número es base 1."""
    from pdf2image import convert_from_bytes
    import pytesseract

    imagenes = convert_from_bytes(
        contenido,
        dpi=DPI_OCR,
        first_page=numero_pagina,
        last_page=numero_pagina,
    )
    if not imagenes:
        return ""
    try:
        return pytesseract.image_to_string(imagenes[0], lang=idioma) or ""
    finally:
        for imagen in imagenes:
            imagen.close()


def extraer(contenido: bytes, nombre: str, permitir_ocr: bool = True) -> DocumentoProcesado:
    """
    Extrae el texto de un PDF y documenta cómo lo obtuvo.

    Nunca lanza excepción por un documento defectuoso: el fallo se registra
    como advertencia en el documento procesado, para que un adjunto corrupto
    no impida el triage de los demás.
    """
    documento = DocumentoProcesado(nombre=nombre)

    if not contenido:
        documento.advertencias.append("El archivo llegó vacío.")
        return documento

    if len(contenido) > MAX_BYTES_ADJUNTO:
        documento.advertencias.append(
            f"El archivo excede el límite de {MAX_BYTES_ADJUNTO // (1024 * 1024)} MB y no fue procesado."
        )
        return documento

    try:
        lector = PdfReader(io.BytesIO(contenido))
    except Exception as exc:
        documento.advertencias.append(f"No es un PDF legible: {exc}")
        return documento

    if lector.is_encrypted:
        try:
            # Muchos oficios se firman con cifrado sin contraseña de apertura.
            if lector.decrypt("") == 0:
                documento.advertencias.append(
                    "El PDF está protegido con contraseña y no pudo abrirse."
                )
                return documento
        except Exception as exc:
            documento.advertencias.append(f"El PDF está cifrado y no pudo abrirse: {exc}")
            return documento

    try:
        total_paginas = len(lector.pages)
    except Exception as exc:
        documento.advertencias.append(f"No se pudo determinar el número de páginas: {exc}")
        return documento

    documento.paginas = total_paginas
    tope = min(total_paginas, MAX_PAGINAS)
    if total_paginas > tope:
        documento.advertencias.append(
            f"El documento tiene {total_paginas} páginas; se procesaron las primeras {tope}."
        )

    textos: list[str] = []
    for indice in range(tope):
        try:
            textos.append(lector.pages[indice].extract_text() or "")
        except Exception:
            textos.append("")

    paginas_pobres = [
        i for i, t in enumerate(textos) if len(t.strip()) < UMBRAL_CARACTERES_POR_PAGINA
    ]
    paginas_nativas = tope - len(paginas_pobres)
    paginas_ocr = 0

    if paginas_pobres and permitir_ocr:
        disponible, espanol, faltantes = diagnosticar_ocr()
        if not disponible:
            documento.advertencias.append(
                "El documento parece escaneado y el reconocimiento óptico no está "
                f"disponible en este entorno (falta: {', '.join(faltantes)}). "
                "Su contenido no fue analizado."
            )
        else:
            idioma = IDIOMA_OCR if espanol else "eng"
            if not espanol:
                documento.advertencias.append(
                    "El diccionario español de tesseract no está instalado; se aplicó "
                    "reconocimiento en inglés y el texto puede contener errores."
                )
            por_reconocer = paginas_pobres[:MAX_PAGINAS_OCR]
            if len(paginas_pobres) > MAX_PAGINAS_OCR:
                documento.advertencias.append(
                    f"{len(paginas_pobres)} páginas requerían reconocimiento óptico; "
                    f"se procesaron {MAX_PAGINAS_OCR}."
                )
            for indice in por_reconocer:
                try:
                    reconocido = _ocr_pagina(contenido, indice + 1, idioma)
                except Exception as exc:
                    documento.advertencias.append(
                        f"Falló el reconocimiento óptico de la página {indice + 1}: {exc}"
                    )
                    continue
                if len(reconocido.strip()) > len(textos[indice].strip()):
                    textos[indice] = reconocido
                    paginas_ocr += 1
    elif paginas_pobres and not permitir_ocr:
        documento.advertencias.append(
            "El documento parece escaneado y el reconocimiento óptico fue desactivado "
            "para esta solicitud."
        )

    texto_completo = "\n\n".join(t.strip() for t in textos if t.strip()).strip()
    documento.texto = texto_completo
    documento.caracteres = len(texto_completo)
    documento.paginas_procesadas = sum(1 for t in textos if t.strip())

    if not texto_completo:
        documento.metodo = "NINGUNO"
        if not documento.advertencias:
            documento.advertencias.append(
                "No se recuperó texto alguno del documento; requiere lectura directa."
            )
    elif paginas_ocr and paginas_nativas:
        documento.metodo = "MIXTO"
    elif paginas_ocr:
        documento.metodo = "OCR"
    else:
        documento.metodo = "TEXTO_NATIVO"

    return documento
