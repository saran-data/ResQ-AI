"""ResQAI - Deliveries API Endpoints"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse, PaginatedResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("", summary="List deliveries")
async def list_deliveries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.delivery import Delivery
    repo = BaseRepository(Delivery, db)
    deliveries, total = await repo.get_all(skip=(page - 1) * page_size, limit=page_size)
    return PaginatedResponse.ok(
        data=[d.to_dict() for d in deliveries], page=page, page_size=page_size, total=total
    )

@router.get("/{delivery_id}", summary="Get delivery by ID")
async def get_delivery(
    delivery_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.delivery import Delivery
    repo = BaseRepository(Delivery, db)
    delivery = await repo.get_or_raise(delivery_id)
    return ApiResponse.ok(data=delivery.to_dict())

@router.patch("/{delivery_id}/location", summary="Update delivery GPS")
async def update_delivery_location(
    delivery_id: UUID,
    latitude: float,
    longitude: float,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.delivery import Delivery
    from datetime import datetime, timezone
    repo = BaseRepository(Delivery, db)
    await repo.update(delivery_id, {
        "current_latitude": latitude,
        "current_longitude": longitude,
        "last_location_update": datetime.now(timezone.utc).isoformat(),
    })
    return ApiResponse.ok(data={"latitude": latitude, "longitude": longitude})
