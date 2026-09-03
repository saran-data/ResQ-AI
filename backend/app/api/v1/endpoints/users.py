"""
ResQAI - Users API Endpoints
GET    /users/me/profile
PUT    /users/me
POST   /users/me/avatar
GET    /users/{user_id}         (admin)
GET    /users                   (admin)
PATCH  /users/{user_id}/status  (admin)
DELETE /users/{user_id}         (admin)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserUpdate, UserResponse, UserListResponse, AdminUserUpdate, UserProfileResponse
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user, get_admin_user, require_roles
from app.repositories.user_repository import UserRepository
from app.services.cloudinary_service import CloudinaryService

router = APIRouter()


@router.get(
    "/me",
    response_model=ApiResponse[UserProfileResponse],
    summary="Get current user's full profile",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns full profile of the authenticated user including linked entity IDs
    (restaurant_id, ngo_id, volunteer_id based on role).
    """
    # Build extended profile with linked entity
    profile_data = UserProfileResponse.model_validate(current_user)

    # Attach linked entity IDs
    if current_user.restaurant:
        profile_data.restaurant_id = current_user.restaurant.id
    if current_user.ngo:
        profile_data.ngo_id = current_user.ngo.id
    if current_user.volunteer:
        profile_data.volunteer_id = current_user.volunteer.id

    return ApiResponse.ok(data=profile_data)


@router.put(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Update current user profile",
)
async def update_my_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update name, phone, location, and notification preferences."""
    repo = UserRepository(db)
    updated = await repo.update(current_user.id, update_data.model_dump(exclude_none=True))
    return ApiResponse.ok(data=UserResponse.model_validate(updated), message="Profile updated")


@router.post(
    "/me/avatar",
    response_model=ApiResponse[dict],
    summary="Upload profile avatar",
)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and set a new profile picture."""
    cloudinary_svc = CloudinaryService()
    result = await cloudinary_svc.upload_profile_image(
        file, entity_type="users", entity_id=str(current_user.id)
    )
    repo = UserRepository(db)
    await repo.update(current_user.id, {"avatar_url": result["secure_url"]})
    return ApiResponse.ok(data={"avatar_url": result["secure_url"]})


# -------------------------------------------------------
# Admin-only endpoints
# -------------------------------------------------------
@router.get(
    "",
    response_model=PaginatedResponse[UserListResponse],
    summary="List all users (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: Optional[UserRole] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users with pagination and filtering."""
    repo = UserRepository(db)
    filters = {"role": role} if role else {}
    skip = (page - 1) * page_size
    users, total = await repo.get_all(skip=skip, limit=page_size, filters=filters)
    return PaginatedResponse.ok(
        data=[UserListResponse.model_validate(u) for u in users],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="Get a user by ID (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch any user by their UUID."""
    repo = UserRepository(db)
    user = await repo.get_or_raise(user_id)
    return ApiResponse.ok(data=UserResponse.model_validate(user))


@router.patch(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="Update user status or role (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def admin_update_user(
    user_id: UUID,
    update_data: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: change user status, role, or permissions."""
    repo = UserRepository(db)
    updated = await repo.update(user_id, update_data.model_dump(exclude_none=True))
    return ApiResponse.ok(data=UserResponse.model_validate(updated))


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Soft-delete a user (admin)",
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user (sets is_deleted=True, not physically removed)."""
    repo = UserRepository(db)
    await repo.soft_delete(user_id)
    return MessageResponse(message="User account deactivated")
