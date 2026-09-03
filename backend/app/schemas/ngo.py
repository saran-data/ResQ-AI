"""
ResQAI - NGO Schemas
"""

from typing import List, Optional
from uuid import UUID
from pydantic import EmailStr, Field

from .base import BaseSchema, TimestampSchema
from app.models.ngo import NGOType, NGOStatus


class NGOCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=255)
    type: NGOType = NGOType.NGO
    description: Optional[str] = None
    mission_statement: Optional[str] = None
    phone: str = Field(min_length=10, max_length=20)
    email: EmailStr
    website: Optional[str] = None
    contact_person: Optional[str] = None
    address_line1: str = Field(min_length=5, max_length=255)
    address_line2: Optional[str] = None
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str = Field(min_length=5, max_length=10)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    registration_number: Optional[str] = None
    pan_number: Optional[str] = None
    darpan_id: Optional[str] = None
    beneficiaries_count: int = Field(default=0, ge=0)
    capacity_per_day: int = Field(default=0, ge=0)
    storage_available: bool = False
    refrigeration_available: bool = False
    food_preferences: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    service_hours: Optional[dict] = None
    advance_notice_hours: int = Field(default=2, ge=0, le=72)


class NGOUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_person: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    capacity_per_day: Optional[int] = Field(default=None, ge=0)
    current_capacity: Optional[int] = Field(default=None, ge=0)
    storage_available: Optional[bool] = None
    refrigeration_available: Optional[bool] = None
    food_preferences: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    service_hours: Optional[dict] = None


class NGOResponse(TimestampSchema):
    id: UUID
    name: str
    slug: str
    type: NGOType
    description: Optional[str] = None
    phone: str
    email: str
    city: str
    state: str
    latitude: float
    longitude: float
    status: NGOStatus
    is_verified: bool
    beneficiaries_count: int
    capacity_per_day: int
    current_capacity: int
    storage_available: bool
    refrigeration_available: bool
    food_preferences: Optional[List[str]] = None
    dietary_restrictions: Optional[List[str]] = None
    acceptance_rate: float
    total_received: int
    total_meals_distributed: int
    logo_url: Optional[str] = None
    manager_id: UUID


class NGOListResponse(BaseSchema):
    id: UUID
    name: str
    type: NGOType
    city: str
    state: str
    is_verified: bool
    status: NGOStatus
    capacity_per_day: int
    current_capacity: int
    acceptance_rate: float
    total_received: int


class NGOCapacityUpdate(BaseSchema):
    """NGO manager updates current capacity."""
    current_capacity: int = Field(ge=0)
    notes: Optional[str] = None


class NGOMatchScore(BaseSchema):
    """AI-generated match score for NGO Matching Agent output."""
    ngo_id: UUID
    ngo_name: str
    match_score: float
    distance_km: float
    capacity_available: int
    reasoning: str
    dietary_compatible: bool
    storage_compatible: bool
    historical_acceptance: float
