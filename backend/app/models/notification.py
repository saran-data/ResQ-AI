"""
ResQAI - Notification Model
Multi-channel notification records (Email, SMS, WhatsApp, Push).
"""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .user import User
    from .donation import Donation


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationType(str, enum.Enum):
    DONATION_CREATED = "donation_created"
    DONATION_ANALYZED = "donation_analyzed"
    DONATION_MATCHED = "donation_matched"
    PICKUP_SCHEDULED = "pickup_scheduled"
    PICKUP_STARTED = "pickup_started"
    DELIVERY_STARTED = "delivery_started"
    DELIVERY_COMPLETED = "delivery_completed"
    OTP_GENERATED = "otp_generated"
    SAFETY_REJECTED = "safety_rejected"
    FRAUD_DETECTED = "fraud_detected"
    NGO_ACCEPTED = "ngo_accepted"
    NGO_REJECTED = "ngo_rejected"
    VOLUNTEER_ASSIGNED = "volunteer_assigned"
    SYSTEM_ALERT = "system_alert"
    WEEKLY_REPORT = "weekly_report"
    VERIFICATION_EMAIL = "verification_email"
    PASSWORD_RESET = "password_reset"
    WELCOME = "welcome"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"
    BOUNCED = "bounced"


class Notification(BaseModel):
    """
    Notification record for every message sent through the system.
    The Notification Agent uses MCP servers to deliver via each channel.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_id", "user_id"),
        Index("idx_notifications_donation_id", "donation_id"),
        Index("idx_notifications_status", "status"),
        Index("idx_notifications_type", "type"),
        Index("idx_notifications_channel", "channel"),
        Index("idx_notifications_created_at", "created_at"),
        {"schema": "resqai"},
    )

    # ---- Target ----
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    donation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.donations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---- Classification ----
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", schema="resqai"),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel", schema="resqai"),
        nullable=False,
    )

    # ---- Content ----
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Extra payload for deep links / actions"
    )
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ---- Recipients ----
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recipient_device_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ---- Delivery ----
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", schema="resqai"),
        nullable=False,
        default=NotificationStatus.PENDING,
        index=True,
    )
    sent_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivered_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    read_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Retry Logic ----
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=3, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ---- Relationships ----
    user: Mapped[Optional["User"]] = relationship("User", back_populates="notifications")
    donation: Mapped[Optional["Donation"]] = relationship(
        "Donation", back_populates="notifications"
    )
