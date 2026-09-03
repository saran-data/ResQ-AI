"""
ResQAI - User Model
Represents all system actors: admins, restaurant owners, NGO managers, volunteers, drivers.
"""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from .restaurant import Restaurant
    from .ngo import NGO
    from .volunteer import Volunteer
    from .notification import Notification
    from .audit_log import AuditLog


class UserRole(str, enum.Enum):
    """Role-Based Access Control roles."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RESTAURANT_OWNER = "restaurant_owner"
    RESTAURANT_STAFF = "restaurant_staff"
    NGO_MANAGER = "ngo_manager"
    NGO_STAFF = "ngo_staff"
    VOLUNTEER = "volunteer"
    DRIVER = "driver"


class UserStatus(str, enum.Enum):
    """Account status flags."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    BANNED = "banned"


class User(BaseModel, SoftDeleteMixin):
    """
    Core user account model.
    Supports OAuth2 (Google) and local password authentication.
    One user can own one Restaurant OR manage one NGO OR be a Volunteer.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email", unique=True),
        Index("idx_users_phone", "phone"),
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
        {"schema": "resqai"},
    )

    # ---- Identity ----
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # ---- Authentication ----
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ---- RBAC ----
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", schema="resqai"),
        nullable=False,
        default=UserRole.VOLUNTEER,
        index=True,
    )
    permissions: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="Extra granular permissions beyond role defaults"
    )

    # ---- Status ----
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", schema="resqai"),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION,
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_fa_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # ---- Security tokens ----
    email_verify_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ---- Location ----
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    # ---- Notifications preferences ----
    notification_preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {
            "email": True,
            "sms": True,
            "whatsapp": True,
            "push": True,
        },
    )

    # ---- Metadata ----
    last_login_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    login_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # ---- Relationships ----
    restaurant: Mapped[Optional["Restaurant"]] = relationship(
        "Restaurant", back_populates="owner", uselist=False, lazy="selectin"
    )
    ngo: Mapped[Optional["NGO"]] = relationship(
        "NGO", back_populates="manager", uselist=False, lazy="selectin"
    )
    volunteer: Mapped[Optional["Volunteer"]] = relationship(
        "Volunteer", back_populates="user", uselist=False, lazy="selectin"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", lazy="dynamic"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", lazy="dynamic"
    )

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and not self.is_deleted

    @property
    def display_name(self) -> str:
        return self.name or self.email.split("@")[0]
