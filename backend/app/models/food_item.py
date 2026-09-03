"""
ResQAI - Food Item Model
Individual food entries within a donation, enriched by the Food Analysis Agent.
"""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .donation import Donation


class FoodCategory(str, enum.Enum):
    COOKED_MEAL = "cooked_meal"
    RAW_PRODUCE = "raw_produce"
    BAKERY = "bakery"
    DAIRY = "dairy"
    BEVERAGES = "beverages"
    PACKAGED = "packaged"
    SNACKS = "snacks"
    DESSERTS = "desserts"
    GRAINS = "grains"
    PULSES = "pulses"
    CONDIMENTS = "condiments"
    OTHER = "other"


class FoodSafetyStatus(str, enum.Enum):
    PENDING = "pending"
    SAFE = "safe"
    CONDITIONALLY_SAFE = "conditionally_safe"
    UNSAFE = "unsafe"
    EXPIRED = "expired"


class FoodItem(BaseModel):
    """
    A single food entry within a donation.
    Images are uploaded to Cloudinary and analyzed by the Gemini vision model.
    """

    __tablename__ = "food_items"
    __table_args__ = (
        Index("idx_food_items_donation_id", "donation_id"),
        Index("idx_food_items_safety_status", "safety_status"),
        Index("idx_food_items_category", "category"),
        {"schema": "resqai"},
    )

    donation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.donations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ---- Basic Info ----
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[FoodCategory] = mapped_column(
        Enum(FoodCategory, name="food_category", schema="resqai"),
        nullable=False,
        default=FoodCategory.COOKED_MEAL,
    )

    # ---- Quantity ----
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg")
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_servings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    portions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Dietary ----
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_vegan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_halal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_jain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allergens: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    ingredients: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # ---- Time & Temperature ----
    preparation_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    best_before: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expiry_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    storage_temperature_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    storage_temperature_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requires_refrigeration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_freezing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Images (Cloudinary) ----
    image_urls: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    primary_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cloudinary_public_ids: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    # ---- Safety ----
    safety_status: Mapped[FoodSafetyStatus] = mapped_column(
        Enum(FoodSafetyStatus, name="food_safety_status", schema="resqai"),
        nullable=False,
        default=FoodSafetyStatus.PENDING,
        index=True,
    )
    safety_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- AI Analysis (Food Analysis Agent output) ----
    ai_analysis: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="""
        {
          confidence_score: float,
          detected_items: [str],
          estimated_servings: int,
          freshness_score: float (0-1),
          estimated_expiry_hours: int,
          classification: str,
          safety_score: float,
          recommendation: str,
          model_used: str,
          analysis_time_ms: int
        }
        """
    )
    ai_analyzed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Relationships ----
    donation: Mapped["Donation"] = relationship("Donation", back_populates="food_items")
