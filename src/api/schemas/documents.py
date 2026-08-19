from datetime import datetime
from enum import IntEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncubatorNumber(IntEnum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8


class BatchProcessError(BaseModel):
    id: UUID
    error: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    original_filename: str
    file_path: str
    file_type: str
    file_size_bytes: int | None = None
    status: str
    incubator_number: int | None = None
    language: str | None = None
    uploaded_at: datetime
    metadata: dict[str, Any] | None = Field(None, validation_alias="metadata_")
    converted_path: str | None = None
    cleaned_path: str | None = None
    ner_path: str | None = None
    images_path: str | None = None


class DocumentLanguageUpdate(BaseModel):
    language: str | None = Field(
        None,
        min_length=2,
        max_length=10,
        description="Código o nombre corto de idioma (ej: es, en, pt, quechua).",
    )

    @field_validator("language")
    @classmethod
    def _language_minuscula(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower().strip()


class SetLanguageBatchRequest(BaseModel):
    document_ids: list[UUID]
    language: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Código o nombre corto de idioma (ej: es, en, pt).",
    )

    @field_validator("language")
    @classmethod
    def _language_minuscula(cls, value: str) -> str:
        return value.lower().strip()


class SetLanguageBatchResponse(BaseModel):
    updated: list[UUID]
    errors: list[BatchProcessError]


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    skip: int
    limit: int


class BatchProcessResponse(BaseModel):
    processed: list[UUID]
    errors: list[BatchProcessError]
