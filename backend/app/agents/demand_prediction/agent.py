"""
ResQAI - Demand Prediction Agent
Uses GPT-4o to predict future food demand at NGOs based on:
- Historical donation and receipt patterns
- Seasonal events and festivals
- Weather conditions
- Day-of-week patterns
- Beneficiary population trends
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
from app.models.ngo import NGO
from app.models.donation import Donation, DonationStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

DEMAND_PREDICTION_SYSTEM = """You are an AI demand forecasting system for food rescue operations.

Analyze patterns to predict food demand at NGOs for the next 7 days.
Consider: seasonal events, festivals, weather, historical trends, day-of-week patterns.

Respond with JSON:
{
  "ngo_id": "<uuid>",
  "forecast_days": 7,
  "daily_predictions": [
    {
      "date": "YYYY-MM-DD",
      "expected_servings": <integer>,
      "confidence": <float 0-1>,
      "demand_level": "low/normal/high/critical",
      "factors": ["list of factors driving this prediction"]
    }
  ],
  "weekly_total": <integer>,
  "peak_day": "YYYY-MM-DD",
  "special_events": ["festival names or events in the forecast window"],
  "recommendations": ["proactive actions for the platform"],
  "confidence_score": <float 0-1>
}
"""


class DemandPredictionAgent(BaseAgent):
    """
    AI Agent: Demand Prediction
    Primary model: GPT-4o

    Forecasts food demand at NGOs for the next 7 days.
    Results are stored in NGO.demand_forecast for the NGO Matching Agent to use.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.DEMAND_PREDICTION

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """Predict demand for the NGO in context.metadata['ngo_id']."""
        ngo_id = context.metadata.get("ngo_id")
        if not ngo_id:
            return AgentResult.failure("ngo_id required in context.metadata")

        ngo_result = await self._db.execute(select(NGO).where(NGO.id == ngo_id))
        ngo = ngo_result.scalar_one_or_none()
        if not ngo:
            return AgentResult.failure(f"NGO {ngo_id} not found")

        # Gather historical data
        historical = await self._get_historical_data(ngo)
        weather_context = await self._get_weather_context(ngo.city or "")
        calendar_events = self._get_upcoming_events()

        prompt = f"""Predict food demand for this NGO over the next 7 days:

NGO Profile:
- Name: {ngo.name}
- Type: {ngo.type.value if ngo.type else 'ngo'}
- City: {ngo.city}
- Daily Capacity: {ngo.capacity_per_day} servings
- Beneficiaries: {ngo.beneficiaries_count}
- Food Preferences: {', '.join(ngo.food_preferences or [])}

Historical Data (last 30 days):
{json.dumps(historical, indent=2)}

Weather Forecast:
{weather_context}

Upcoming Events/Festivals:
{json.dumps(calendar_events, indent=2)}

Current Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} (IST)

Predict daily demand for the next 7 days."""

        try:
            response = await self._llm.complete(
                model=ModelID.GPT4O,
                system_prompt=DEMAND_PREDICTION_SYSTEM,
                user_prompt=prompt,
                temperature=0.2,
                max_tokens=1024,
                json_mode=True,
            )
            forecast = self._parse_forecast(response.content, ngo_id)

            # Save forecast to NGO record
            from sqlalchemy import update
            await self._db.execute(
                update(NGO)
                .where(NGO.id == ngo_id)
                .values(demand_forecast=forecast)
            )

            return AgentResult(
                success=True,
                data=forecast,
                confidence=forecast.get("confidence_score", 0.7),
                model_used=ModelID.GPT4O.value,
                reasoning=f"7-day demand forecast: {forecast.get('weekly_total', 0)} servings",
            )
        except Exception as e:
            logger.warning(f"Demand prediction LLM failed: {e}")
            return self._statistical_forecast(ngo, historical)

    async def _get_historical_data(self, ngo: NGO) -> list:
        """Get last 30 days of donation receipts for this NGO."""
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = await self._db.execute(
            select(
                func.date(Donation.delivered_at).label("date"),
                func.count(Donation.id).label("donations"),
                func.sum(Donation.total_servings).label("servings"),
            )
            .where(
                Donation.matched_ngo_id == ngo.id,
                Donation.status == DonationStatus.CONFIRMED,
                Donation.delivered_at >= thirty_days_ago,
            )
            .group_by(func.date(Donation.delivered_at))
            .order_by(func.date(Donation.delivered_at).desc())
            .limit(30)
        )
        return [
            {"date": str(row.date), "donations": row.donations, "servings": row.servings or 0}
            for row in result.all()
        ]

    async def _get_weather_context(self, city: str) -> str:
        """Fetch weather forecast for the NGO's city."""
        from app.config import settings
        if not settings.OPENWEATHER_API_KEY or settings.OPENWEATHER_API_KEY.startswith("your"):
            return "Weather data unavailable (API key not configured)"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as http:
                r = await http.get(
                    f"{settings.OPENWEATHER_BASE_URL}/forecast",
                    params={"q": f"{city},IN", "cnt": 5, "appid": settings.OPENWEATHER_API_KEY},
                )
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("list", [])[:3]
                    return "; ".join(
                        f"{i['dt_txt']}: {i['weather'][0]['description']}, {i['main']['temp']-273:.0f}°C"
                        for i in items
                    )
        except Exception:
            pass
        return "Weather data unavailable"

    def _get_upcoming_events(self) -> list:
        """Return known Indian festivals and events in the next 7 days."""
        # In production: integrate with a calendar API or maintain event database
        from datetime import date
        today = date.today()
        events = []
        # Static well-known high-demand days
        month = today.month
        if month in (10, 11):
            events.append("Diwali season — historically 40-60% higher demand")
        elif month in (3, 4):
            events.append("Holi season — moderate demand increase")
        elif month == 1:
            events.append("Pongal/Makar Sankranti season")
        elif month == 12:
            events.append("Christmas — moderate demand in metro cities")
        return events

    def _statistical_forecast(self, ngo: NGO, historical: list) -> AgentResult:
        """Simple statistical fallback using historical averages."""
        if historical:
            avg_servings = sum(h.get("servings", 0) for h in historical) / len(historical)
        else:
            avg_servings = ngo.capacity_per_day * 0.5

        today = datetime.now(timezone.utc).date()
        daily = []
        for i in range(7):
            day = today + timedelta(days=i)
            # Weekends see ~20% higher demand
            multiplier = 1.2 if day.weekday() >= 5 else 1.0
            daily.append({
                "date": str(day),
                "expected_servings": int(avg_servings * multiplier),
                "confidence": 0.6,
                "demand_level": "normal",
                "factors": ["historical_average"],
            })

        forecast = {
            "ngo_id": str(ngo.id),
            "forecast_days": 7,
            "daily_predictions": daily,
            "weekly_total": sum(d["expected_servings"] for d in daily),
            "confidence_score": 0.6,
        }
        return AgentResult(
            success=True,
            data=forecast,
            confidence=0.6,
            reasoning="Statistical fallback forecast",
        )

    def _parse_forecast(self, raw: str, ngo_id: str) -> dict:
        """Parse GPT-4o forecast response."""
        try:
            content = raw.strip()
            if "```" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]
            data = json.loads(content)
            data["ngo_id"] = ngo_id
            return data
        except Exception:
            return {"ngo_id": ngo_id, "confidence_score": 0.5, "weekly_total": 0}
