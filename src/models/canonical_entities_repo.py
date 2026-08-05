from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.canonical_entities import CanonicalEntity


class CanonicalEntityRepo:

    @staticmethod
    def crear(db: Session, canonical_name: str, category: str) -> CanonicalEntity:
        canonical_entity = CanonicalEntity(
            canonical_name=canonical_name,
            category=category,
        )
        db.add(canonical_entity)
        db.commit()
        db.refresh(canonical_entity)
        return canonical_entity

    @staticmethod
    def leer_uno(db: Session, canonical_id: UUID) -> CanonicalEntity | None:
        return db.get(CanonicalEntity, canonical_id)

    @staticmethod
    def buscar_por_nombre_y_categoria(
        db: Session, canonical_name: str, category: str
    ) -> CanonicalEntity | None:
        return db.scalar(
            select(CanonicalEntity).where(
                CanonicalEntity.canonical_name == canonical_name,
                CanonicalEntity.category == category,
            )
        )
