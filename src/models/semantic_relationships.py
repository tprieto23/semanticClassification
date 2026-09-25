from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class SemanticNetworkSourceEdge(Base):
    """Instantánea de una arista del GraphML de una partición Leiden."""

    __tablename__ = "semantic_network_source_edges"
    __table_args__ = (
        UniqueConstraint(
            "clustering_sha256",
            "source_canonical_id",
            "target_canonical_id",
            name="uq_meta_source_edge_partition_pair",
        ),
        Index("ix_meta_source_edges_partition", "clustering_sha256"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    clustering_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_graph_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_canonical_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    target_canonical_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    source_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    sentence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class SemanticNodeRelationship(Base):
    __tablename__ = "semantic_node_relationships"
    __table_args__ = (
        UniqueConstraint(
            "clustering_sha256", "source_node_id", "target_node_id", "formula_version",
            "minimum_source_edge_weight",
            name="uq_meta_relationship_formula",
        ),
        Index("ix_meta_relationships_partition", "clustering_sha256"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    clustering_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_graph_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_node_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("semantic_nodes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_node_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("semantic_nodes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    formula_version: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_source_edge_weight: Mapped[float] = mapped_column(Float, nullable=False)
    source_edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    mean_source_weight: Mapped[float] = mapped_column(Float, nullable=False)
    sentence_support_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    document_support_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="calculated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    source_node: Mapped["SemanticNode"] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped["SemanticNode"] = relationship(foreign_keys=[target_node_id])
