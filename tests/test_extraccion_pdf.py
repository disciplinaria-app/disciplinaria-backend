"""Pruebas de la extracción de texto de adjuntos PDF."""

import pytest

from services import extraccion_pdf
from tests.utilidades import construir_pdf_escaneado, construir_pdf_texto

LINEAS = [
    "LA PREVISORA S.A. COMPANIA DE SEGUROS",
    "Radicado CNDJ-2025-0412",
    "Nos permitimos informar que esta entidad no es competente",
]

ocr_requerido = pytest.mark.skipif(
    not extraccion_pdf.diagnosticar_ocr()[0],
    reason="el reconocimiento óptico no está instalado en este entorno",
)


class TestPdfConCapaDeTexto:
    def test_extrae_el_texto_nativo(self):
        documento = extraccion_pdf.extraer(construir_pdf_texto(LINEAS), "oficio.pdf")
        assert documento.metodo == "TEXTO_NATIVO"
        assert documento.paginas == 1
        assert documento.paginas_procesadas == 1
        assert "CNDJ-2025-0412" in documento.texto
        assert documento.caracteres == len(documento.texto)
        assert documento.advertencias == []


class TestPdfEscaneado:
    @ocr_requerido
    def test_el_reconocimiento_optico_recupera_el_texto(self):
        """
        El oficio digitalizado carece de capa de texto. Sin reconocimiento
        óptico el sistema lo reportaría como vacío, que es justamente el
        documento que el destinatario necesita conocer.
        """
        escaneado = construir_pdf_escaneado(LINEAS)
        sin_ocr = extraccion_pdf.extraer(escaneado, "escaneado.pdf", permitir_ocr=False)
        assert sin_ocr.metodo == "NINGUNO"
        assert sin_ocr.advertencias

        con_ocr = extraccion_pdf.extraer(escaneado, "escaneado.pdf")
        assert con_ocr.metodo == "OCR"
        assert "PREVISORA" in con_ocr.texto.upper()
        assert "CNDJ-2025-0412" in con_ocr.texto

    def test_sin_ocr_se_advierte_en_lugar_de_reportar_documento_vacio(self):
        documento = extraccion_pdf.extraer(
            construir_pdf_escaneado(LINEAS), "escaneado.pdf", permitir_ocr=False
        )
        assert documento.metodo == "NINGUNO"
        assert any("escaneado" in a.lower() for a in documento.advertencias)


class TestDocumentosDefectuosos:
    def test_archivo_que_no_es_pdf_no_interrumpe_el_proceso(self):
        documento = extraccion_pdf.extraer(b"PK\x03\x04 contenido de un .docx", "anexo.docx")
        assert documento.metodo == "NINGUNO"
        assert documento.advertencias

    def test_archivo_vacio(self):
        documento = extraccion_pdf.extraer(b"", "vacio.pdf")
        assert documento.metodo == "NINGUNO"
        assert "vac" in documento.advertencias[0].lower()

    def test_archivo_que_excede_el_limite(self, monkeypatch):
        monkeypatch.setattr(extraccion_pdf, "MAX_BYTES_ADJUNTO", 10)
        documento = extraccion_pdf.extraer(construir_pdf_texto(LINEAS), "grande.pdf")
        assert documento.metodo == "NINGUNO"
        assert "límite" in documento.advertencias[0]


class TestDiagnostico:
    def test_informa_el_estado_de_las_dependencias(self):
        disponible, espanol, faltantes = extraccion_pdf.diagnosticar_ocr()
        assert isinstance(disponible, bool)
        assert isinstance(espanol, bool)
        # Si el reconocimiento está disponible, no puede haber componentes
        # ausentes del motor; a la inversa, la ausencia debe quedar enunciada.
        assert disponible or faltantes
