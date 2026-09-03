"""
ResQAI - NGO Model
Represents food receivers: NGOs, orphanages, old age homes, shelters, community kitchens.
"""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from .user import User
    from .donation import Donation
    from .volunteer import Volunteer


class NGOType(str, enum.Enum):
    NGO = "ngo"
    ORPHANAGE = "orphanage"
    OLD_AGE_HOME = "old_age_home"
    SHELTER = "shelter"
    COMMUNITY_KITCHEN = "community_kitchen"
    FOOD_BANK = "food_bank"
    RELIGIOUS_INSTITUTION = "religious_institution"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    OTHER = "other"


class NGOStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class NGO(BaseModel, SoftDeleteMixin):
    """
    NGO / food receiver entity.
    Tracks capacity, food preferences, dietary restrictions, service hours,
    and accumulates impact statistics.
    """

    __tablename__ = "ngos"
    __table_args__ = (
        Index("idx_ngos_manager_id", "manager_id"),
        Index("idx_ngos_status", "status"),
        Index("idx_ngos_city", "city"),
        Index("idx_ngos_type", "type"),
        Index("idx_ngos_location", "latitude", "longitude"),
        Index("idx_ngos_geohash", "geohash"),
        {"schema": "resqai"},
    )

    # ---- Identity ----
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[NGOType] = mapped_column(
        Enum(NGOType, name="ngo_type", schema="resqai"),
        nullable=False,
        default=NGOType.NGO,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mission_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Contact ----
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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

    # ---- Registration / Compliance ----
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    registration_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 80G, 12A, etc.
    pan_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    darpan_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # NGO Darpan
    fcra_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Verification ----
    status: Mapped[NGOStatus] = mapped_column(
        Enum(NGOStatus, name="ngo_status", schema="resqai"),
        nullable=False,
        default=NGOStatus.PENDING_VERIFICATION,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    verified_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fraud_flags: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # ---- Capacity & Operations ----
    beneficiaries_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capacity_per_day: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refrigeration_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    storage_capacity_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cold_storage_capacity_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Food Preferences ----
    food_preferences: Mapped[Optional[list]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
        comment="Accepted food types: ['cooked_meal', 'raw_produce', ...]"
    )
    dietary_restrictions: Mapped[Optional[list]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
        comment="Restrictions: ['no_beef', 'vegetarian_only', ...]"
    )
    allergen_restrictions: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    min_serving_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Schedule ----
    service_hours: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pickup_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    advance_notice_hours: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    # ---- Acceptance History (for AI Matching) ----
    acceptance_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_response_time_minutes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_donation_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Impact Metrics ----
    total_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_meals_distributed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_weight_received_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # ---- Media ----
    logo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # ---- RAG ----
    rag_embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    demand_forecast: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ---- FK ----
    manager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ---- Relationships ----
    manager: Mapped["User"] = relationship("User", back_populates="ngo")
    donations_received: Mapped[List["Donation"]] = relationship(
        "Donation", back_populates="matched_ngo", lazy="dynamic",
        foreign_keys="Donation.matched_ngo_id"
    )
