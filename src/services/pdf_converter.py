"""Convertidor híbrido PDF: fast path con PyMuPDF, fallback a Docling OCR."""

import base64
import os
from pathlib import Path

import fitz  # PyMuPDF
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions

from src.config import settings


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

    def _extraer_imagenes_pymupdf(
        self, file_path: str, images_dir: Path
    ) -> list[Path]:
        """Extrae imágenes embebidas de un PDF usando PyMuPDF."""
        doc = fitz.open(file_path)
        images_dir.mkdir(parents=True, exist_ok=True)
        extraidas: list[Path] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                images = page.get_images(full=True)
                for img_idx, img in enumerate(images):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    # Normalizar a PNG si es posible, sino conservar extensión
                    ext = "png" if image_ext in ("png", "PNG") else image_ext
                    img_name = f"page_{page_num + 1}_img_{img_idx + 1}.{ext}"
                    img_path = images_dir / img_name
                    img_path.write_bytes(image_bytes)
                    extraidas.append(img_path)
        finally:
            doc.close()

        return extraidas

    def _pymupdf_to_markdown(
        self, file_path: str, images_dir: Path
    ) -> str:
        """Extrae texto nativo + imágenes y genera Markdown con referencias."""
        doc = fitz.open(file_path)
        partes: list[str] = []
        images = self._extraer_imagenes_pymupdf(file_path, images_dir)

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                texto = page.get_text().strip()

                # Si la página tiene texto nativo, usarlo
                if texto:
                    partes.append(texto)
                else:
                    # Página sin texto (posible imagen escaneada) — insertar placeholder
                    partes.append(f"<!-- scanned page {page_num + 1} — no text detected -->")

                # Añadir imágenes de esta página al final
                page_images = [
                    img for img in images
                    if f"page_{page_num + 1}_" in img.name
                ]
                for img in page_images:
                    rel_path = str(img.relative_to(settings.STORAGE_IMAGES))
                    partes.append(f"\n![image]({rel_path})\n")
        finally:
            doc.close()

        return "\n\n".join(partes)

    def _docling_to_markdown(
        self, file_path: str, images_dir: Path
    ) -> str:
        """Fallback: Docling con OCR + extracción de imágenes."""
        converter = self._get_docling_converter()
        resultado = converter.convert(file_path)
        doc = resultado.document

        # Extraer imágenes de páginas como PNG
        images_dir.mkdir(parents=True, exist_ok=True)
        for page_no, page in doc.pages.items():
            if page.image:
                uri = str(page.image.uri)
                if uri.startswith("data:image"):
                    header, b64 = uri.split(",", 1)
                    img_data = base64.b64decode(b64)
                    img_path = images_dir / f"page_{page_no}.png"
                    img_path.write_bytes(img_data)

        md = doc.export_to_markdown()
        # Reemplazar placeholders de Docling con referencias locales
        # Docling usa <!-- image --> por cada imagen; no sabemos el orden exacto,
        # así que mantenemos los placeholders y el usuario puede referenciar.
        return md

    def convertir(self, file_path: str, doc_id: str) -> tuple[str, Path | None]:
        """
        Convierte un PDF a Markdown.

        Retorna: (markdown_content, images_dir) o (markdown_content, None) si no hay imágenes.
        """
        ext = Path(file_path).suffix.lower()
        if ext != ".pdf":
            # No es PDF — usar Docling directamente (DOCX, etc.)
            converter = DocumentConverter()
            resultado = converter.convert(file_path)
            return resultado.document.export_to_markdown(), None

        images_dir = settings.STORAGE_IMAGES / doc_id

        if self._es_texto_nativo(file_path):
            md = self._pymupdf_to_markdown(file_path, images_dir)
        else:
            md = self._docling_to_markdown(file_path, images_dir)

        # Si no se extrajo ninguna imagen, no reportar directorio
        if images_dir.exists() and any(images_dir.iterdir()):
            return md, images_dir
        return md, None
