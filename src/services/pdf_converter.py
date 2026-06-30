"""Convertidor híbrido PDF: fast path con PyMuPDF, fallback a Docling OCR."""

from pathlib import Path

import fitz  # PyMuPDF
import pymupdf4llm  # extracción layout-aware (orden multicolumna + tablas)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions


_MIN_TEXTO_NATIVO = 500  # chars — umbral para considerar PDF nativo


class PdfConverter:
    """Convierte PDFs usando PyMuPDF (rápido) o Docling OCR (lento, fallback)."""

    def __init__(self):
        self._docling_converter: DocumentConverter | None = None

    def _get_docling_converter(self) -> DocumentConverter:
        """Lazy-load del convertidor Docling (con OCR)."""
        if self._docling_converter is None:
            opts = ThreadedPdfPipelineOptions(do_ocr=True, do_table_structure=False)
            self._docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
                }
            )
        return self._docling_converter

    def _es_texto_nativo(self, file_path: str) -> bool:
        """Detecta si un PDF tiene texto nativo seleccionable."""
        doc = fitz.open(file_path)
        try:
            total_texto = 0
            for page in doc:
                total_texto += len(page.get_text().strip())
                if total_texto > _MIN_TEXTO_NATIVO:
                    return True
            return total_texto > _MIN_TEXTO_NATIVO
        finally:
            doc.close()

    def _pymupdf_to_markdown(self, file_path: str) -> str:
        """Ruta FAST con extracción layout-aware (pymupdf4llm).

        Respeta el orden de lectura multicolumna y reconstruye las tablas como
        tablas Markdown, a diferencia de page.get_text() que aplanaba columnas
        y desordenaba el texto.

        Las imágenes embebidas se marcan con placeholders
        <!-- Start of picture text --> / <!-- End of picture text -->.
        """
        return pymupdf4llm.to_markdown(
            file_path,
            write_images=False,
            embed_images=False,
            show_progress=False,
        )

    def _docling_to_markdown(self, file_path: str) -> str:
        """Fallback OCR para PDFs escaneados o con muy poco texto nativo."""
        converter = self._get_docling_converter()
        resultado = converter.convert(file_path)
        return resultado.document.export_to_markdown()

    def convertir(self, file_path: str) -> str:
        """Convierte un archivo a Markdown.

        - PDFs nativos: PyMuPDF (rápido).
        - PDFs escaneados: Docling con OCR (fallback).
        - DOCX y otros formatos: Docling directamente.

        TODO: futura mejora — para PDFs nativos que contengan imágenes .png
        con texto relevante (por ejemplo tablas insertadas como imagen),
        combinar el markdown de PyMuPDF con OCR selectivo sobre esas imágenes,
        de modo que el documento final incluya tanto el texto nativo como el
        texto legible en las imágenes, todo en un solo archivo markdown.
        """
        ext = Path(file_path).suffix.lower()
        if ext != ".pdf":
            converter = DocumentConverter()
            resultado = converter.convert(file_path)
            return resultado.document.export_to_markdown()

        if self._es_texto_nativo(file_path):
            return self._pymupdf_to_markdown(file_path)
        return self._docling_to_markdown(file_path)
