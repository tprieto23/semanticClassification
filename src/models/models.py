import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, BigInteger, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from src.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger)
    status = Column(Text, nullable=False, default="raw")
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column(JSONB, name="metadata")
    original_char_count = Column(Integer)
    cleaned_char_count = Column(Integer)
    reduction_percentage = Column(Float)
    cleaning_metadata = Column(JSONB)

    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.original_filename}, status={self.status})>"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    category = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text)
    context = Column(Text)
    position_start = Column(Integer)
    position_end = Column(Integer)
    confidence = Column(Float)
    metadata_ = Column(JSONB, name="metadata")
    created_at = Column(DateTime, default=datetime.utcnow)
    embedding = Column(Vector(384))

    document = relationship("Document", back_populates="entities")
    relationships_as_source = relationship(
        "Relationship",
        foreign_keys="Relationship.entity_source_id",
        back_populates="source_entity",
        cascade="all, delete-orphan"
    )
    relationships_as_target = relationship(
        "Relationship",
        foreign_keys="Relationship.entity_target_id",
        back_populates="target_entity",
        cascade="all, delete-orphan"
    )
    metrics = relationship("Metric", back_populates="entity", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Entity(id={self.id}, category={self.category}, text={self.text[:50]}...)>"


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_source_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    entity_target_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    weight = Column(Float, nullable=False)
    relationship_type = Column(Text)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    metadata_ = Column(JSONB, name="metadata")
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="relationships")
    source_entity = relationship(
        "Entity",
        foreign_keys=[entity_source_id],
        back_populates="relationships_as_source"
    )
    target_entity = relationship(
        "Entity",
        foreign_keys=[entity_target_id],
        back_populates="relationships_as_target"
    )

    def __repr__(self):
        return f"<Relationship(id={self.id}, source={self.entity_source_id}, target={self.entity_target_id})>"


class Graph(Base):
    __tablename__ = "graphs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    file_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    metrics = relationship("Metric", back_populates="graph", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Graph(id={self.id}, name={self.name})>"


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("graphs.id"))
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    metric_name = Column(Text, nullable=False)
    metric_value = Column(Float, nullable=False)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    graph = relationship("Graph", back_populates="metrics")
    entity = relationship("Entity", back_populates="metrics")

    def __repr__(self):
        return f"<Metric(id={self.id}, name={self.metric_name}, value={self.metric_value})>"
