from pydantic import BaseModel


class EntityOut(BaseModel):
    text: str
    category: str
    labels: list[str] = []
    context: str | None = None
    label_id: int | None = None
    type_id: int | None = None
    node_id: int | None = None
    attribute_id: int | None = None
    value_id: int | None = None
    ambiguity_id: int | None = None


class ExtractEntitiesResponse(BaseModel):
    document_id: str
    entities: list[EntityOut]
