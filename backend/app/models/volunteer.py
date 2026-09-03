"""
ResQAI - Volunteer & Vehicle Models
Volunteers perform pickups/deliveries. Each volunteer may have a registered vehicle.
"""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from .user import User
    from .delivery import Delivery
    from .vehicle import Vehicle


class VolunteerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_DELIVERY = "on_delivery"
    UNAVAILABLE = "unavailable"
    SUSPENDED = "suspended"


class Volunteer(BaseModel, SoftDeleteMixin):
    """
    Volunteer profile linked to a User account.
    Tracks availability, location, vehicle, and performance metrics.
    The Volunteer Agent uses these attributes for auto-assignment.
    """

    __tablename__ = "volunteers"
    __table_args__ = (
        Index("idx_volunteers_user_id", "user_id"),
        Index("idx_volunteers_status", "status"),
        Index("idx_volunteers_city", "city"),
        Index("idx_volunteers_location", "latitude", "longitude"),
        Index("idx_volunteers_geohash", "geohash"),
        {"schema": "resqai"},
    )

    # ---- FK to User ----
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ---- Identity ----
    badge_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    languages: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # ---- Status & Availability ----
    status: Mapped[VolunteerStatus] = mapped_column(
        Enum(VolunteerStatus, name="volunteer_status", schema="resqai"),
        nullable=False,
        default=VolunteerStatus.INACTIVE,
        index=True,
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    availability_schedule: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Weekly availability: {mon: [{from: '09:00', to: '18:00'}], ...}"
    )
    max_concurrent_deliveries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ---- Location (real-time, updated by mobile app) ----
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, index=True)
    last_location_update: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    service_radius_km: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    # ---- ID Verification ----
    id_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Aadhaar, PAN, etc.
    id_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    background_check_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Performance ----
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_distance_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_delivery_time_minutes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    on_time_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meals_delivered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    carbon_saved_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # ---- Relationships ----
    user: Mapped["User"] = relationship("User", back_populates="volunteer")
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", back_populates="volunteer", uselist=False
    )
    deliveries: Mapped[List["Delivery"]] = relationship(
        "Delivery", back_populates="volunteer", lazy="dynamic"
    )
