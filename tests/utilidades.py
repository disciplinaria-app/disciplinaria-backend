"""
Generación de PDF de prueba.

Los documentos se construyen en memoria para que el repositorio no cargue
binarios y para poder probar el caso crítico: un PDF escaneado, sin capa de
texto, que solo el reconocimiento óptico puede leer.
"""

import io


def _escapar(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def construir_pdf_texto(lineas: list[str], tamano_fuente: int = 14) -> bytes:
    """Construye un PDF de una página con capa de texto nativa."""
    operaciones = [f"BT /F1 {tamano_fuente} Tf 50 740 Td"]
    for indice, linea in enumerate(lineas):
        if indice:
            operaciones.append(f"0 -{tamano_fuente + 8} Td")
        operaciones.append(f"({_escapar(linea)}) Tj")
    operaciones.append("ET")
    contenido = "\n".join(operaciones).encode("latin-1", errors="replace")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream",
    ]

    salida = io.BytesIO()
    salida.write(b"%PDF-1.4\n")
    desplazamientos: list[int] = []
    for numero, cuerpo in enumerate(objetos, start=1):
        desplazamientos.append(salida.tell())
        salida.write(f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n")

    inicio_xref = salida.tell()
    salida.write(f"xref\n0 {len(objetos) + 1}\n".encode())
    salida.write(b"0000000000 65535 f \n")
    for desplazamiento in desplazamientos:
        salida.write(f"{desplazamiento:010d} 00000 n \n".encode())
    salida.write(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    )
    return salida.getvalue()


def construir_pdf_escaneado(lineas: list[str], dpi: int = 200) -> bytes:
    """
    Construye un PDF sin capa de texto, como el oficio suscrito y digitalizado
    que remiten habitualmente las entidades.

    Rasteriza un PDF de texto y vuelve a empaquetar la imagen como PDF, de modo
    que el resultado solo sea legible mediante reconocimiento óptico.
    """
    from pdf2image import convert_from_bytes

    imagenes = convert_from_bytes(construir_pdf_texto(lineas, tamano_fuente=18), dpi=dpi)
    salida = io.BytesIO()
    imagenes[0].convert("L").save(salida, format="PDF")
    for imagen in imagenes:
        imagen.close()
    return salida.getvalue()
