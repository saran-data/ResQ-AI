"""
ResQAI - Audit Log Model
Immutable record of all write operations for compliance, security auditing,
and forensic analysis. Never updated or deleted.
"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .user import User


class AuditLog(BaseModel):
    """
    Append-only audit log.
    Every POST/PUT/PATCH/DELETE request is logged here, including
    the actor, the resource affected, the change, and the outcome.

    NOTE: This table should have NO update/delete permissions at the DB level.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_resource_id", "resource_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_request_id", "request_id"),
        {"schema": "resqai"},
    )

    # ---- Actor ----
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ---- Request ----
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    http_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    http_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(nullable=True)

    # ---- Resource ----
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # ---- Change Data ----
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    changed_fields: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ---- Context ----
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ---- Relationships ----
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
