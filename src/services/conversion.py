from markitdown import MarkItDown
from sqlalchemy.orm import Session

from src.models.documents import Document
from src.models.documents_repo import DocumentRepo
from src.models.storage import Storage


class DocumentoNoEncontrado(Exception):
    pass


class DocumentoYaConvertido(Exception):
    pass


class ConversionService:

    @staticmethod
    def convertir(db: Session, document_id: str) -> None:
        doc = DocumentRepo.leer_uno(db, document_id)
        if doc is None:
            raise DocumentoNoEncontrado(f"Documento {document_id} no encontrado")

        if doc.status != "raw":
            raise DocumentoYaConvertido(
                f"Documento {document_id} ya está en estado '{doc.status}'"
            )

        md = MarkItDown()
        resultado = md.convert(doc.file_path)
        nombre_md = f"{doc.id}.md"

        Storage.guardar_convertido(resultado.text_content.encode("utf-8"), nombre_md)
        DocumentRepo.actualizar_status(db, doc, "converted")
