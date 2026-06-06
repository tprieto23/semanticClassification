import json

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.models.database import get_db  # noqa: F401 — pasamanos para api

from src.models.documents import Document
from src.models.documents_repo import DocumentRepo
from src.models.storage import Storage


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
        path = Storage.guardar(content, nombreParaAlmacenar)

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
