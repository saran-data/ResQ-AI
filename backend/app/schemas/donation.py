"""
ResQAI - Donation Schemas
Full lifecycle request/response models for food rescue donations.
"""

from typing import List, Optional
from uuid import UUID
from pydantic import Field

from .base import BaseSchema, TimestampSchema
from app.models.donation import DonationStatus
from app.models.food_item import FoodCategory


class FoodItemCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    category: FoodCategory = FoodCategory.COOKED_MEAL
    description: Optional[str] = None
    quantity: float = Field(gt=0)
    unit: str = Field(default="kg", max_length=20)
    is_vegetarian: bool = True
    is_vegan: bool = False
    is_halal: bool = False
    is_jain: bool = False
    allergens: Optional[List[str]] = None
    preparation_time: Optional[str] = None
    best_before: Optional[str] = None
    requires_refrigeration: bool = False
    requires_freezing: bool = False


class FoodItemResponse(TimestampSchema):
    id: UUID
    donation_id: UUID
    name: str
    category: FoodCategory
    quantity: float
    unit: str
    estimated_servings: Optional[int] = None
    is_vegetarian: bool
    is_vegan: bool
    is_halal: bool
    allergens: Optional[List[str]] = None
    primary_image_url: Optional[str] = None
    safety_status: str
    ai_analysis: Optional[dict] = None


class DonationCreate(BaseSchema):
    food_items: List[FoodItemCreate] = Field(min_length=1)
    pickup_address: str = Field(min_length=10, max_length=500)
    pickup_latitude: float = Field(ge=-90, le=90)
    pickup_longitude: float = Field(ge=-180, le=180)
    pickup_window_start: str
    pickup_window_end: str
    special_instructions: Optional[str] = None
    contact_at_pickup: Optional[str] = None


class DonationUpdate(BaseSchema):
    pickup_address: Optional[str] = None
    pickup_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    pickup_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    pickup_window_start: Optional[str] = None
    pickup_window_end: Optional[str] = None
    special_instructions: Optional[str] = None


class DonationResponse(TimestampSchema):
    id: UUID
    restaurant_id: UUID
    status: DonationStatus
    total_items: int
    total_servings: int
    total_weight_kg: float
    pickup_address: str
    pickup_latitude: float
    pickup_longitude: float
    pickup_window_start: str
    pickup_window_end: str
    special_instructions: Optional[str] = None
    matched_ngo_id: Optional[UUID] = None
    volunteer_id: Optional[UUID] = None
    matched_at: Optional[str] = None
    scheduled_pickup_at: Optional[str] = None
    otp_verified: bool
    qr_code_url: Optional[str] = None
    ai_safety_score: Optional[float] = None
    ai_confidence_score: Optional[float] = None
    fraud_score: float
    is_flagged: bool
    carbon_saved_kg: Optional[float] = None
    food_items: List[FoodItemResponse] = []


class DonationListResponse(BaseSchema):
    id: UUID
    restaurant_id: UUID
    status: DonationStatus
    total_servings: int
    total_weight_kg: float
    pickup_window_start: str
    matched_ngo_id: Optional[UUID] = None
    created_at: str
    ai_safety_score: Optional[float] = None


class DonationOTPVerify(BaseSchema):
    """OTP verification at pickup."""
    otp: str = Field(min_length=4, max_length=10)


class DonationConfirm(BaseSchema):
    """NGO confirmation of received food."""
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback: Optional[str] = None
    food_condition: str = "good"


class DonationStatusUpdate(BaseSchema):
    """Manual status override (admin only)."""
    status: DonationStatus
    reason: Optional[str] = None
