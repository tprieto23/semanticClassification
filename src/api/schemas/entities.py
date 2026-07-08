from uuid import UUID

from pydantic import BaseModel


class EntityOut(BaseModel):
    text: str
    labels: list[str]
    start: int
    end: int
    confidence: float | None = None
    context: str | None = None


class ExtractEntitiesResponse(BaseModel):
    document_id: UUID
    entities: list[EntityOut]
