"""
ResQAI - Donation Model
Central entity representing a food rescue event from creation to delivery confirmation.
"""

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin

if TYPE_CHECKING:
    from .restaurant import Restaurant
    from .ngo import NGO
    from .volunteer import Volunteer
    from .food_item import FoodItem
    from .delivery import Delivery
    from .ai_decision import AIDecision
    from .notification import Notification


class DonationStatus(str, enum.Enum):
    """
    Full lifecycle state machine for a donation.
    Transitions are managed by the AI Orchestrator and confirmed by humans.
    """
    DRAFT = "draft"
    PENDING_ANALYSIS = "pending_analysis"
    ANALYZED = "analyzed"
    SAFETY_CHECK = "safety_check"
    SAFETY_FAILED = "safety_failed"
    MATCHING = "matching"
    MATCHED = "matched"
    PICKUP_SCHEDULED = "pickup_scheduled"
    AWAITING_PICKUP = "awaiting_pickup"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Donation(BaseModel):
    """
    Food rescue event.
    Created by a restaurant, processed by AI agents, delivered to matched NGO.

    State machine:
        DRAFT → PENDING_ANALYSIS → ANALYZED → SAFETY_CHECK →
        MATCHING → MATCHED → PICKUP_SCHEDULED → PICKED_UP →
        IN_TRANSIT → DELIVERED → CONFIRMED
    """

    __tablename__ = "donations"
    __table_args__ = (
        Index("idx_donations_restaurant_id", "restaurant_id"),
        Index("idx_donations_status", "status"),
        Index("idx_donations_matched_ngo_id", "matched_ngo_id"),
        Index("idx_donations_volunteer_id", "volunteer_id"),
        Index("idx_donations_created_at", "created_at"),
        Index("idx_donations_pickup_location", "pickup_latitude", "pickup_longitude"),
        {"schema": "resqai"},
    )

    # ---- FKs ----
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.restaurants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    matched_ngo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.ngos.id", ondelete="SET NULL"),
        nullable=True,
    )
    volunteer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.volunteers.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---- Status ----
    status: Mapped[DonationStatus] = mapped_column(
        Enum(DonationStatus, name="donation_status", schema="resqai"),
        nullable=False,
        default=DonationStatus.DRAFT,
        index=True,
    )
    status_history: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Array of {status, timestamp, actor} transitions"
    )

    # ---- Summary (computed from food_items) ----
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_servings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_value_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Pickup Details ----
    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    pickup_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    pickup_window_start: Mapped[str] = mapped_column(String(50), nullable=False)
    pickup_window_end: Mapped[str] = mapped_column(String(50), nullable=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_at_pickup: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ---- Timestamps ----
    matched_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scheduled_pickup_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actual_pickup_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivered_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confirmed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Verification ----
    otp: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    otp_expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    otp_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # ---- AI Metadata ----
    ai_safety_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    models_used: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ---- Fraud Detection ----
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fraud_flags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # ---- Impact ----
    carbon_saved_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meals_equivalent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- NGO Feedback ----
    ngo_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ngo_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    volunteer_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Relationships ----
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="donations")
    matched_ngo: Mapped[Optional["NGO"]] = relationship(
        "NGO", back_populates="donations_received", foreign_keys=[matched_ngo_id]
    )
    volunteer: Mapped[Optional["Volunteer"]] = relationship(
        "Volunteer", foreign_keys=[volunteer_id]
    )
    food_items: Mapped[List["FoodItem"]] = relationship(
        "FoodItem", back_populates="donation", cascade="all, delete-orphan"
    )
    delivery: Mapped[Optional["Delivery"]] = relationship(
        "Delivery", back_populates="donation", uselist=False
    )
    ai_decisions: Mapped[List["AIDecision"]] = relationship(
        "AIDecision", back_populates="donation", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="donation", lazy="dynamic"
    )
