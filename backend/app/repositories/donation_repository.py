"""
ResQAI - Donation Repository
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donation import Donation, DonationStatus
from .base import BaseRepository


class DonationRepository(BaseRepository[Donation]):

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Donation, db)

    async def get_with_items(self, donation_id: UUID) -> Optional[Donation]:
        """Fetch donation with all food items eagerly loaded."""
        result = await self._db.execute(
            select(Donation)
            .where(Donation.id == donation_id)
            .options(
                selectinload(Donation.food_items),
                selectinload(Donation.ai_decisions),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_restaurant(
        self,
        restaurant_id: UUID,
        status: Optional[DonationStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Donation], int]:
        """Paginated donations for a specific restaurant."""
        query = select(Donation).where(Donation.restaurant_id == restaurant_id)
        if status:
            query = query.where(Donation.status == status)

        from sqlalchemy import func
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self._db.execute(count_q)).scalar_one()

        query = query.order_by(desc(Donation.created_at)).offset(skip).limit(limit)
        result = await self._db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_ngo(
        self,
        ngo_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Donation], int]:
        """Paginated donations matched to a specific NGO."""
        query = select(Donation).where(Donation.matched_ngo_id == ngo_id)

        from sqlalchemy import func
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self._db.execute(count_q)).scalar_one()

        query = query.order_by(desc(Donation.created_at)).offset(skip).limit(limit)
        result = await self._db.execute(query)
        return list(result.scalars().all()), total

    async def get_pending_analysis(self) -> List[Donation]:
        """Fetch donations awaiting AI analysis (for background processing)."""
        result = await self._db.execute(
            select(Donation)
            .where(Donation.status == DonationStatus.PENDING_ANALYSIS)
            .options(selectinload(Donation.food_items))
            .order_by(Donation.created_at.asc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_pending_matching(self) -> List[Donation]:
        """Fetch safety-cleared donations awaiting NGO matching."""
        result = await self._db.execute(
            select(Donation)
            .where(Donation.status == DonationStatus.MATCHING)
            .options(selectinload(Donation.food_items))
            .order_by(Donation.created_at.asc())
            .limit(20)
        )
        return list(result.scalars().all())

    async def transition_status(
        self,
        donation_id: UUID,
        new_status: DonationStatus,
        actor: str = "system",
    ) -> Optional[Donation]:
        """
        Transition donation to a new status and append to status_history.
        This is the canonical way to change donation status throughout the system.
        """
        from datetime import datetime, timezone
        from sqlalchemy import update

        donation = await self.get(donation_id)
        if not donation:
            return None

        # Build history entry
        history_entry = {
            "status": new_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "previous_status": donation.status.value if donation.status else None,
        }

        current_history = donation.status_history or []
        new_history = current_history + [history_entry]

        await self._db.execute(
            update(Donation)
            .where(Donation.id == donation_id)
            .values(status=new_status, status_history=new_history)
        )
        await self._db.flush()
        return await self.get(donation_id)

    async def get_active_for_tracking(self) -> List[Donation]:
        """Fetch all in-flight donations (for real-time tracking)."""
        active_statuses = [
            DonationStatus.PICKUP_SCHEDULED,
            DonationStatus.AWAITING_PICKUP,
            DonationStatus.PICKED_UP,
            DonationStatus.IN_TRANSIT,
        ]
        result = await self._db.execute(
            select(Donation).where(Donation.status.in_(active_statuses))
        )
        return list(result.scalars().all())
