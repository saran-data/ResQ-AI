"""
ResQAI - RBAC (Role-Based Access Control) Service
Permission definitions, role hierarchies, and FastAPI dependency injectors
for all protected endpoints.
"""

from enum import Enum
from typing import List, Optional, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User, UserRole, UserStatus
from app.repositories.user_repository import UserRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


# -------------------------------------------------------
# Permission Definitions
# -------------------------------------------------------
class Permission(str, Enum):
    """Fine-grained permissions for resource operations."""

    # Donation permissions
    DONATION_CREATE = "donation:create"
    DONATION_READ = "donation:read"
    DONATION_UPDATE = "donation:update"
    DONATION_DELETE = "donation:delete"
    DONATION_VERIFY_OTP = "donation:verify_otp"

    # Restaurant permissions
    RESTAURANT_CREATE = "restaurant:create"
    RESTAURANT_READ = "restaurant:read"
    RESTAURANT_UPDATE = "restaurant:update"
    RESTAURANT_VERIFY = "restaurant:verify"

    # NGO permissions
    NGO_CREATE = "ngo:create"
    NGO_READ = "ngo:read"
    NGO_UPDATE = "ngo:update"
    NGO_VERIFY = "ngo:verify"
    NGO_ACCEPT_DONATION = "ngo:accept_donation"

    # Volunteer permissions
    VOLUNTEER_READ = "volunteer:read"
    VOLUNTEER_UPDATE = "volunteer:update"
    VOLUNTEER_ASSIGN = "volunteer:assign"

    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # Admin permissions
    ADMIN_READ = "admin:read"
    ADMIN_USER_MANAGE = "admin:user_manage"
    ADMIN_SYSTEM = "admin:system"
    FRAUD_REVIEW = "fraud:review"

    # AI permissions
    AI_AGENT_TRIGGER = "ai:agent_trigger"
    AI_OVERRIDE = "ai:override"


# -------------------------------------------------------
# Role → Permission Matrix
# -------------------------------------------------------
ROLE_PERMISSIONS: dict[UserRole, List[Permission]] = {
    UserRole.SUPER_ADMIN: list(Permission),  # All permissions

    UserRole.ADMIN: [
        Permission.DONATION_READ, Permission.DONATION_UPDATE, Permission.DONATION_DELETE,
        Permission.RESTAURANT_READ, Permission.RESTAURANT_VERIFY,
        Permission.NGO_READ, Permission.NGO_VERIFY,
        Permission.VOLUNTEER_READ, Permission.VOLUNTEER_ASSIGN,
        Permission.ANALYTICS_READ, Permission.ANALYTICS_EXPORT,
        Permission.ADMIN_READ, Permission.ADMIN_USER_MANAGE,
        Permission.FRAUD_REVIEW, Permission.AI_AGENT_TRIGGER,
    ],

    UserRole.RESTAURANT_OWNER: [
        Permission.DONATION_CREATE, Permission.DONATION_READ, Permission.DONATION_UPDATE,
        Permission.RESTAURANT_READ, Permission.RESTAURANT_UPDATE,
        Permission.ANALYTICS_READ,
    ],

    UserRole.RESTAURANT_STAFF: [
        Permission.DONATION_CREATE, Permission.DONATION_READ,
        Permission.RESTAURANT_READ,
    ],

    UserRole.NGO_MANAGER: [
        Permission.DONATION_READ, Permission.NGO_ACCEPT_DONATION,
        Permission.NGO_READ, Permission.NGO_UPDATE,
        Permission.VOLUNTEER_READ,
        Permission.ANALYTICS_READ,
    ],

    UserRole.NGO_STAFF: [
        Permission.DONATION_READ, Permission.NGO_ACCEPT_DONATION,
        Permission.NGO_READ,
    ],

    UserRole.VOLUNTEER: [
        Permission.DONATION_READ, Permission.DONATION_VERIFY_OTP,
        Permission.VOLUNTEER_READ, Permission.VOLUNTEER_UPDATE,
    ],

    UserRole.DRIVER: [
        Permission.DONATION_READ, Permission.DONATION_VERIFY_OTP,
        Permission.VOLUNTEER_READ, Permission.VOLUNTEER_UPDATE,
    ],
}


def has_permission(user: User, permission: Permission) -> bool:
    """
    Check if a user has a specific permission.
    Checks role-based permissions first, then any extra permissions
    stored in user.permissions (for dynamic grants).

    Args:
        user: User model instance
        permission: Permission to check

    Returns:
        True if user has the permission
    """
    # Role-based check
    role_perms = ROLE_PERMISSIONS.get(user.role, [])
    if permission in role_perms:
        return True

    # Dynamic permission override
    if user.permissions and permission.value in user.permissions.get("grant", []):
        return True

    return False


def require_permission(permission: Permission) -> Callable:
    """
    FastAPI dependency factory for permission-based access control.

    Usage:
        @router.post("/donations")
        async def create_donation(
            _=Depends(require_permission(Permission.DONATION_CREATE)),
            ...
        ):
    """
    async def _check_permission(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}",
            )
        return current_user

    return _check_permission


def require_roles(*roles: UserRole) -> Callable:
    """
    FastAPI dependency factory that restricts endpoints to specific roles.

    Usage:
        @router.get("/admin/users")
        async def list_users(
            _=Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
            ...
        ):
    """
    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to roles: {[r.value for r in roles]}",
            )
        return current_user

    return _check_role


# -------------------------------------------------------
# Core Authentication Dependencies
# -------------------------------------------------------
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: resolve current user from JWT token.
    Used as a base for all authenticated endpoints.

    Raises:
        HTTPException 401: Token invalid
        HTTPException 401: User not found or deleted
        HTTPException 403: Account suspended
    """
    user_repo = UserRepository(db)
    user = await user_repo.get(UUID(user_id))

    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.status in (UserStatus.SUSPENDED, UserStatus.BANNED):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {user.status.value}",
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: current user must be ACTIVE."""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    return current_user


# Role-specific convenience dependencies
async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: restrict to admins and super admins."""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_restaurant_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: restrict to restaurant owners and staff."""
    if current_user.role not in (UserRole.RESTAURANT_OWNER, UserRole.RESTAURANT_STAFF):
        raise HTTPException(status_code=403, detail="Restaurant account required")
    return current_user


async def get_ngo_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: restrict to NGO managers and staff."""
    if current_user.role not in (UserRole.NGO_MANAGER, UserRole.NGO_STAFF):
        raise HTTPException(status_code=403, detail="NGO account required")
    return current_user


async def get_volunteer_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: restrict to volunteers and drivers."""
    if current_user.role not in (UserRole.VOLUNTEER, UserRole.DRIVER):
        raise HTTPException(status_code=403, detail="Volunteer account required")
    return current_user


def get_optional_user(
    db: AsyncSession = Depends(get_db),
) -> Callable:
    """
    Dependency for endpoints that work for both authenticated and anonymous users.
    Returns None if no valid token provided.
    """
    async def _get_optional(
        user_id: Optional[str] = Depends(
            lambda credentials=None: (
                get_current_user_id(credentials) if credentials else None
            )
        ),
    ) -> Optional[User]:
        if not user_id:
            return None
        user_repo = UserRepository(db)
        return await user_repo.get(UUID(user_id))

    return _get_optional
