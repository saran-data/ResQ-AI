"""
ResQAI - Analytics Agent
Uses GPT-4o to generate KPI narratives, trend analysis, and actionable insights
from aggregated platform data.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.donation import Donation, DonationStatus
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.models.volunteer import Volunteer
from app.models.analytics import AnalyticsSnapshot, SnapshotType
from app.core.logging import get_logger

logger = get_logger(__name__)

ANALYTICS_SYSTEM = """You are a food rescue analytics expert for the ResQAI platform.

Analyze platform data and generate concise, actionable insights.

Respond with JSON:
{
  "headline": "<one powerful sentence summarizing the period>",
  "key_achievements": ["3-5 notable achievements"],
  "trends": [
    {"metric": "<name>", "direction": "up/down/stable", "change_percent": <float>, "insight": "<why>"}
  ],
  "alerts": ["urgent issues requiring attention"],
  "recommendations": ["3-5 specific actions to improve performance"],
  "carbon_equivalent": "<human-readable carbon saving comparison>",
  "meals_equivalent": "<human-readable meals saved context>",
  "confidence_score": <float 0-1>
}
"""


class AnalyticsAgent(BaseAgent):
    """
    AI Agent: Analytics
    Primary model: GPT-4o

    Generates narrative insights, trend analysis, and recommendations
    from platform KPI data. Runs on schedule and on-demand.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ANALYTICS

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate analytics insights for the specified period."""
        period_days: int = kwargs.get("period_days", 7)
        entity_type: Optional[str] = kwargs.get("entity_type")  # restaurant/ngo/system
        entity_id: Optional[str] = kwargs.get("entity_id")

        # Gather raw metrics
        metrics = await self._gather_metrics(period_days, entity_type, entity_id)

        # Generate insights using GPT-4o
        insights = await self._generate_insights(metrics, period_days)

        # Compute carbon and impact equivalents
        insights["carbon_saved_kg"] = metrics.get("carbon_saved_kg", 0)
        insights["meals_saved"] = metrics.get("total_meals", 0)
        insights["donations_processed"] = metrics.get("total_donations", 0)

        return AgentResult(
            success=True,
            data=insights,
            confidence=insights.get("confidence_score", 0.8),
            model_used=ModelID.GPT4O.value,
            reasoning=f"Analytics generated for {period_days}-day period",
        )

    async def _gather_metrics(
        self, days: int, entity_type: Optional[str], entity_id: Optional[str]
    ) -> dict:
        """Aggregate raw KPIs from the database."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        query = select(
            func.count(Donation.id).label("total"),
            func.sum(Donation.total_servings).label("servings"),
            func.sum(Donation.total_weight_kg).label("weight"),
            func.count(Donation.id).filter(
                Donation.status == DonationStatus.CONFIRMED
            ).label("confirmed"),
        ).where(Donation.created_at >= since)

        if entity_type == "restaurant" and entity_id:
            query = query.where(Donation.restaurant_id == entity_id)
        elif entity_type == "ngo" and entity_id:
            query = query.where(Donation.matched_ngo_id == entity_id)

        result = await self._db.execute(query)
        row = result.first()

        total = row.total or 0
        confirmed = row.confirmed or 0
        servings = int(row.servings or 0)
        weight = float(row.weight or 0)

        active_restaurants = (await self._db.execute(
            select(func.count(Restaurant.id)).where(Restaurant.is_deleted == False)  # noqa
        )).scalar_one()

        active_ngos = (await self._db.execute(
            select(func.count(NGO.id)).where(NGO.is_deleted == False)  # noqa
        )).scalar_one()

        active_volunteers = (await self._db.execute(
            select(func.count(Volunteer.id)).where(Volunteer.is_deleted == False)  # noqa
        )).scalar_one()

        # Environmental impact calculations
        # ~0.5 kg CO2 saved per meal (vs food going to landfill + methane production)
        carbon_saved = round(servings * 0.5, 2)
        # ~1 liter water saved per 100g food waste prevented
        water_saved = round(weight * 10, 2)

        return {
            "total_donations": total,
            "confirmed_donations": confirmed,
            "total_meals": servings,
            "total_weight_kg": round(weight, 2),
            "success_rate": round((confirmed / max(total, 1)) * 100, 1),
            "carbon_saved_kg": carbon_saved,
            "water_saved_liters": water_saved,
            "active_restaurants": active_restaurants,
            "active_ngos": active_ngos,
            "active_volunteers": active_volunteers,
            "period_days": days,
        }

    async def _generate_insights(self, metrics: dict, period_days: int) -> dict:
        """Use GPT-4o to narrate the metrics and generate recommendations."""
        prompt = f"""Analyze these {period_days}-day platform metrics for ResQAI food rescue platform:

{json.dumps(metrics, indent=2)}

Generate actionable insights, highlight achievements, identify trends, and provide recommendations.
Context: This is a food rescue platform connecting restaurants with NGOs in India.
The platform uses AI agents to automate the rescue process."""

        try:
            response = await self._llm.complete(
                model=ModelID.GPT4O,
                system_prompt=ANALYTICS_SYSTEM,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=1024,
                json_mode=True,
            )
            data = json.loads(response.content)
            data["raw_metrics"] = metrics
            return data
        except Exception as e:
            logger.warning(f"Analytics LLM failed: {e}")
            return self._rule_based_insights(metrics)

    def _rule_based_insights(self, metrics: dict) -> dict:
        """Fallback deterministic insights."""
        success_rate = metrics.get("success_rate", 0)
        meals = metrics.get("total_meals", 0)
        carbon = metrics.get("carbon_saved_kg", 0)

        achievements = [f"Saved {meals:,} meals from going to waste"]
        if carbon > 0:
            achievements.append(f"Prevented {carbon:.1f}kg of CO₂ emissions")
        if success_rate > 80:
            achievements.append(f"Achieved {success_rate:.1f}% delivery success rate")

        return {
            "headline": f"{meals:,} meals rescued in {metrics.get('period_days', 7)} days",
            "key_achievements": achievements,
            "trends": [],
            "alerts": [] if success_rate > 60 else [f"Success rate dropped to {success_rate:.1f}%"],
            "recommendations": [
                "Onboard more volunteers in high-demand areas",
                "Increase NGO capacity notifications",
                "Schedule reminders for restaurant staff",
            ],
            "carbon_equivalent": f"Equivalent to planting {int(carbon/21)} trees",
            "meals_equivalent": f"{meals:,} people fed for one day",
            "confidence_score": 0.7,
            "raw_metrics": metrics,
        }
