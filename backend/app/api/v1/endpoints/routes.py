"""ResQAI - Routes API Endpoints"""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/{route_id}", summary="Get route details")
async def get_route(
    route_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.route import Route
    repo = BaseRepository(Route, db)
    route = await repo.get_or_raise(route_id)
    return ApiResponse.ok(data=route.to_dict())

@router.post("/optimize", summary="Request route optimization")
async def optimize_route(
    donation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Triggers the Route Optimization Agent for a matched donation."""
    try:
        from app.tasks.ai_tasks import route_optimization_task
        route_optimization_task.delay(str(donation_id))
    except Exception:
        pass
    return ApiResponse.ok(data={"queued": True, "donation_id": str(donation_id)})
