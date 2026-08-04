from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.entities import Entity


class EntityRepo:

    @staticmethod
    def eliminar_por_documento(db: Session, document_id: UUID) -> None:
        db.query(Entity).filter(Entity.document_id == document_id).delete()
        db.commit()

    @staticmethod
    def reemplazar_entidades(
        db: Session, document_id: UUID, entidades: list[dict]
    ) -> None:
        db.query(Entity).filter(Entity.document_id == document_id).delete()

        now = datetime.now(timezone.utc)
        for ent in entidades:
            entity = Entity(
                document_id=document_id,
                category=ent.get("category", ""),
                text=ent["text"],
                position_start=ent["start"],
                position_end=ent["end"],
                sentence_id=ent.get("sentence_id"),
                context=ent.get("context"),
                ambiguity=ent.get("ambiguity"),
                created_at=now,
            )
            db.add(entity)
        db.commit()
