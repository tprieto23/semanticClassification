"""Convertidor de documentos a Markdown.

PDF nativo    → pymupdf4llm (estructura: títulos, párrafos, tablas).
PDF escaneado → Docling con OCR (texto desde imagen).
DOCX          → Docling.

No extrae imágenes: solo interesa el texto estructurado.
"""

from pathlib import Path

import fitz  # PyMuPDF
import pymupdf4llm
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions


_MIN_TEXTO_NATIVO = 500  # chars — umbral para considerar un PDF nativo


class PdfConverter:
    """Convierte PDFs y DOCX a Markdown, priorizando texto nativo."""

    def __init__(self):
        self._docling_converter: DocumentConverter | None = None

    def _get_docling_converter(self) -> DocumentConverter:
        """Lazy-load del convertidor Docling con OCR (para escaneados)."""
        if self._docling_converter is None:
            opts = ThreadedPdfPipelineOptions(do_ocr=True, do_table_structure=False)
            self._docling_converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
        return self._docling_converter

    def _es_texto_nativo(self, file_path: str) -> bool:
        """Detecta si un PDF tiene texto nativo seleccionable."""
        doc = fitz.open(file_path)
        try:
            total = 0
            for page in doc:
                total += len(page.get_text().strip())
                if total > _MIN_TEXTO_NATIVO:
                    return True
            return total > _MIN_TEXTO_NATIVO
        finally:
            doc.close()

    def convertir(self, file_path: str) -> str:
        """Convierte un documento a Markdown y retorna el contenido."""
        ext = Path(file_path).suffix.lower()

        if ext != ".pdf":
            # DOCX y otros → Docling
            resultado = DocumentConverter().convert(file_path)
            return resultado.document.export_to_markdown()

        if self._es_texto_nativo(file_path):
            # PDF nativo → pymupdf4llm (Markdown estructurado, sin imágenes)
            return pymupdf4llm.to_markdown(file_path, write_images=False, show_progress=False)

        # PDF escaneado → Docling con OCR (sin extraer imágenes)
        resultado = self._get_docling_converter().convert(file_path)
        return resultado.document.export_to_markdown()
