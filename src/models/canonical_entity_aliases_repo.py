from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.canonical_entity_aliases import CanonicalEntityAlias


class CanonicalEntityAliasRepo:

    @staticmethod
    def leer_todos(db: Session) -> list[CanonicalEntityAlias]:
        return list(db.scalars(select(CanonicalEntityAlias)).all())

    @staticmethod
    def registrar(
        db: Session,
        *,
        canonical_id: UUID,
        alias_text: str,
        normalized_alias: str,
        resolution_method: str,
        source_document_id: UUID | None,
    ) -> CanonicalEntityAlias:
        existente = db.scalar(
            select(CanonicalEntityAlias).where(
                CanonicalEntityAlias.canonical_id == canonical_id,
                CanonicalEntityAlias.normalized_alias == normalized_alias,
            )
        )
        if existente is not None:
            return existente

        alias = CanonicalEntityAlias(
            canonical_id=canonical_id,
            alias_text=alias_text,
            normalized_alias=normalized_alias,
            resolution_method=resolution_method,
            source_document_id=source_document_id,
        )
        db.add(alias)
        db.flush()
        return alias
