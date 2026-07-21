from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base


class CatalogLabel(Base):
    __tablename__ = "catalog_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    types: Mapped[list["CatalogType"]] = relationship(back_populates="label")


class CatalogType(Base):
    __tablename__ = "catalog_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    label_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_labels.id", ondelete="CASCADE"), nullable=False
    )

    label: Mapped["CatalogLabel"] = relationship(back_populates="types")
    nodes: Mapped[list["CatalogNode"]] = relationship(back_populates="type")


class CatalogNode(Base):
    __tablename__ = "catalog_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_types.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped["CatalogType"] = relationship(back_populates="nodes")


class CatalogAttribute(Base):
    __tablename__ = "catalog_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    values: Mapped[list["CatalogValue"]] = relationship(back_populates="attribute")


class CatalogValue(Base):
    __tablename__ = "catalog_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    attribute_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_attributes.id", ondelete="CASCADE"), nullable=False
    )

    attribute: Mapped["CatalogAttribute"] = relationship(back_populates="values")


class CatalogAmbiguityLevel(Base):
    __tablename__ = "catalog_ambiguity_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
