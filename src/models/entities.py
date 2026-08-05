from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.canonical_entities import CanonicalEntity
from src.models.database import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentence_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    ambiguity: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=lambda: datetime.now(timezone.utc)
    )

    document: Mapped["Document"] = relationship(backref="entities")  # noqa: F821
    canonical_entity: Mapped[CanonicalEntity] = relationship(backref="mentions")

    def __repr__(self) -> str:
        return f"<Entity {self.category}: {self.text[:50]}>"
