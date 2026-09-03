"""ResQAI - Analytics Celery Tasks"""
from celery import shared_task
from loguru import logger


@shared_task(name="app.tasks.analytics_tasks.compute_daily_snapshot")
def compute_daily_snapshot() -> None:
    import asyncio
    from datetime import datetime, date
    async def _run():
        from app.core.database import get_db_context
        from app.models.analytics import AnalyticsSnapshot, SnapshotType
        from app.models.donation import Donation, DonationStatus
        from app.models.restaurant import Restaurant, RestaurantStatus
        from app.models.ngo import NGO, NGOStatus
        from app.models.volunteer import Volunteer, VolunteerStatus
        from sqlalchemy import func, select
        async with get_db_context() as db:
            today = date.today().isoformat()
            total_donations = (await db.execute(select(func.count(Donation.id)))).scalar_one()
            total_meals = (await db.execute(select(func.sum(Donation.total_servings)))).scalar_one() or 0
            confirmed = (await db.execute(
                select(func.count(Donation.id)).where(Donation.status == DonationStatus.CONFIRMED)
            )).scalar_one()
            active_restaurants = (await db.execute(
                select(func.count(Restaurant.id)).where(Restaurant.status == RestaurantStatus.ACTIVE)
            )).scalar_one()
            active_ngos = (await db.execute(
                select(func.count(NGO.id)).where(NGO.status == NGOStatus.ACTIVE)
            )).scalar_one()
            active_volunteers = (await db.execute(
                select(func.count(Volunteer.id)).where(Volunteer.status == VolunteerStatus.ACTIVE)
            )).scalar_one()

            snapshot = AnalyticsSnapshot(
                snapshot_date=today,
                snapshot_type=SnapshotType.DAILY,
                total_donations=total_donations,
                total_meals_saved=total_meals,
                successful_deliveries=confirmed,
                carbon_saved_kg=round(total_meals * 0.5, 2),
                active_restaurants=active_restaurants,
                active_ngos=active_ngos,
                active_volunteers=active_volunteers,
                success_rate=round((confirmed / max(total_donations, 1)) * 100, 1),
            )
            db.add(snapshot)
            logger.info(f"Daily analytics snapshot computed for {today}")
    asyncio.run(_run())


@shared_task(name="app.tasks.analytics_tasks.update_restaurant_rankings")
def update_restaurant_rankings() -> None:
    import asyncio
    async def _run():
        from app.core.database import get_db_context
        from app.models.restaurant import Restaurant, RestaurantStatus
        from sqlalchemy import select, update
        async with get_db_context() as db:
            result = await db.execute(
                select(Restaurant)
                .where(Restaurant.status == RestaurantStatus.ACTIVE)
                .order_by(Restaurant.sustainability_score.desc())
            )
            restaurants = result.scalars().all()
            for rank, restaurant in enumerate(restaurants, start=1):
                await db.execute(
                    update(Restaurant).where(Restaurant.id == restaurant.id).values(impact_rank=rank)
                )
    asyncio.run(_run())
