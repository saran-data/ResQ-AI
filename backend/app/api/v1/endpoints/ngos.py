"""
ResQAI - NGOs API Endpoints
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from python_slugify import slugify

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.ngo import (
    NGOCreate, NGOUpdate, NGOResponse, NGOListResponse, NGOCapacityUpdate,
)
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user, get_admin_user, get_ngo_user
from app.repositories.ngo_repository import NGORepository
from app.services.cloudinary_service import CloudinaryService

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[NGOResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register an NGO",
)
async def create_ngo(
    data: NGOCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new NGO. Requires NGO_MANAGER role."""
    if current_user.role not in (UserRole.NGO_MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="NGO manager role required")

    repo = NGORepository(db)
    existing = await repo.get_by_manager(current_user.id)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="You already manage an NGO")

    base_slug = slugify(data.name)
    slug = base_slug
    counter = 1
    while await repo.get_by_slug(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    ngo = await repo.create({
        **data.model_dump(),
        "slug": slug,
        "manager_id": current_user.id,
    })
    return ApiResponse.ok(
        data=NGOResponse.model_validate(ngo),
        message="NGO registered. Pending admin verification.",
    )


@router.get(
    "",
    response_model=PaginatedResponse[NGOListResponse],
    summary="List NGOs",
)
async def list_ngos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    city: Optional[str] = Query(default=None),
    verified_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    from app.models.ngo import NGOStatus
    repo = NGORepository(db)
    filters = {"status": NGOStatus.ACTIVE}
    if verified_only:
        filters["is_verified"] = True
    skip = (page - 1) * page_size
    ngos, total = await repo.get_all(skip=skip, limit=page_size, filters=filters)
    return PaginatedResponse.ok(
        data=[NGOListResponse.model_validate(n) for n in ngos],
        page=page, page_size=page_size, total=total,
    )


@router.get(
    "/my",
    response_model=ApiResponse[NGOResponse],
    summary="Get my NGO profile",
)
async def get_my_ngo(
    current_user: User = Depends(get_ngo_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NGORepository(db)
    ngo = await repo.get_by_manager(current_user.id)
    if not ngo:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No NGO found for this account")
    return ApiResponse.ok(data=NGOResponse.model_validate(ngo))


@router.get(
    "/nearby",
    response_model=ApiResponse[list],
    summary="Find nearby NGOs",
)
async def get_nearby_ngos(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(default=30.0, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    repo = NGORepository(db)
    ngos = await repo.get_nearby_ngos(latitude, longitude, radius_km)
    return ApiResponse.ok(data=[NGOListResponse.model_validate(n).model_dump() for n in ngos])


@router.get(
    "/{ngo_id}",
    response_model=ApiResponse[NGOResponse],
    summary="Get NGO by ID",
)
async def get_ngo(ngo_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = NGORepository(db)
    ngo = await repo.get_or_raise(ngo_id)
    return ApiResponse.ok(data=NGOResponse.model_validate(ngo))


@router.put(
    "/{ngo_id}",
    response_model=ApiResponse[NGOResponse],
    summary="Update NGO profile",
)
async def update_ngo(
    ngo_id: UUID,
    data: NGOUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NGORepository(db)
    ngo = await repo.get_or_raise(ngo_id)
    if ngo.manager_id != current_user.id and current_user.role not in (
        UserRole.ADMIN, UserRole.SUPER_ADMIN
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")

    updated = await repo.update(ngo_id, data.model_dump(exclude_none=True))
    return ApiResponse.ok(data=NGOResponse.model_validate(updated))


@router.patch(
    "/{ngo_id}/capacity",
    response_model=MessageResponse,
    summary="Update NGO current capacity",
)
async def update_capacity(
    ngo_id: UUID,
    request: NGOCapacityUpdate,
    current_user: User = Depends(get_ngo_user),
    db: AsyncSession = Depends(get_db),
):
    repo = NGORepository(db)
    ngo = await repo.get_or_raise(ngo_id)
    if ngo.manager_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")
    await repo.update_capacity(ngo_id, request.current_capacity)
    return MessageResponse(message=f"Capacity updated to {request.current_capacity}")


@router.patch(
    "/{ngo_id}/verify",
    response_model=ApiResponse[NGOResponse],
    summary="Verify NGO (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def verify_ngo(
    ngo_id: UUID,
    approved: bool = True,
    rejection_reason: Optional[str] = None,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.ngo import NGOStatus
    from datetime import datetime, timezone
    repo = NGORepository(db)
    update_data = {
        "is_verified": approved,
        "status": NGOStatus.ACTIVE if approved else NGOStatus.SUSPENDED,
        "verified_by": current_user.id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    if not approved and rejection_reason:
        update_data["rejection_reason"] = rejection_reason
    updated = await repo.update(ngo_id, update_data)
    return ApiResponse.ok(
        data=NGOResponse.model_validate(updated),
        message="NGO verified" if approved else "NGO rejected",
    )
