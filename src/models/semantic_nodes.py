from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class SemanticNode(Base):
    __tablename__ = "semantic_nodes"
    __table_args__ = (
        UniqueConstraint(
            "clustering_sha256", "community_id", name="uq_semantic_nodes_partition_community"
        ),
        Index("ix_semantic_nodes_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    projection_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_source: Mapped[str] = mapped_column(Text, nullable=False)
    community_id: Mapped[str] = mapped_column(Text, nullable=False)
    clustering_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    source_graph_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    incubator_support: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending_description"
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    members: Mapped[list["SemanticNodeMember"]] = relationship(
        back_populates="node", cascade="all, delete-orphan", lazy="selectin"
    )


class SemanticNodeMember(Base):
    __tablename__ = "semantic_node_members"
    __table_args__ = (
        UniqueConstraint(
            "semantic_node_id", "canonical_id", name="uq_semantic_node_member"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    semantic_node_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("semantic_nodes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    canonical_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("canonical_entities.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[SemanticNode] = relationship(back_populates="members")
