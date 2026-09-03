"""
ResQAI - User Repository
All database operations for the User model.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, UserStatus
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Data access layer for User entities.
    Extends BaseRepository with user-specific queries.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Find an active user by email address."""
        result = await self._db.execute(
            select(User).where(
                User.email == email.lower().strip(),
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: str, subject: str) -> Optional[User]:
        """Find user by OAuth provider + subject ID."""
        result = await self._db.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_subject == subject,
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_verification_token(self, token: str) -> Optional[User]:
        """Find user by email verification token."""
        result = await self._db.execute(
            select(User).where(
                User.email_verify_token == token,
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: str) -> Optional[User]:
        """Find user by password reset token."""
        result = await self._db.execute(
            select(User).where(
                User.password_reset_token == token,
                User.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        user = await self.get_by_email(email)
        return user is not None

    async def get_active_users_by_role(self, role: UserRole) -> list[User]:
        """Fetch all active users with a given role."""
        result = await self._db.execute(
            select(User).where(
                User.role == role,
                User.status == UserStatus.ACTIVE,
                User.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def increment_login_count(self, user_id: UUID, ip: str) -> None:
        """Update last login metadata."""
        from datetime import datetime, timezone
        from sqlalchemy import update
        await self._db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                login_count=User.login_count + 1,
                last_login_at=datetime.now(timezone.utc).isoformat(),
                last_login_ip=ip,
            )
        )
