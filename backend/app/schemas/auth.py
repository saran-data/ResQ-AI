"""
ResQAI - Authentication Schemas
Request/response models for login, registration, token management, and OAuth.
"""

from typing import Optional
from pydantic import EmailStr, Field, field_validator
import re

from .base import BaseSchema
from app.models.user import UserRole


class LoginRequest(BaseSchema):
    """Email + password login."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    remember_me: bool = False
    device_id: Optional[str] = None


class RegisterRequest(BaseSchema):
    """New user registration."""
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str
    role: UserRole = UserRole.VOLUNTEER
    organization_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce strong password: uppercase, lowercase, digit, special char."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits_only = re.sub(r"[^\d+]", "", v)
        if len(digits_only) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return v


class TokenResponse(BaseSchema):
    """JWT access + refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expiry


class RefreshTokenRequest(BaseSchema):
    """Refresh token to obtain new access token."""
    refresh_token: str


class ForgotPasswordRequest(BaseSchema):
    """Initiate password reset via email."""
    email: EmailStr


class ResetPasswordRequest(BaseSchema):
    """Complete password reset with token."""
    token: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class ChangePasswordRequest(BaseSchema):
    """Change password while authenticated."""
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class VerifyEmailRequest(BaseSchema):
    """Email verification via token."""
    token: str


class OAuthCallbackRequest(BaseSchema):
    """OAuth2 callback payload."""
    code: str
    state: Optional[str] = None
    redirect_uri: Optional[str] = None


class AuthUserResponse(BaseSchema):
    """Authenticated user info returned after login/register."""
    id: str
    email: str
    name: str
    role: str
    status: str
    avatar_url: Optional[str] = None
    is_email_verified: bool
    is_2fa_enabled: bool
