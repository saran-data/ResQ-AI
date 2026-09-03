"""
ResQAI - Knowledge Base Models
Documents and chunked content stored for RAG retrieval.
Metadata is stored in PostgreSQL; embeddings in Qdrant.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class DocumentType(str, enum.Enum):
    NGO_PROFILE = "ngo_profile"
    RESTAURANT_PROFILE = "restaurant_profile"
    FOOD_SAFETY_GUIDELINE = "food_safety_guideline"
    FSSAI_REGULATION = "fssai_regulation"
    WHO_GUIDELINE = "who_guideline"
    GOVERNMENT_NOTIFICATION = "government_notification"
    DONATION_HISTORY = "donation_history"
    VOLUNTEER_REPORT = "volunteer_report"
    WEATHER_REPORT = "weather_report"
    TRAFFIC_REPORT = "traffic_report"
    DEMAND_REPORT = "demand_report"
    GENERAL = "general"


class KnowledgeDocument(BaseModel):
    """
    A source document ingested into the RAG knowledge base.
    The document is chunked, embedded, and stored in Qdrant.
    PostgreSQL keeps the metadata and tracks sync status.
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("idx_knowledge_documents_type", "document_type"),
        Index("idx_knowledge_documents_entity_id", "entity_id"),
        Index("idx_knowledge_documents_is_active", "is_active"),
        {"schema": "resqai"},
    )

    # ---- Classification ----
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type", schema="resqai"),
        nullable=False,
        index=True,
    )
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # ---- Entity Reference ----
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ---- Content ----
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Chunking & Embedding ----
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qdrant_collection: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_embedded_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Metadata ----
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Relationships ----
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(BaseModel):
    """
    A single chunk from a KnowledgeDocument.
    Each chunk has its own embedding stored in Qdrant.
    The qdrant_point_id maps this chunk to its vector in the collection.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("idx_knowledge_chunks_document_id", "document_id"),
        Index("idx_knowledge_chunks_qdrant_id", "qdrant_point_id"),
        {"schema": "resqai"},
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # FK defined as string to avoid circular import issues
        nullable=False,
        index=True,
    )

    # ---- Content ----
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Context ----
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Qdrant Reference ----
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    qdrant_collection: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ---- Retrieval Stats ----
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Metadata ----
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- Relationships ----
    document: Mapped["KnowledgeDocument"] = relationship(
        "KnowledgeDocument", back_populates="chunks"
    )
