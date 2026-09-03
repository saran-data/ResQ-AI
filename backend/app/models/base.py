"""
ResQAI - SQLAlchemy Base Model
Shared mixin classes providing common columns and behaviors for all models.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, declared_attr

from app.core.database import Base


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at columns to any model.
    updated_at is automatically set via PostgreSQL trigger defined in init.sql.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Mixin that uses a UUID primary key (server-generated)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin for soft-deletion support.
    Records are marked deleted rather than physically removed,
    preserving audit history and foreign key integrity.
    """

    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def soft_delete(self) -> None:
        """Mark this record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)


class BaseModel(UUIDMixin, TimestampMixin, Base):
    """
    Abstract base for all ResQAI models.
    Provides: UUID PK, created_at, updated_at.
    Subclasses must define __tablename__ and __table_args__ with schema.
    """

    __abstract__ = True

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return {"schema": "resqai"}

    def to_dict(self) -> dict[str, Any]:
        """Serialize model to dict (excludes SQLAlchemy internals)."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"
