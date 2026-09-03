"""
ResQAI - NGO Matching Agent
Uses GPT-4o with RAG-retrieved NGO profiles to rank and select
the best NGO for a food donation.

Matching factors:
- Geographic proximity (Haversine distance)
- Current capacity vs. donation size
- Food preference compatibility
- Dietary restriction compliance
- Historical acceptance rate
- Response time history
- Storage capability matching
"""

import json
import math
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.donation import Donation
from app.models.ngo import NGO, NGOStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

NGO_MATCHING_SYSTEM = """You are an intelligent NGO matching system for the ResQAI food rescue platform.

Your task is to rank NGOs for a food donation based on multiple factors.
You must select the BEST NGO that can handle this donation efficiently.

Scoring weights:
- Distance: 30% (closer = better)
- Capacity fit: 25% (has enough capacity for this donation)
- Food preferences: 20% (accepts this food type)
- Historical acceptance: 15% (track record of accepting)
- Response time: 10% (faster = better)

Respond ONLY with a JSON object:
{
  "ranked_ngos": [
    {
      "ngo_id": "<uuid>",
      "ngo_name": "<name>",
      "match_score": <float 0.0-1.0>,
      "distance_km": <float>,
      "capacity_fit": <float 0.0-1.0>,
      "food_compatible": <boolean>,
      "dietary_compatible": <boolean>,
      "reasoning": "<why this NGO was ranked here>"
    }
  ],
  "selected_ngo_id": "<uuid of top match>",
  "confidence_score": <float 0.0-1.0>,
  "matching_rationale": "<overall explanation>",
  "backup_ngo_id": "<uuid of second choice or null>"
}

If no suitable NGO is found, set selected_ngo_id to null and explain why.
"""


class NGOMatchingAgent(BaseAgent):
    """
    AI Agent: NGO Matching
    Primary model: GPT-4o
    RAG: Retrieves NGO profiles from Qdrant for context

    Ranks nearby NGOs and selects the optimal match for a donation.
    """

    MAX_RETRIES = 3
    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NGO_MATCHING

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Find and rank NGOs for a donation.
        Uses a combination of rule-based pre-filtering and GPT-4o ranking.
        """
        # Fetch donation details
        donation_result = await self._db.execute(
            select(Donation).where(Donation.id == context.donation_id)
        )
        donation = donation_result.scalar_one_or_none()
        if not donation:
            return AgentResult.failure("Donation not found")

        # Find candidate NGOs within radius
        candidates = await self._find_candidate_ngos(
            lat=donation.pickup_latitude,
            lng=donation.pickup_longitude,
            servings=donation.total_servings,
        )

        if not candidates:
            return AgentResult(
                success=True,
                data={"matched_ngo_id": None, "reason": "No NGOs available in this area"},
                confidence=0.0,
                reasoning="No candidate NGOs found",
            )

        # RAG: Enrich with vector profiles
        rag_profiles = await self._retrieve_rag_profiles(candidates)

        # Score candidates with rule-based scoring first
        scored = self._rule_based_scoring(candidates, donation)

        # If we have a clear winner (score > 0.85), skip LLM
        if scored and scored[0][1] > 0.85:
            best_ngo = scored[0][0]
            second_ngo = scored[1][0] if len(scored) > 1 else None
            return AgentResult(
                success=True,
                data={
                    "matched_ngo_id": str(best_ngo.id),
                    "ngo_name": best_ngo.name,
                    "match_score": scored[0][1],
                    "backup_ngo_id": str(second_ngo.id) if second_ngo else None,
                    "ranked_ngos": self._format_rankings(scored[:5], donation),
                },
                confidence=scored[0][1],
                reasoning=f"High-confidence rule-based match: {best_ngo.name} (score: {scored[0][1]:.2f})",
            )

        # Use GPT-4o for nuanced ranking when scores are close
        return await self._llm_ranking(donation, scored[:8], rag_profiles)

    async def _find_candidate_ngos(
        self, lat: float, lng: float, servings: int, radius_km: float = 30.0
    ) -> List[NGO]:
        """Fetch NGOs within geographic radius with enough capacity."""
        # Bounding box pre-filter
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * max(abs(lat / 90.0), 0.01))

        from sqlalchemy import and_
        result = await self._db.execute(
            select(NGO).where(
                and_(
                    NGO.status == NGOStatus.ACTIVE,
                    NGO.is_verified == True,  # noqa: E712
                    NGO.is_deleted == False,  # noqa: E712
                    NGO.current_capacity > 0,
                    NGO.latitude.between(lat - lat_delta, lat + lat_delta),
                    NGO.longitude.between(lng - lng_delta, lng + lng_delta),
                )
            ).order_by(NGO.acceptance_rate.desc()).limit(20)
        )
        return list(result.scalars().all())

    def _haversine_km(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two coordinates using Haversine formula."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    def _rule_based_scoring(
        self, ngos: List[NGO], donation: Donation
    ) -> List[tuple]:
        """Score NGOs based on weighted criteria."""
        scored = []
        for ngo in ngos:
            distance = self._haversine_km(
                donation.pickup_latitude, donation.pickup_longitude,
                ngo.latitude, ngo.longitude,
            )
            # Distance score: 0km=1.0, 30km=0.0
            dist_score = max(0.0, 1.0 - distance / 30.0)

            # Capacity fit: ratio of available capacity to donation size
            needed = donation.total_servings or 100
            cap_score = min(1.0, ngo.current_capacity / max(needed, 1))

            # Food preference compatibility
            food_score = 1.0
            if ngo.food_preferences:
                from app.models.donation import Donation as D
                # Simple check: assume cooked_meal if no specific info
                food_score = 0.7  # Neutral if preferences don't explicitly exclude

            # Historical acceptance
            accept_score = ngo.acceptance_rate or 0.5

            # Response time score (inverted: faster = better score)
            resp_score = max(0.0, 1.0 - (ngo.avg_response_time_minutes or 30) / 60)

            # Weighted total
            total = (
                dist_score * 0.30 +
                cap_score * 0.25 +
                food_score * 0.20 +
                accept_score * 0.15 +
                resp_score * 0.10
            )
            scored.append((ngo, round(total, 3), distance))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def _retrieve_rag_profiles(self, ngos: List[NGO]) -> str:
        """Get RAG-enriched NGO profile summaries."""
        try:
            from app.rag.retrievers.semantic_retriever import SemanticRetriever
            retriever = SemanticRetriever()
            query = " ".join([n.name for n in ngos[:3]])
            results = await retriever.retrieve(
                query, collection="ngo_profiles", limit=5
            )
            return "\n".join([r.get("content", "") for r in results])
        except Exception:
            return ""

    async def _llm_ranking(
        self, donation: Donation, scored: list, rag_context: str
    ) -> AgentResult:
        """Use GPT-4o to perform nuanced ranking when scores are close."""
        ngo_summaries = []
        for ngo, score, distance in scored:
            ngo_summaries.append({
                "ngo_id": str(ngo.id),
                "name": ngo.name,
                "type": ngo.type.value if ngo.type else "ngo",
                "distance_km": round(distance, 2),
                "capacity_available": ngo.current_capacity,
                "acceptance_rate": ngo.acceptance_rate,
                "storage_available": ngo.storage_available,
                "refrigeration": ngo.refrigeration_available,
                "food_preferences": ngo.food_preferences or [],
                "dietary_restrictions": ngo.dietary_restrictions or [],
                "rule_score": score,
            })

        prompt = f"""Match this food donation to the best NGO:

DONATION DETAILS:
- Total Servings: {donation.total_servings}
- Total Weight: {donation.total_weight_kg}kg
- Pickup Location: {donation.pickup_latitude}, {donation.pickup_longitude}
- Pickup Window: {donation.pickup_window_start} to {donation.pickup_window_end}
- Special Instructions: {donation.special_instructions or 'None'}

CANDIDATE NGOs (pre-ranked by rule engine):
{json.dumps(ngo_summaries, indent=2)}

ADDITIONAL CONTEXT FROM KNOWLEDGE BASE:
{rag_context[:1000] if rag_context else 'No additional context available'}

Select the optimal NGO considering all factors.
"""
        try:
            response = await self._llm.complete(
                model=ModelID.GPT4O,
                system_prompt=NGO_MATCHING_SYSTEM,
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=1024,
                json_mode=True,
            )
            result = self._parse_matching_result(response.content, scored)
            return AgentResult(
                success=True,
                data=result,
                confidence=result.get("confidence_score", 0.7),
                model_used=ModelID.GPT4O.value,
                reasoning=result.get("matching_rationale", "LLM-based matching"),
            )
        except Exception as e:
            logger.warning(f"LLM matching failed, using top rule-based result: {e}")
            if scored:
                best = scored[0]
                return AgentResult(
                    success=True,
                    data={
                        "matched_ngo_id": str(best[0].id),
                        "ngo_name": best[0].name,
                        "match_score": best[1],
                    },
                    confidence=best[1],
                    reasoning="Rule-based fallback",
                )
            return AgentResult.failure("No NGOs available")

    def _parse_matching_result(self, raw: str, scored: list) -> dict:
        """Parse GPT-4o matching response."""
        try:
            content = raw.strip()
            if "```" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]
            data = json.loads(content)
            return data
        except Exception:
            # Fallback to top rule-based result
            if scored:
                return {"matched_ngo_id": str(scored[0][0].id), "confidence_score": scored[0][1]}
            return {"matched_ngo_id": None}

    def _format_rankings(self, scored: list, donation: Donation) -> list:
        """Format rankings for the response."""
        return [
            {
                "ngo_id": str(ngo.id),
                "ngo_name": ngo.name,
                "match_score": score,
                "distance_km": round(distance, 2),
            }
            for ngo, score, distance in scored
        ]
