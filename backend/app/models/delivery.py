"""
ResQAI - Delivery Model
Tracks a single food rescue delivery from pickup to drop-off confirmation.
"""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .donation import Donation
    from .volunteer import Volunteer
    from .ngo import NGO
    from .route import Route


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    HEADING_TO_PICKUP = "heading_to_pickup"
    AT_PICKUP = "at_pickup"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    NEAR_DESTINATION = "near_destination"
    AT_DESTINATION = "at_destination"
    DELIVERED = "delivered"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Delivery(BaseModel):
    """
    Delivery record linking a Donation to a Volunteer and NGO.
    Tracks real-time GPS position, timing, and status transitions.
    """

    __tablename__ = "deliveries"
    __table_args__ = (
        Index("idx_deliveries_donation_id", "donation_id"),
        Index("idx_deliveries_volunteer_id", "volunteer_id"),
        Index("idx_deliveries_ngo_id", "ngo_id"),
        Index("idx_deliveries_status", "status"),
        Index("idx_deliveries_created_at", "created_at"),
        {"schema": "resqai"},
    )

    # ---- FKs ----
    donation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.donations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.volunteers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ngo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.ngos.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ---- Status ----
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status", schema="resqai"),
        nullable=False,
        default=DeliveryStatus.PENDING,
        index=True,
    )
    status_history: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)

    # ---- Real-time GPS ----
    current_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_heading: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_location_update: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location_history: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Array of {lat, lng, timestamp, speed} for replay"
    )

    # ---- Timing ----
    estimated_pickup_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actual_pickup_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_delivery_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actual_delivery_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Distances & Duration ----
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pickup_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Confirmation ----
    otp_used: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    confirmed_by_ngo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by_volunteer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proof_photo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    digital_signature: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    # ---- Issues & Notes ----
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    food_condition_on_delivery: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Relationships ----
    donation: Mapped["Donation"] = relationship("Donation", back_populates="delivery")
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="deliveries")
    ngo: Mapped["NGO"] = relationship("NGO")
    route: Mapped[Optional["Route"]] = relationship(
        "Route", back_populates="delivery", uselist=False
    )
