import json

from fastapi import UploadFile
from markitdown import MarkItDown
from sqlalchemy.orm import Session

from src.models.database import get_db  # noqa: F401 — pasamanos para api

from src.config import settings
from src.models.documents import Document
from src.models.documents_repo import DocumentRepo
from src.models.storage import Storage
from src.services.cleaning import CleaningService


class DocumentoError(Exception):
    def __init__(self, mensaje: str, codigo_http: int):
        self.mensaje = mensaje
        self.codigo_http = codigo_http
        super().__init__(mensaje)


class ArchivoSinNombre(DocumentoError):
    def __init__(self):
        super().__init__("El archivo debe tener un nombre", 400)


class MetadataInvalido(DocumentoError):
    def __init__(self, detalle: str):
        super().__init__(f"Metadata inválido: {detalle}", 422)


class DocumentoNoEncontrado(DocumentoError):
    def __init__(self, document_id: str):
        super().__init__(f"Documento {document_id} no encontrado", 404)


class DocumentoYaConvertido(DocumentoError):
    def __init__(self, document_id: str, status: str):
        super().__init__(f"Documento {document_id} ya está en estado '{status}'", 409)


class DocumentoNoConvertido(DocumentoError):
    def __init__(self, document_id: str, status: str):
        super().__init__(f"Documento {document_id} no está convertido (estado: '{status}')", 409)


class DocumentoNoLimpiado(DocumentoError):
    def __init__(self, document_id: str, status: str):
        super().__init__(f"Documento {document_id} no está limpiado (estado: '{status}')", 409)


class DocumentService:

    @staticmethod
    def cargar_documento(
        db: Session,
        file: UploadFile,
        metadata_json: str | None,
    ) -> Document:
        if not file.filename:
            raise ArchivoSinNombre()

        metadata: dict | None = None
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
                if not isinstance(metadata, dict):
                    raise ValueError("debe ser un objeto JSON")
            except (json.JSONDecodeError, ValueError) as e:
                raise MetadataInvalido(str(e))

        nombreInicial, ext, doc_id, nombreParaAlmacenar = Storage.preparar_nombre(file.filename)
        content = file.file.read()
        path = Storage.guardar(content, nombreParaAlmacenar, settings.STORAGE_RAW)

        return DocumentRepo.crear(
            db,
            id=doc_id,
            original_filename=nombreInicial,
            file_path=str(path),
            file_type=ext,
            file_size_bytes=len(content),
            metadata_=metadata,
        )

    @staticmethod
    def leer_todos(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        file_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Document], int]:
        return DocumentRepo.leer_todos(db, skip, limit, file_type, status)

    @staticmethod
    def leer_uno(db: Session, document_id: str) -> Document | None:
        return DocumentRepo.leer_uno(db, document_id)

    @staticmethod
    def eliminar(db: Session, documento: Document) -> None:
        Storage.eliminar(documento.file_path)
        DocumentRepo.eliminar(db, documento)

    @staticmethod
    def cargar_documentos(
        db: Session,
        files: list[UploadFile],
        metadata_json: str | None,
    ) -> list[Document]:
        return [
            DocumentService.cargar_documento(db, file, metadata_json)
            for file in files
        ]

    @staticmethod
    def convertir(db: Session, document_id: str) -> None:
        doc = DocumentRepo.leer_uno(db, document_id)
        if doc is None:
            raise DocumentoNoEncontrado(document_id)

        if doc.status != "raw":
            raise DocumentoYaConvertido(document_id, doc.status)

        md = MarkItDown()
        resultado = md.convert(doc.file_path)
        nombre_md = f"{doc.id}.md"

        path = Storage.guardar(resultado.text_content.encode("utf-8"), nombre_md, settings.STORAGE_CONVERTED)
        doc.converted_path = str(path)
        DocumentRepo.actualizar_status(db, doc, "converted")

    @staticmethod
    def convertir_varios(db: Session) -> dict:
        docs = DocumentRepo.leer_por_status(db, "raw")
        processed: list[str] = []
        errors: list[dict] = []

        for doc in docs:
            doc_id = str(doc.id)
            try:
                DocumentService.convertir(db, doc_id)
                processed.append(doc_id)
            except DocumentoError as e:
                errors.append({"id": doc_id, "error": e.mensaje})
                db.rollback()

        return {"processed": processed, "errors": errors}

    @staticmethod
    def limpiar(db: Session, document_id: str) -> None:
        doc = DocumentRepo.leer_uno(db, document_id)
        if doc is None:
            raise DocumentoNoEncontrado(document_id)

        if doc.status != "converted":
            raise DocumentoNoConvertido(document_id, doc.status)

        texto_md = doc.converted_path and Storage.leer(doc.converted_path)
        if not texto_md:
            raise DocumentoError("Archivo convertido no encontrado o vacío", 500)

        texto_limpio = CleaningService.limpiar(texto_md)
        nombre_txt = f"{doc.id}.txt"

        path = Storage.guardar(texto_limpio.encode("utf-8"), nombre_txt, settings.DATA_CLEANED)
        doc.cleaned_path = str(path)
        DocumentRepo.actualizar_status(db, doc, "cleaned")

    @staticmethod
    def limpiar_varios(db: Session) -> dict:
        docs = DocumentRepo.leer_por_status(db, "converted")
        processed: list[str] = []
        errors: list[dict] = []

        for doc in docs:
            doc_id = str(doc.id)
            try:
                DocumentService.limpiar(db, doc_id)
                processed.append(doc_id)
            except DocumentoError as e:
                errors.append({"id": doc_id, "error": e.mensaje})
                db.rollback()

        return {"processed": processed, "errors": errors}

    @staticmethod
    def revertir_limpieza(db: Session, document_id: str) -> None:
        doc = DocumentRepo.leer_uno(db, document_id)
        if doc is None:
            raise DocumentoNoEncontrado(document_id)

        if doc.status != "cleaned":
            raise DocumentoNoLimpiado(document_id, doc.status)

        if doc.cleaned_path:
            Storage.eliminar(doc.cleaned_path)
        doc.cleaned_path = None
        DocumentRepo.actualizar_status(db, doc, "converted")
