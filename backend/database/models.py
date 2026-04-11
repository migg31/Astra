from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


node_type_enum = ENUM(
    "IR", "AMC", "GM", "CS",
    name="node_type",
    create_type=False,
)

edge_type_enum = ENUM(
    "IMPLEMENTS", "ACCEPTABLE_MEANS", "GUIDANCE_FOR", "REFERENCES",
    "REQUIRES", "EQUIVALENT_TO", "SUPERSEDES", "IF_MINOR", "IF_MAJOR", "LEADS_TO",
    name="edge_type",
    create_type=False,
)


class RegulatoryNode(Base):
    __tablename__ = "regulatory_nodes"

    node_id: Mapped[UUID] = mapped_column(primary_key=True)
    node_type: Mapped[str] = mapped_column(node_type_enum)
    reference_code: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    hierarchy_path: Mapped[str] = mapped_column(Text)
    source_doc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("harvest_documents.doc_id"), nullable=True
    )
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (UniqueConstraint("node_type", "reference_code"),)


class RegulatoryEdge(Base):
    __tablename__ = "regulatory_edges"

    edge_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_node_id: Mapped[UUID] = mapped_column(ForeignKey("regulatory_nodes.node_id"))
    target_node_id: Mapped[UUID] = mapped_column(ForeignKey("regulatory_nodes.node_id"))
    relation: Mapped[str] = mapped_column(edge_type_enum)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    source_node: Mapped[RegulatoryNode] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped[RegulatoryNode] = relationship(foreign_keys=[target_node_id])

    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", "relation"),
        CheckConstraint("source_node_id <> target_node_id"),
    )
