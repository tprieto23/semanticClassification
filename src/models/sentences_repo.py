from uuid import UUID

from sqlalchemy.orm import Session

from src.models.sentences import Sentence


class SentenceRepo:
    @staticmethod
    def reemplazar_por_documento(
        db: Session,
        document_id: UUID,
        sentences: list[dict[str, object]],
    ) -> None:
        """Elimina las oraciones previas del documento y las reemplaza.

        Cada elemento de ``sentences`` debe tener al menos ``sentence_id`` y
        ``text``. El identificador de oración debe ser único dentro del documento.
        """
        db.query(Sentence).filter(Sentence.document_id == document_id).delete()
        for sentence in sentences:
            db.add(
                Sentence(
                    document_id=document_id,
                    sentence_id=str(sentence["sentence_id"]),
                    text=str(sentence["text"]),
                )
            )

    @staticmethod
    def eliminar_por_documento(db: Session, document_id: UUID) -> None:
        db.query(Sentence).filter(Sentence.document_id == document_id).delete()
