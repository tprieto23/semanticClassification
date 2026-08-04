from pydantic import BaseModel


class EntityOut(BaseModel):
    text: str
    category: str
    start: int
    end: int
    context: str | None = None
    ambiguity: str | None = None


class ExtractEntitiesResponse(BaseModel):
    document_id: str
    entities: list[EntityOut]
