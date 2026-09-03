"""ResQAI - Volunteers API Endpoints"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("", summary="List volunteers")
async def list_volunteers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.volunteer import Volunteer
    repo = BaseRepository(Volunteer, db)
    volunteers, total = await repo.get_all(skip=(page - 1) * page_size, limit=page_size)
    return PaginatedResponse.ok(
        data=[v.to_dict() for v in volunteers], page=page, page_size=page_size, total=total
    )

@router.get("/me", summary="Get my volunteer profile")
async def get_my_volunteer(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.volunteer import Volunteer
    repo = BaseRepository(Volunteer, db)
    vol = await repo.get_by_field("user_id", current_user.id)
    if not vol:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Volunteer profile not found")
    return ApiResponse.ok(data=vol.to_dict())

@router.patch("/me/availability", summary="Toggle availability")
async def toggle_availability(
    is_available: bool,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.volunteer import Volunteer
    repo = BaseRepository(Volunteer, db)
    vol = await repo.get_by_field("user_id", current_user.id)
    if not vol:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Volunteer profile not found")
    await repo.update(vol.id, {"is_available": is_available})
    return MessageResponse(message=f"Availability set to {is_available}")

@router.patch("/me/location", summary="Update volunteer GPS location")
async def update_location(
    latitude: float,
    longitude: float,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.volunteer import Volunteer
    from datetime import datetime, timezone
    repo = BaseRepository(Volunteer, db)
    vol = await repo.get_by_field("user_id", current_user.id)
    if vol:
        await repo.update(vol.id, {
            "latitude": latitude,
            "longitude": longitude,
            "last_location_update": datetime.now(timezone.utc).isoformat(),
        })
    return MessageResponse(message="Location updated")
