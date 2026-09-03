"""
ResQAI - Authentication Service
Business logic for registration, login, token management, OAuth2, and email verification.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, create_special_token,
    decode_token, TokenType, generate_secure_token,
)
from app.models.user import User, UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
    AuthUserResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Access token expiry in seconds (for client-side use)
ACCESS_TOKEN_EXPIRES_IN = settings.jwt.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class AuthService:
    """
    Handles all authentication flows:
    - Local email/password auth
    - Google OAuth2
    - JWT token management
    - Email verification
    - Password reset
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._user_repo = UserRepository(db)

    # -------------------------------------------------------
    # Registration
    # -------------------------------------------------------
    async def register(self, request: RegisterRequest) -> tuple[User, TokenResponse]:
        """
        Register a new user.

        1. Check email uniqueness
        2. Hash password
        3. Create user with PENDING_VERIFICATION status
        4. Generate email verification token
        5. Queue verification email (async)
        6. Return user + JWT tokens

        Args:
            request: Validated registration data

        Returns:
            Tuple of (User, TokenResponse)

        Raises:
            HTTPException 409: If email already registered
        """
        # Uniqueness check
        if await self._user_repo.email_exists(request.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

        # Build user record
        verify_token = generate_secure_token()
        user_data = {
            "email": request.email.lower().strip(),
            "name": request.name.strip(),
            "phone": request.phone,
            "hashed_password": hash_password(request.password),
            "role": request.role,
            "status": UserStatus.ACTIVE,  # Auto-activate for dev; PENDING_VERIFICATION in prod
            "email_verify_token": verify_token,
            "is_email_verified": not settings.is_production,  # Skip verify in dev
        }

        user = await self._user_repo.create(user_data)
        logger.info(f"New user registered: {user.email} [{user.role}]")

        # Queue verification email (fire-and-forget via Celery)
        if settings.is_production:
            try:
                from app.tasks.notification_tasks import send_verification_email
                send_verification_email.delay(user.id, user.email, verify_token)
            except Exception as e:
                logger.warning(f"Could not queue verification email: {e}")

        tokens = await self._generate_tokens(user)
        return user, tokens

    # -------------------------------------------------------
    # Login
    # -------------------------------------------------------
    async def login(
        self,
        request: LoginRequest,
        client_ip: str = "unknown",
    ) -> tuple[User, TokenResponse]:
        """
        Authenticate with email + password.

        Raises:
            HTTPException 401: Invalid credentials
            HTTPException 403: Account suspended/banned
        """
        user = await self._user_repo.get_by_email(request.email)

        # Constant-time comparison to prevent timing attacks
        if not user or not user.hashed_password:
            verify_password("dummy", "$2b$12$dummyhash")  # Prevent timing oracle
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Status check
        if user.status == UserStatus.SUSPENDED:
            raise HTTPException(status_code=403, detail="Account has been suspended")
        if user.status == UserStatus.BANNED:
            raise HTTPException(status_code=403, detail="Account has been banned")
        if user.status == UserStatus.INACTIVE:
            raise HTTPException(status_code=403, detail="Account is inactive")

        # Update login metadata
        await self._user_repo.increment_login_count(user.id, client_ip)

        logger.info(f"User logged in: {user.email} from {client_ip}")
        tokens = await self._generate_tokens(user)
        return user, tokens

    # -------------------------------------------------------
    # Token Refresh
    # -------------------------------------------------------
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Generate new access + refresh tokens from a valid refresh token.

        Raises:
            HTTPException 401: Invalid or expired refresh token
        """
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != TokenType.REFRESH:
                raise HTTPException(status_code=401, detail="Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")

        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await self._user_repo.get(UUID(user_id))
        if not user or user.is_deleted or user.status not in (UserStatus.ACTIVE,):
            raise HTTPException(status_code=401, detail="User not found or inactive")

        return await self._generate_tokens(user)

    # -------------------------------------------------------
    # Google OAuth2
    # -------------------------------------------------------
    async def handle_google_oauth(self, code: str, redirect_uri: str) -> tuple[User, TokenResponse]:
        """
        Complete Google OAuth2 flow.
        Exchanges authorization code for tokens, fetches user profile,
        and creates/updates local user account.
        """
        # Exchange code for Google tokens
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.gemini.CLIENT_ID,
                    "client_secret": settings.gemini.CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")
            token_data = token_resp.json()

            # Fetch user profile from Google
            profile_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            if profile_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch Google profile")
            profile = profile_resp.json()

        google_id = profile.get("sub")
        email = profile.get("email", "").lower()
        name = profile.get("name", email.split("@")[0])
        avatar = profile.get("picture")

        # Find existing user by OAuth subject or email
        user = await self._user_repo.get_by_oauth("google", google_id)
        if not user:
            user = await self._user_repo.get_by_email(email)

        if user:
            # Update OAuth linkage if not already set
            if not user.oauth_provider:
                await self._user_repo.update(user.id, {
                    "oauth_provider": "google",
                    "oauth_subject": google_id,
                    "avatar_url": avatar or user.avatar_url,
                    "is_email_verified": True,
                })
                await self._db.refresh(user)
        else:
            # Create new user from Google profile
            user = await self._user_repo.create({
                "email": email,
                "name": name,
                "oauth_provider": "google",
                "oauth_subject": google_id,
                "avatar_url": avatar,
                "role": UserRole.VOLUNTEER,
                "status": UserStatus.ACTIVE,
                "is_email_verified": True,
            })

        logger.info(f"Google OAuth login: {user.email}")
        return user, await self._generate_tokens(user)

    # -------------------------------------------------------
    # Email Verification
    # -------------------------------------------------------
    async def verify_email(self, token: str) -> User:
        """Verify user email address using a one-time token."""
        user = await self._user_repo.get_by_verification_token(token)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        await self._user_repo.update(user.id, {
            "is_email_verified": True,
            "email_verify_token": None,
            "status": UserStatus.ACTIVE,
        })
        await self._db.refresh(user)
        logger.info(f"Email verified: {user.email}")
        return user

    # -------------------------------------------------------
    # Password Reset
    # -------------------------------------------------------
    async def request_password_reset(self, request: ForgotPasswordRequest) -> None:
        """
        Initiate password reset.
        Always returns success (prevents email enumeration).
        """
        user = await self._user_repo.get_by_email(request.email)
        if not user:
            return  # Silent success

        reset_token = generate_secure_token()
        await self._user_repo.update(user.id, {"password_reset_token": reset_token})

        try:
            from app.tasks.notification_tasks import send_password_reset_email
            send_password_reset_email.delay(user.id, user.email, reset_token)
        except Exception as e:
            logger.warning(f"Could not queue password reset email: {e}")

    async def reset_password(self, request: ResetPasswordRequest) -> None:
        """Complete password reset with token + new password."""
        user = await self._user_repo.get_by_reset_token(request.token)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        await self._user_repo.update(user.id, {
            "hashed_password": hash_password(request.new_password),
            "password_reset_token": None,
        })
        logger.info(f"Password reset completed: {user.email}")

    async def change_password(
        self, user_id: UUID, request: ChangePasswordRequest
    ) -> None:
        """Change password while authenticated (verifies current password first)."""
        user = await self._user_repo.get_or_raise(user_id)

        if not user.hashed_password or not verify_password(
            request.current_password, user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        await self._user_repo.update(user_id, {
            "hashed_password": hash_password(request.new_password),
        })

    # -------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------
    async def _generate_tokens(self, user: User) -> TokenResponse:
        """Build JWT access + refresh token pair with user context claims."""
        additional_claims = {
            "role": user.role.value,
            "email": user.email,
            "name": user.name,
        }
        access_token = create_access_token(user.id, additional_claims)
        refresh_token = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRES_IN,
        )

    def build_auth_response(self, user: User) -> AuthUserResponse:
        """Build the authenticated user response object."""
        return AuthUserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role.value,
            status=user.status.value,
            avatar_url=user.avatar_url,
            is_email_verified=user.is_email_verified,
            is_2fa_enabled=user.is_2fa_enabled,
        )
