from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    original_filename: str
    file_path: str
    file_type: str
    file_size_bytes: int | None = None
    status: str
    uploaded_at: datetime
    metadata: dict[str, Any] | None = Field(None, validation_alias="metadata_")


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    skip: int
    limit: int