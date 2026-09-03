"""
ResQAI - Security & Authentication
JWT token generation/validation, password hashing, OAuth2 integration.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# -------------------------------------------------------
# Password Hashing
# -------------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Work factor — increase for stronger security
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The raw password to hash

    Returns:
        Bcrypt-hashed password string
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Args:
        plain_password: Raw password to check
        hashed_password: Stored bcrypt hash

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# -------------------------------------------------------
# JWT Token Management
# -------------------------------------------------------
class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    VERIFY_EMAIL = "verify_email"


def create_access_token(
    subject: Union[str, UUID],
    additional_claims: Optional[dict] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: Token subject (usually user ID)
        additional_claims: Extra claims to embed (roles, permissions, etc.)

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt.ACCESS_TOKEN_EXPIRE_MINUTES)

    claims = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": TokenType.ACCESS,
        "jti": _generate_jti(),
    }

    if additional_claims:
        claims.update(additional_claims)

    return jwt.encode(
        claims,
        settings.jwt.SECRET_KEY,
        algorithm=settings.jwt.ALGORITHM,
    )


def create_refresh_token(subject: Union[str, UUID]) -> str:
    """
    Create a JWT refresh token with longer expiry.

    Args:
        subject: Token subject (usually user ID)

    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt.REFRESH_TOKEN_EXPIRE_DAYS)

    claims = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": TokenType.REFRESH,
        "jti": _generate_jti(),
    }

    return jwt.encode(
        claims,
        settings.jwt.SECRET_KEY,
        algorithm=settings.jwt.ALGORITHM,
    )


def create_special_token(
    subject: Union[str, UUID],
    token_type: str,
    expire_minutes: int = 60,
) -> str:
    """
    Create a special-purpose token (password reset, email verification).

    Args:
        subject: Token subject
        token_type: One of TokenType constants
        expire_minutes: Token validity duration

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)

    claims = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": token_type,
        "jti": _generate_jti(),
    }

    return jwt.encode(
        claims,
        settings.jwt.SECRET_KEY,
        algorithm=settings.jwt.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT string to decode

    Returns:
        Decoded claims dictionary

    Raises:
        HTTPException 401: If token is invalid, expired, or malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.SECRET_KEY,
            algorithms=[settings.jwt.ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_user_id(token: str) -> str:
    """
    Extract the user ID from a valid JWT token.

    Args:
        token: Valid JWT access token

    Returns:
        User ID string

    Raises:
        HTTPException 401: If token is invalid or missing subject
    """
    payload = decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type or missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


# -------------------------------------------------------
# FastAPI Bearer Token Extractor
# -------------------------------------------------------
http_bearer = HTTPBearer(auto_error=False)


async def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> str:
    """
    FastAPI dependency: extract Bearer token from Authorization header.

    Raises:
        HTTPException 401: If no token is provided
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_current_user_id(
    token: str = Depends(get_token_from_header),
) -> str:
    """
    FastAPI dependency: validate token and return current user ID.
    """
    return extract_user_id(token)


# -------------------------------------------------------
# Internal helpers
# -------------------------------------------------------
def _generate_jti() -> str:
    """Generate a unique JWT ID for token revocation support."""
    import secrets
    return secrets.token_urlsafe(32)


def generate_otp(length: int = 6) -> str:
    """
    Generate a secure numeric OTP for pickup/delivery verification.

    Args:
        length: OTP digit length (default 6)

    Returns:
        Numeric OTP string
    """
    import random
    digits = "0123456789"
    return "".join(random.choices(digits, k=length))


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    Used for email verification, password reset links, API keys.

    Args:
        nbytes: Number of random bytes

    Returns:
        URL-safe base64 encoded token string
    """
    import secrets
    return secrets.token_urlsafe(nbytes)
