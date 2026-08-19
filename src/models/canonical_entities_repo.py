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
        db.flush()
        return canonical_entity

    @staticmethod
    def leer_todas(db: Session) -> list[CanonicalEntity]:
        return list(db.scalars(select(CanonicalEntity)).all())

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
