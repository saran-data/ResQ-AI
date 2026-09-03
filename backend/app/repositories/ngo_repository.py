"""
ResQAI - NGO Repository
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ngo import NGO, NGOStatus, NGOType
from .base import BaseRepository


class NGORepository(BaseRepository[NGO]):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(NGO, db)

    async def get_by_manager(self, manager_id: UUID) -> Optional[NGO]:
        result = await self._db.execute(
            select(NGO).where(
                NGO.manager_id == manager_id,
                NGO.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[NGO]:
        result = await self._db.execute(
            select(NGO).where(NGO.slug == slug, NGO.is_deleted == False)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def get_available_ngos(
        self,
        city: Optional[str] = None,
        food_category: Optional[str] = None,
    ) -> List[NGO]:
        """Fetch verified, active NGOs with available capacity."""
        query = select(NGO).where(
            NGO.status == NGOStatus.ACTIVE,
            NGO.is_verified == True,  # noqa: E712
            NGO.is_deleted == False,  # noqa: E712
            NGO.current_capacity > 0,
        )
        if city:
            query = query.where(NGO.city.ilike(f"%{city}%"))

        result = await self._db.execute(query)
        ngos = list(result.scalars().all())

        # Filter by food preferences if category provided
        if food_category and ngos:
            ngos = [
                n for n in ngos
                if not n.food_preferences or food_category in n.food_preferences
            ]
        return ngos

    async def get_nearby_ngos(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 30.0,
        min_capacity: int = 1,
    ) -> List[NGO]:
        """Fetch NGOs within approximate radius with minimum capacity."""
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * abs(latitude / 90.0 + 0.01))

        result = await self._db.execute(
            select(NGO).where(
                and_(
                    NGO.latitude.between(latitude - lat_delta, latitude + lat_delta),
                    NGO.longitude.between(longitude - lng_delta, longitude + lng_delta),
                    NGO.status == NGOStatus.ACTIVE,
                    NGO.is_verified == True,  # noqa: E712
                    NGO.is_deleted == False,  # noqa: E712
                    NGO.current_capacity >= min_capacity,
                )
            )
        )
        return list(result.scalars().all())

    async def update_capacity(self, ngo_id: UUID, capacity: int) -> None:
        from sqlalchemy import update
        await self._db.execute(
            update(NGO).where(NGO.id == ngo_id).values(current_capacity=capacity)
        )

    async def update_impact_metrics(
        self, ngo_id: UUID, meals_delta: int, weight_delta: float
    ) -> None:
        from sqlalchemy import update
        await self._db.execute(
            update(NGO)
            .where(NGO.id == ngo_id)
            .values(
                total_received=NGO.total_received + 1,
                total_meals_distributed=NGO.total_meals_distributed + meals_delta,
                total_weight_received_kg=NGO.total_weight_received_kg + weight_delta,
            )
        )
