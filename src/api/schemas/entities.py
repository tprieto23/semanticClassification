from pydantic import BaseModel


class EntityOut(BaseModel):
    text: str
    category: str
    start: int
    end: int
    sentence_id: str
    context: str | None = None
    ambiguity: str | None = None


class ExtractEntitiesResponse(BaseModel):
    document_id: str
    entities: list[EntityOut]


class FuzzyMatchingResponse(BaseModel):
    document_id: str
    entities: list[EntityOut]
