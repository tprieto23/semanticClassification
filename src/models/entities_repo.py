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
                category=ent.get(
                    "category", ent.get("labels", [""])[0] if ent.get("labels") else ""
                ),
                text=ent["text"],
                context=ent.get("context"),
                ambiguity=ent.get("ambiguity"),
                label_id=ent.get("label_id"),
                type_id=ent.get("type_id"),
                node_id=ent.get("node_id"),
                attribute_id=ent.get("attribute_id"),
                value_id=ent.get("value_id"),
                ambiguity_id=ent.get("ambiguity_id"),
                created_at=now,
            )
            db.add(entity)
        db.commit()
