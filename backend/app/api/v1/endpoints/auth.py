"""
ResQAI - Authentication API Endpoints
POST /auth/register, /auth/login, /auth/refresh, /auth/logout
GET  /auth/me, /auth/google, /auth/google/callback
POST /auth/forgot-password, /auth/reset-password, /auth/change-password
POST /auth/verify-email
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
    VerifyEmailRequest, OAuthCallbackRequest, AuthUserResponse,
)
from app.schemas.base import ApiResponse, MessageResponse
from app.services.auth_service import AuthService
from app.services.rbac_service import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter()


# -------------------------------------------------------
# Registration
# -------------------------------------------------------
@router.post(
    "/register",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    request: RegisterRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user with email/password.

    - Validates password strength (uppercase, lowercase, digit, special char)
    - Checks email uniqueness
    - Sends verification email in production
    - Returns JWT tokens immediately

    **Roles**: No auth required
    """
    service = AuthService(db)
    user, tokens = await service.register(request)
    auth_user = service.build_auth_response(user)

    return ApiResponse.ok(
        data={"user": auth_user.model_dump(), "tokens": tokens.model_dump()},
        message="Registration successful",
    )


# -------------------------------------------------------
# Login
# -------------------------------------------------------
@router.post(
    "/login",
    response_model=ApiResponse[dict],
    summary="Login with email and password",
)
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email + password.
    Returns access token (30min) and refresh token (7 days).

    **Roles**: No auth required
    """
    client_ip = req.client.host if req.client else "unknown"
    service = AuthService(db)
    user, tokens = await service.login(request, client_ip=client_ip)
    auth_user = service.build_auth_response(user)

    return ApiResponse.ok(
        data={"user": auth_user.model_dump(), "tokens": tokens.model_dump()},
        message="Login successful",
    )


# -------------------------------------------------------
# Current User
# -------------------------------------------------------
@router.get(
    "/me",
    response_model=ApiResponse[AuthUserResponse],
    summary="Get current authenticated user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the currently authenticated user's profile.

    **Roles**: Any authenticated user
    """
    from app.services.auth_service import AuthService
    # Build response without DB hit (user already loaded by dependency)
    auth_user = AuthUserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        status=current_user.status.value,
        avatar_url=current_user.avatar_url,
        is_email_verified=current_user.is_email_verified,
        is_2fa_enabled=current_user.is_2fa_enabled,
    )
    return ApiResponse.ok(data=auth_user)


# -------------------------------------------------------
# Token Refresh
# -------------------------------------------------------
@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Refresh access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    Old refresh token is invalidated (rotation).

    **Roles**: No auth required (presents refresh token)
    """
    service = AuthService(db)
    tokens = await service.refresh_tokens(request.refresh_token)
    return ApiResponse.ok(data=tokens)


# -------------------------------------------------------
# Logout
# -------------------------------------------------------
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout current session",
)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout: invalidates the refresh token in the database.
    Client must discard the access token (it remains valid until expiry).

    **Roles**: Any authenticated user
    """
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    await repo.update(current_user.id, {"refresh_token_hash": None})
    return MessageResponse(message="Logged out successfully")


# -------------------------------------------------------
# Email Verification
# -------------------------------------------------------
@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email address",
)
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify email using the token sent during registration.

    **Roles**: No auth required
    """
    service = AuthService(db)
    await service.verify_email(request.token)
    return MessageResponse(message="Email verified successfully")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend email verification",
)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resend the verification email."""
    if current_user.is_email_verified:
        return MessageResponse(message="Email is already verified")

    from app.core.security import generate_secure_token
    from app.repositories.user_repository import UserRepository

    token = generate_secure_token()
    repo = UserRepository(db)
    await repo.update(current_user.id, {"email_verify_token": token})

    try:
        from app.tasks.notification_tasks import send_verification_email
        send_verification_email.delay(current_user.id, current_user.email, token)
    except Exception:
        pass

    return MessageResponse(message="Verification email sent")


# -------------------------------------------------------
# Password Reset
# -------------------------------------------------------
@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset email",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a password reset link to the provided email address.
    Always returns success (prevents email enumeration).

    **Roles**: No auth required
    """
    service = AuthService(db)
    await service.request_password_reset(request)
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Set a new password using the reset token from email.

    **Roles**: No auth required
    """
    service = AuthService(db)
    await service.reset_password(request)
    return MessageResponse(message="Password reset successfully. Please login.")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password while authenticated",
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change password by providing the current password.

    **Roles**: Any authenticated user
    """
    service = AuthService(db)
    await service.change_password(current_user.id, request)
    return MessageResponse(message="Password changed successfully")


# -------------------------------------------------------
# Google OAuth2
# -------------------------------------------------------
@router.get(
    "/google",
    summary="Initiate Google OAuth2 login",
    include_in_schema=True,
)
async def google_login():
    """
    Redirect user to Google OAuth2 consent screen.
    
    **Roles**: No auth required
    """
    import urllib.parse
    params = {
        "client_id": settings.gemini.CLIENT_ID,
        "redirect_uri": settings.gemini.REDIRECT_URI if hasattr(settings.gemini, 'REDIRECT_URI') else f"{settings.FRONTEND_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=google_url)


@router.get(
    "/google/callback",
    response_model=ApiResponse[dict],
    summary="Handle Google OAuth2 callback",
)
async def google_callback(
    code: str,
    state: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle OAuth2 authorization code from Google.
    Exchanges code for tokens, creates/updates user, returns JWT.

    **Roles**: No auth required
    """
    redirect_uri = f"{settings.FRONTEND_URL}/auth/google/callback"
    service = AuthService(db)
    user, tokens = await service.handle_google_oauth(code, redirect_uri)
    auth_user = service.build_auth_response(user)

    return ApiResponse.ok(
        data={"user": auth_user.model_dump(), "tokens": tokens.model_dump()},
        message="Google login successful",
    )
