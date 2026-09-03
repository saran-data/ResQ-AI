"""ResQAI - Admin API Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, check_database_health
from app.schemas.base import ApiResponse
from app.services.rbac_service import get_admin_user
from app.models.user import User

router = APIRouter()

@router.get("/system/health", summary="System component health")
async def system_health(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    db_health = await check_database_health()
    from app.core.redis_client import get_cache_manager
    redis_health = await get_cache_manager().health_check()
    return ApiResponse.ok(data={"database": db_health, "redis": redis_health})

@router.get("/stats/overview", summary="Platform overview statistics")
async def get_overview_stats(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select
    from app.models.user import User as UserModel
    from app.models.restaurant import Restaurant
    from app.models.ngo import NGO
    from app.models.donation import Donation
    from app.models.volunteer import Volunteer

    total_users = (await db.execute(select(func.count(UserModel.id)))).scalar_one()
    total_restaurants = (await db.execute(select(func.count(Restaurant.id)))).scalar_one()
    total_ngos = (await db.execute(select(func.count(NGO.id)))).scalar_one()
    total_donations = (await db.execute(select(func.count(Donation.id)))).scalar_one()
    total_volunteers = (await db.execute(select(func.count(Volunteer.id)))).scalar_one()

    return ApiResponse.ok(data={
        "total_users": total_users,
        "total_restaurants": total_restaurants,
        "total_ngos": total_ngos,
        "total_donations": total_donations,
        "total_volunteers": total_volunteers,
    })

@router.get("/fraud/flagged", summary="Get flagged donations")
async def get_flagged_donations(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.donation import Donation
    result = await db.execute(
        select(Donation).where(Donation.is_flagged == True).limit(50)  # noqa
    )
    flagged = result.scalars().all()
    return ApiResponse.ok(data=[{"id": str(d.id), "fraud_score": d.fraud_score, "restaurant_id": str(d.restaurant_id)} for d in flagged])
