from pathlib import Path

import fitz
from docx import Document as DocxDocument


SUPPORTED_TYPES = {"pdf", "docx"}


class UnsupportedFileTypeError(ValueError):
    pass


class ConversionError(RuntimeError):
    pass


def convert_pdf(file_path: str) -> str:
    try:
        with fitz.open(file_path) as pdf:
            pages = [page.get_text() for page in pdf]
        return "\n\n".join(pages).strip()
    except Exception as e:
        raise ConversionError(f"Failed to convert PDF: {e}") from e


def convert_docx(file_path: str) -> str:
    try:
        document = DocxDocument(file_path)
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except Exception as e:
        raise ConversionError(f"Failed to convert DOCX: {e}") from e


def convert_document(file_path: str, file_type: str) -> str:
    normalized = file_type.lower().lstrip(".")
    if normalized == "pdf":
        return convert_pdf(file_path)
    if normalized == "docx":
        return convert_docx(file_path)
    raise UnsupportedFileTypeError(
        f"File type '{file_type}' not supported. Supported types: {sorted(SUPPORTED_TYPES)}"
    )


def save_converted_text(text: str, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding="utf-8")
