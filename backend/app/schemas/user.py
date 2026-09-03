"""
ResQAI - User Schemas
Request/response models for user CRUD and profile management.
"""

from typing import Optional
from uuid import UUID
from pydantic import EmailStr, Field

from .base import BaseSchema, TimestampSchema
from app.models.user import UserRole, UserStatus


class UserBase(BaseSchema):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    timezone: str = "Asia/Kolkata"
    preferred_language: str = "en"


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VOLUNTEER


class UserUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    avatar_url: Optional[str] = Field(default=None, max_length=1024)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = None
    preferred_language: Optional[str] = None
    notification_preferences: Optional[dict] = None


class UserResponse(UserBase, TimestampSchema):
    id: UUID
    role: UserRole
    status: UserStatus
    avatar_url: Optional[str] = None
    is_email_verified: bool
    is_phone_verified: bool
    is_2fa_enabled: bool
    last_login_at: Optional[str] = None
    login_count: int


class UserListResponse(BaseSchema):
    id: UUID
    name: str
    email: str
    role: UserRole
    status: UserStatus
    city: Optional[str] = None
    created_at: str
    is_email_verified: bool


class AdminUserUpdate(BaseSchema):
    """Admin-only fields that regular users cannot change."""
    status: Optional[UserStatus] = None
    role: Optional[UserRole] = None
    is_email_verified: Optional[bool] = None
    permissions: Optional[dict] = None


class UserProfileResponse(UserResponse):
    """Extended profile with related entity summaries."""
    restaurant_id: Optional[UUID] = None
    ngo_id: Optional[UUID] = None
    volunteer_id: Optional[UUID] = None
