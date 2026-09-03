"""
ResQAI - Restaurants API Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from python_slugify import slugify

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.restaurant import (
    RestaurantCreate, RestaurantUpdate, RestaurantResponse,
    RestaurantListResponse, RestaurantImpactResponse,
)
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user, get_admin_user, get_restaurant_user
from app.repositories.restaurant_repository import RestaurantRepository
from app.services.cloudinary_service import CloudinaryService

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[RestaurantResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a restaurant",
)
async def create_restaurant(
    data: RestaurantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new restaurant/food donor profile.
    One user can own exactly one restaurant.
    Requires RESTAURANT_OWNER role (or admin).
    """
    if current_user.role not in (
        UserRole.RESTAURANT_OWNER, UserRole.ADMIN, UserRole.SUPER_ADMIN
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Restaurant owner role required")

    repo = RestaurantRepository(db)

    # Check if owner already has a restaurant
    existing = await repo.get_by_owner(current_user.id)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="You already have a registered restaurant")

    # Build unique slug
    base_slug = slugify(data.name)
    slug = base_slug
    counter = 1
    while await repo.get_by_slug(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    restaurant = await repo.create({
        **data.model_dump(),
        "slug": slug,
        "owner_id": current_user.id,
    })
    return ApiResponse.ok(
        data=RestaurantResponse.model_validate(restaurant),
        message="Restaurant registered. Pending admin verification.",
    )


@router.get(
    "",
    response_model=PaginatedResponse[RestaurantListResponse],
    summary="List restaurants",
)
async def list_restaurants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    city: Optional[str] = Query(default=None),
    verified_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    """Public list of active restaurants."""
    from app.models.restaurant import RestaurantStatus
    repo = RestaurantRepository(db)
    filters = {"status": RestaurantStatus.ACTIVE}
    if verified_only:
        filters["is_verified"] = True

    skip = (page - 1) * page_size
    restaurants, total = await repo.get_all(skip=skip, limit=page_size, filters=filters)
    return PaginatedResponse.ok(
        data=[RestaurantListResponse.model_validate(r) for r in restaurants],
        page=page, page_size=page_size, total=total,
    )


@router.get(
    "/my",
    response_model=ApiResponse[RestaurantResponse],
    summary="Get my restaurant profile",
)
async def get_my_restaurant(
    current_user: User = Depends(get_restaurant_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the restaurant owned by the current user."""
    repo = RestaurantRepository(db)
    restaurant = await repo.get_by_owner(current_user.id)
    if not restaurant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No restaurant found for this account")
    return ApiResponse.ok(data=RestaurantResponse.model_validate(restaurant))


@router.get(
    "/leaderboard",
    response_model=ApiResponse[list],
    summary="Restaurant impact leaderboard",
)
async def get_leaderboard(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Top restaurants by sustainability score."""
    repo = RestaurantRepository(db)
    restaurants = await repo.get_leaderboard(limit)
    return ApiResponse.ok(
        data=[RestaurantListResponse.model_validate(r).model_dump() for r in restaurants]
    )


@router.get(
    "/{restaurant_id}",
    response_model=ApiResponse[RestaurantResponse],
    summary="Get restaurant by ID",
)
async def get_restaurant(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = RestaurantRepository(db)
    restaurant = await repo.get_or_raise(restaurant_id)
    return ApiResponse.ok(data=RestaurantResponse.model_validate(restaurant))


@router.put(
    "/{restaurant_id}",
    response_model=ApiResponse[RestaurantResponse],
    summary="Update restaurant profile",
)
async def update_restaurant(
    restaurant_id: UUID,
    data: RestaurantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = RestaurantRepository(db)
    restaurant = await repo.get_or_raise(restaurant_id)

    # Only owner or admin can update
    if restaurant.owner_id != current_user.id and current_user.role not in (
        UserRole.ADMIN, UserRole.SUPER_ADMIN
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")

    updated = await repo.update(restaurant_id, data.model_dump(exclude_none=True))
    return ApiResponse.ok(data=RestaurantResponse.model_validate(updated))


@router.post(
    "/{restaurant_id}/logo",
    response_model=ApiResponse[dict],
    summary="Upload restaurant logo",
)
async def upload_logo(
    restaurant_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = RestaurantRepository(db)
    restaurant = await repo.get_or_raise(restaurant_id)

    if restaurant.owner_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")

    svc = CloudinaryService()
    result = await svc.upload_profile_image(file, "restaurants", str(restaurant_id))
    await repo.update(restaurant_id, {"logo_url": result["secure_url"]})
    return ApiResponse.ok(data={"logo_url": result["secure_url"]})


@router.patch(
    "/{restaurant_id}/verify",
    response_model=ApiResponse[RestaurantResponse],
    summary="Verify restaurant (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def verify_restaurant(
    restaurant_id: UUID,
    approved: bool = True,
    rejection_reason: Optional[str] = None,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin approves or rejects restaurant verification."""
    from app.models.restaurant import RestaurantStatus
    from datetime import datetime, timezone

    repo = RestaurantRepository(db)
    restaurant = await repo.get_or_raise(restaurant_id)

    update_data = {
        "is_verified": approved,
        "status": RestaurantStatus.ACTIVE if approved else RestaurantStatus.SUSPENDED,
        "verified_by": current_user.id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    if not approved and rejection_reason:
        update_data["rejection_reason"] = rejection_reason

    updated = await repo.update(restaurant_id, update_data)
    return ApiResponse.ok(
        data=RestaurantResponse.model_validate(updated),
        message="Restaurant verified" if approved else "Restaurant verification rejected",
    )
