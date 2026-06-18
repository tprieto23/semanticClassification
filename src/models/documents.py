from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="raw", server_default=text("'raw'")
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, default=_utcnow
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    converted_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    images_path: Mapped[str | None] = mapped_column(Text, nullable=True)
