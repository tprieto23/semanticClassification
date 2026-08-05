from uuid import UUID, uuid4

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class CanonicalEntity(Base):
    __tablename__ = "canonical_entities"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<CanonicalEntity {self.category}: {self.canonical_name[:50]}>"
