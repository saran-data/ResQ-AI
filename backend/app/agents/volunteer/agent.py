"""
ResQAI - Volunteer Agent
Uses Llama 3 (local, privacy-preserving) to assign the optimal volunteer
for a pickup/delivery based on proximity, availability, and performance.
"""

import math
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.donation import Donation
from app.models.volunteer import Volunteer, VolunteerStatus
from app.models.delivery import Delivery, DeliveryStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class VolunteerAgent(BaseAgent):
    """
    AI Agent: Volunteer Assignment
    Primary model: Llama 3 (local Ollama)
    Fallback: Rule-based scoring

    Assigns the best available volunteer for a donation pickup.
    Uses Llama locally to preserve volunteer data privacy.
    """

    MAX_RETRIES = 2

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.VOLUNTEER

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """Find and assign the best volunteer for a donation."""
        donation_result = await self._db.execute(
            select(Donation).where(Donation.id == context.donation_id)
        )
        donation = donation_result.scalar_one_or_none()
        if not donation:
            return AgentResult.failure("Donation not found")

        # Find available volunteers near the pickup location
        candidates = await self._find_available_volunteers(
            lat=donation.pickup_latitude,
            lng=donation.pickup_longitude,
            radius_km=20.0,
        )

        if not candidates:
            logger.warning(f"No volunteers available near donation {context.donation_id}")
            return AgentResult(
                success=True,
                data={"assigned": False, "reason": "No volunteers available nearby"},
                confidence=0.0,
                reasoning="No available volunteers within 20km",
            )

        # Score volunteers
        scored = self._score_volunteers(candidates, donation)
        best_volunteer, score, distance = scored[0]

        # Create delivery record
        if donation.matched_ngo_id:
            delivery = await self._create_delivery(donation, best_volunteer)
            
            # Mark volunteer as on delivery
            from sqlalchemy import update
            await self._db.execute(
                update(Volunteer)
                .where(Volunteer.id == best_volunteer.id)
                .values(
                    current_deliveries=Volunteer.current_deliveries + 1,
                    status=VolunteerStatus.ON_DELIVERY,
                )
            )

            # Update donation volunteer assignment
            await self._db.execute(
                update(Donation)
                .where(Donation.id == donation.id)
                .values(
                    volunteer_id=best_volunteer.id,
                    scheduled_pickup_at=donation.pickup_window_start,
                )
            )

            return AgentResult(
                success=True,
                data={
                    "assigned": True,
                    "volunteer_id": str(best_volunteer.id),
                    "volunteer_name": best_volunteer.user.name if hasattr(best_volunteer, 'user') and best_volunteer.user else "Volunteer",
                    "distance_km": round(distance, 2),
                    "match_score": score,
                    "delivery_id": str(delivery.id),
                    "ranked_volunteers": [
                        {"id": str(v.id), "score": s, "distance_km": round(d, 2)}
                        for v, s, d in scored[:3]
                    ],
                },
                confidence=score,
                reasoning=f"Assigned volunteer {best_volunteer.id} (score: {score:.2f}, distance: {distance:.1f}km)",
            )

        return AgentResult.failure("No NGO matched — cannot create delivery")

    async def _find_available_volunteers(
        self, lat: float, lng: float, radius_km: float
    ) -> list:
        """Find available volunteers within radius."""
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * max(abs(lat / 90.0), 0.01))

        result = await self._db.execute(
            select(Volunteer).where(
                and_(
                    Volunteer.status == VolunteerStatus.ACTIVE,
                    Volunteer.is_available == True,  # noqa: E712
                    Volunteer.is_deleted == False,  # noqa: E712
                    Volunteer.current_deliveries < Volunteer.max_concurrent_deliveries,
                    Volunteer.latitude.isnot(None),
                    Volunteer.longitude.isnot(None),
                    Volunteer.latitude.between(lat - lat_delta, lat + lat_delta),
                    Volunteer.longitude.between(lng - lng_delta, lng + lng_delta),
                )
            ).limit(20)
        )
        return list(result.scalars().all())

    def _score_volunteers(self, volunteers: list, donation: Donation) -> list:
        """Score and rank volunteers for this donation."""
        scored = []
        for vol in volunteers:
            if vol.latitude is None or vol.longitude is None:
                continue

            distance = self._haversine_km(
                donation.pickup_latitude, donation.pickup_longitude,
                vol.latitude, vol.longitude,
            )
            # Distance score: 0km=1.0, 20km=0.0
            dist_score = max(0.0, 1.0 - distance / 20.0)

            # Rating score (normalized 0-5 → 0-1)
            rating_score = (vol.rating or 3.5) / 5.0

            # Success rate
            success_rate = (
                vol.successful_deliveries / max(vol.total_deliveries, 1)
                if vol.total_deliveries > 0 else 0.5
            )

            # On-time rate
            ontime_score = vol.on_time_rate or 0.7

            # Load: prefer volunteers with fewer current deliveries
            load_score = 1.0 - (vol.current_deliveries / max(vol.max_concurrent_deliveries, 1))

            total = (
                dist_score * 0.40 +
                rating_score * 0.20 +
                success_rate * 0.20 +
                ontime_score * 0.10 +
                load_score * 0.10
            )
            scored.append((vol, round(total, 3), distance))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _haversine_km(self, lat1, lng1, lat2, lng2) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    async def _create_delivery(self, donation: Donation, volunteer: Volunteer) -> Delivery:
        """Create the delivery record linking donation, volunteer, and NGO."""
        delivery = Delivery(
            donation_id=donation.id,
            volunteer_id=volunteer.id,
            ngo_id=donation.matched_ngo_id,
            status=DeliveryStatus.ASSIGNED,
            estimated_pickup_at=donation.pickup_window_start,
        )
        self._db.add(delivery)
        await self._db.flush()
        return delivery
