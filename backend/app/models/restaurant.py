"""
ResQAI - Restaurant Model
Represents food donors: restaurants, hotels, marriage halls, catering, bakeries, cafeterias.
"""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from .user import User
    from .donation import Donation


class RestaurantType(str, enum.Enum):
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    MARRIAGE_HALL = "marriage_hall"
    CATERING = "catering"
    BAKERY = "bakery"
    CORPORATE_CAFETERIA = "corporate_cafeteria"
    CLOUD_KITCHEN = "cloud_kitchen"
    FOOD_COURT = "food_court"
    OTHER = "other"


class RestaurantStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class Restaurant(BaseModel, SoftDeleteMixin):
    """
    Restaurant/food donor entity.
    Each restaurant belongs to one owner (User with RESTAURANT_OWNER role).
    Tracks FSSAI license, geolocation, and cumulative impact metrics.
    """

    __tablename__ = "restaurants"
    __table_args__ = (
        Index("idx_restaurants_owner_id", "owner_id"),
        Index("idx_restaurants_status", "status"),
        Index("idx_restaurants_city", "city"),
        Index("idx_restaurants_location", "latitude", "longitude"),
        UniqueConstraint("fssai_license", name="uq_restaurant_fssai", deferrable=True),
        {"schema": "resqai"},
    )

    # ---- Identity ----
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[RestaurantType] = mapped_column(
        Enum(RestaurantType, name="restaurant_type", schema="resqai"),
        nullable=False,
        default=RestaurantType.RESTAURANT,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Contact ----
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ---- Address ----
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)

    # ---- Geolocation ----
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, index=True)

    # ---- Compliance ----
    fssai_license: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fssai_expiry: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    registration_certificate: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # ---- Media ----
    logo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    images: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True, default=list)

    # ---- Status / Verification ----
    status: Mapped[RestaurantStatus] = mapped_column(
        Enum(RestaurantStatus, name="restaurant_status", schema="resqai"),
        nullable=False,
        default=RestaurantStatus.PENDING_VERIFICATION,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    verified_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Operational ----
    operating_hours: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Weekly schedule: {mon: {open: '09:00', close: '22:00'}, ...}"
    )
    avg_daily_surplus_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cuisine_types: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    serves_veg: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    serves_nonveg: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- Impact Metrics (Denormalized for quick queries) ----
    total_donations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_meals_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_weight_donated_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbon_saved_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    impact_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    sustainability_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # ---- Settings ----
    notification_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_insights_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_donate_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rag_embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ---- FK ----
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ---- Relationships ----
    owner: Mapped["User"] = relationship("User", back_populates="restaurant")
    donations: Mapped[List["Donation"]] = relationship(
        "Donation", back_populates="restaurant", lazy="dynamic"
    )
