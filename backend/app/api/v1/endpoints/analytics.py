"""ResQAI - Analytics API Endpoints"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse
from app.services.rbac_service import get_current_user, get_admin_user
from app.models.user import User

router = APIRouter()

@router.get("/dashboard", summary="Get dashboard KPIs")
async def get_dashboard_kpis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns KPIs for the current user's dashboard."""
    from sqlalchemy import func, select
    from app.models.donation import Donation, DonationStatus
    from app.models.restaurant import Restaurant
    from app.models.ngo import NGO

    # Aggregate real-time KPIs
    total_donations = (await db.execute(select(func.count(Donation.id)))).scalar_one()
    total_meals = (await db.execute(select(func.sum(Donation.total_servings)))).scalar_one() or 0
    confirmed_count = (await db.execute(
        select(func.count(Donation.id)).where(Donation.status == DonationStatus.CONFIRMED)
    )).scalar_one()

    return ApiResponse.ok(data={
        "total_donations": total_donations,
        "total_meals_saved": total_meals,
        "confirmed_deliveries": confirmed_count,
        "success_rate": round((confirmed_count / max(total_donations, 1)) * 100, 1),
        "carbon_saved_kg": round(total_meals * 0.5, 2),  # ~0.5kg CO2 per meal saved
    })

@router.get("/snapshots", summary="Get historical analytics snapshots")
async def get_snapshots(
    period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
    limit: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.repositories.base import BaseRepository
    from app.models.analytics import AnalyticsSnapshot, SnapshotType
    repo = BaseRepository(AnalyticsSnapshot, db)
    snapshots, _ = await repo.get_all(
        limit=limit,
        filters={"snapshot_type": SnapshotType(period)},
        order_by="snapshot_date",
        order_desc=True,
    )
    return ApiResponse.ok(data=[s.to_dict() for s in snapshots])

@router.get("/leaderboard", summary="Platform-wide leaderboard")
async def get_leaderboard(
    entity: str = Query(default="restaurant", pattern="^(restaurant|ngo|volunteer)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.restaurant_repository import RestaurantRepository
    from app.repositories.ngo_repository import NGORepository
    if entity == "restaurant":
        repo = RestaurantRepository(db)
        items = await repo.get_leaderboard(limit)
        return ApiResponse.ok(data=[{"id": str(r.id), "name": r.name, "score": r.sustainability_score, "meals": r.total_meals_saved} for r in items])
    elif entity == "ngo":
        repo = NGORepository(db)
        items, _ = await repo.get_all(limit=limit, order_by="total_received")
        return ApiResponse.ok(data=[{"id": str(n.id), "name": n.name, "received": n.total_received} for n in items])
    return ApiResponse.ok(data=[])
