"""
ResQAI - Restaurant Schemas
"""

from typing import List, Optional
from uuid import UUID
from pydantic import EmailStr, Field, field_validator

from .base import BaseSchema, TimestampSchema
from app.models.restaurant import RestaurantType, RestaurantStatus


class RestaurantCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=255)
    type: RestaurantType = RestaurantType.RESTAURANT
    description: Optional[str] = None
    phone: str = Field(min_length=10, max_length=20)
    email: EmailStr
    website: Optional[str] = None
    address_line1: str = Field(min_length=5, max_length=255)
    address_line2: Optional[str] = None
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str = Field(min_length=5, max_length=10)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    fssai_license: Optional[str] = None
    gst_number: Optional[str] = None
    serves_veg: bool = True
    serves_nonveg: bool = True
    cuisine_types: Optional[List[str]] = None
    avg_daily_surplus_kg: Optional[float] = Field(default=None, ge=0)
    operating_hours: Optional[dict] = None


class RestaurantUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    serves_veg: Optional[bool] = None
    serves_nonveg: Optional[bool] = None
    cuisine_types: Optional[List[str]] = None
    avg_daily_surplus_kg: Optional[float] = None
    operating_hours: Optional[dict] = None
    notification_preferences: Optional[dict] = None


class RestaurantResponse(TimestampSchema):
    id: UUID
    name: str
    slug: str
    type: RestaurantType
    description: Optional[str] = None
    phone: str
    email: str
    website: Optional[str] = None
    address_line1: str
    city: str
    state: str
    pincode: str
    latitude: float
    longitude: float
    status: RestaurantStatus
    is_verified: bool
    fssai_license: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    serves_veg: bool
    serves_nonveg: bool
    cuisine_types: Optional[List[str]] = None
    total_donations: int
    total_meals_saved: int
    total_weight_donated_kg: float
    carbon_saved_kg: float
    sustainability_score: float
    impact_rank: Optional[int] = None
    owner_id: UUID


class RestaurantListResponse(BaseSchema):
    id: UUID
    name: str
    type: RestaurantType
    city: str
    state: str
    is_verified: bool
    status: RestaurantStatus
    total_donations: int
    total_meals_saved: int
    sustainability_score: float
    logo_url: Optional[str] = None


class RestaurantImpactResponse(BaseSchema):
    """Impact summary for the restaurant dashboard."""
    restaurant_id: UUID
    total_donations: int
    total_meals_saved: int
    total_weight_donated_kg: float
    carbon_saved_kg: float
    sustainability_score: float
    impact_rank: Optional[int] = None
    weekly_change: float = 0.0
    monthly_trend: List[dict] = []
