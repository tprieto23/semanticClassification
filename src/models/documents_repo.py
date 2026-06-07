from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.documents import Document


class DocumentRepo:

    @staticmethod
    def crear(db: Session, **datos_documento) -> Document:
        documento = Document(**datos_documento)
        db.add(documento)
        db.commit()
        db.refresh(documento)
        return documento

    @staticmethod
    def leer_todos(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        file_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Document], int]:
        q = select(Document)
        if file_type:
            q = q.where(Document.file_type == file_type)
        if status:
            q = q.where(Document.status == status)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        filas = list(
            db.scalars(
                q.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit)
            ).all()
        )
        return filas, total

    @staticmethod
    def leer_uno(db: Session, document_id) -> Document | None:
        return db.get(Document, document_id)

    @staticmethod
    def eliminar(db: Session, documento: Document) -> None:
        db.delete(documento)
        db.commit()

    @staticmethod
    def actualizar_status(db: Session, documento: Document, nuevo_status: str) -> None:
        documento.status = nuevo_status
        db.commit()
