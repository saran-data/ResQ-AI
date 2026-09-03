"""
ResQAI - Restaurant Repository
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant, RestaurantStatus
from .base import BaseRepository


class RestaurantRepository(BaseRepository[Restaurant]):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Restaurant, db)

    async def get_by_owner(self, owner_id: UUID) -> Optional[Restaurant]:
        result = await self._db.execute(
            select(Restaurant).where(
                Restaurant.owner_id == owner_id,
                Restaurant.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Restaurant]:
        result = await self._db.execute(
            select(Restaurant).where(
                Restaurant.slug == slug,
                Restaurant.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_verified_active(self, city: Optional[str] = None) -> List[Restaurant]:
        """Fetch all verified active restaurants, optionally filtered by city."""
        query = select(Restaurant).where(
            Restaurant.status == RestaurantStatus.ACTIVE,
            Restaurant.is_verified == True,  # noqa: E712
            Restaurant.is_deleted == False,  # noqa: E712
        )
        if city:
            query = query.where(Restaurant.city.ilike(f"%{city}%"))
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def get_nearby(
        self, latitude: float, longitude: float, radius_km: float = 20.0
    ) -> List[Restaurant]:
        """
        Fetch restaurants within approximate bounding box.
        For production, use PostGIS ST_DWithin for accurate geo queries.
        """
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * abs(latitude / 90.0 + 0.01))

        result = await self._db.execute(
            select(Restaurant).where(
                and_(
                    Restaurant.latitude.between(latitude - lat_delta, latitude + lat_delta),
                    Restaurant.longitude.between(longitude - lng_delta, longitude + lng_delta),
                    Restaurant.status == RestaurantStatus.ACTIVE,
                    Restaurant.is_deleted == False,  # noqa: E712
                )
            )
        )
        return list(result.scalars().all())

    async def update_impact_metrics(
        self,
        restaurant_id: UUID,
        meals_delta: int,
        weight_delta: float,
        carbon_delta: float,
    ) -> None:
        """Atomically increment impact counters (called after each successful delivery)."""
        from sqlalchemy import update
        await self._db.execute(
            update(Restaurant)
            .where(Restaurant.id == restaurant_id)
            .values(
                total_donations=Restaurant.total_donations + 1,
                total_meals_saved=Restaurant.total_meals_saved + meals_delta,
                total_weight_donated_kg=Restaurant.total_weight_donated_kg + weight_delta,
                carbon_saved_kg=Restaurant.carbon_saved_kg + carbon_delta,
            )
        )

    async def get_leaderboard(self, limit: int = 10) -> List[Restaurant]:
        """Top restaurants by sustainability score."""
        result = await self._db.execute(
            select(Restaurant)
            .where(
                Restaurant.status == RestaurantStatus.ACTIVE,
                Restaurant.is_deleted == False,  # noqa: E712
            )
            .order_by(Restaurant.sustainability_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
