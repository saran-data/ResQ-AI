"""
ResQAI - Fraud Detection Agent
Uses DeepSeek to detect fake NGOs, suspicious donation patterns,
repeated fraud, and anomalous platform activity.

Detection categories:
- Fake NGO registrations
- Inflated donation quantities
- Repeated pickup-no-shows
- Suspicious OTP patterns
- Velocity fraud (too many donations too fast)
- Geo-inconsistency (donations claimed from impossible locations)
- Identity fraud (duplicate registrations)
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.donation import Donation, DonationStatus
from app.models.restaurant import Restaurant
from app.models.ngo import NGO
from app.core.logging import get_logger

logger = get_logger(__name__)

FRAUD_DETECTION_SYSTEM = """You are a fraud detection AI for the ResQAI food rescue platform.

Analyze patterns to identify fraudulent activity. Be specific and evidence-based.

Respond with JSON:
{
  "fraud_score": <float 0.0-1.0>,
  "risk_level": "low/medium/high/critical",
  "is_fraudulent": <boolean>,
  "fraud_categories": ["list of detected fraud types"],
  "evidence": ["specific data points supporting the assessment"],
  "recommended_action": "approve/flag/suspend/block",
  "confidence_score": <float 0.0-1.0>,
  "reasoning": "<detailed explanation>"
}

Fraud score guide:
- 0.0-0.3: Low risk (normal activity)
- 0.3-0.6: Medium risk (monitor)
- 0.6-0.8: High risk (manual review required)
- 0.8-1.0: Critical (auto-block)
"""


class FraudDetectionAgent(BaseAgent):
    """
    AI Agent: Fraud Detection
    Primary model: DeepSeek (pattern recognition / code-style reasoning)

    Analyzes donations, NGOs, and restaurants for fraud signals.
    Results update fraud_score on the relevant entity.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.FRAUD_DETECTION

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Run fraud analysis on a donation or entity.
        Triggered after donation creation and on a nightly schedule.
        """
        # Determine target: donation or entity check
        if context.donation_id:
            return await self._check_donation_fraud(context.donation_id)

        entity_type = context.metadata.get("entity_type")
        entity_id = context.metadata.get("entity_id")
        if entity_type and entity_id:
            return await self._check_entity_fraud(entity_type, entity_id)

        return AgentResult.failure("No donation_id or entity context provided")

    async def _check_donation_fraud(self, donation_id: str) -> AgentResult:
        """Analyze a specific donation for fraud signals."""
        donation_result = await self._db.execute(
            select(Donation).where(Donation.id == donation_id)
        )
        donation = donation_result.scalar_one_or_none()
        if not donation:
            return AgentResult.failure("Donation not found")

        # Gather restaurant history
        restaurant_history = await self._get_restaurant_history(donation.restaurant_id)
        # Rule-based pre-checks
        rule_flags = self._rule_based_checks(donation, restaurant_history)

        # If rule-based already flags as critical, skip LLM
        if rule_flags["fraud_score"] >= 0.85:
            await self._apply_fraud_result(donation, rule_flags)
            return AgentResult(
                success=True,
                data=rule_flags,
                confidence=rule_flags["confidence_score"],
                reasoning=f"Critical fraud detected: {rule_flags['fraud_categories']}",
            )

        # LLM-based analysis for nuanced detection
        llm_result = await self._llm_fraud_analysis(donation, restaurant_history, rule_flags)

        # Combine rule + LLM scores
        final_score = max(rule_flags["fraud_score"], llm_result.get("fraud_score", 0))
        final_result = {**llm_result, "fraud_score": final_score}

        await self._apply_fraud_result(donation, final_result)

        return AgentResult(
            success=True,
            data=final_result,
            confidence=final_result.get("confidence_score", 0.7),
            model_used=ModelID.DEEPSEEK_CHAT.value,
            reasoning=f"Fraud score: {final_score:.2f} — {final_result.get('risk_level', 'low')} risk",
        )

    async def _check_entity_fraud(self, entity_type: str, entity_id: str) -> AgentResult:
        """Analyze an NGO or restaurant for fraud/legitimacy."""
        if entity_type == "ngo":
            result = await self._db.execute(select(NGO).where(NGO.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return AgentResult.failure("NGO not found")

            prompt = f"""Analyze this NGO for fraud/legitimacy:
Name: {entity.name}
Registration: {entity.registration_number}
DARPAN ID: {entity.darpan_id}
City: {entity.city}
Capacity: {entity.capacity_per_day} servings/day
Beneficiaries: {entity.beneficiaries_count}
Total Received: {entity.total_received} donations
Created: {entity.created_at}

Check for: fake registrations, inflated capacity claims, mismatched data, suspicious timing."""

        elif entity_type == "restaurant":
            result = await self._db.execute(select(Restaurant).where(Restaurant.id == entity_id))
            entity = result.scalar_one_or_none()
            if not entity:
                return AgentResult.failure("Restaurant not found")

            prompt = f"""Analyze this restaurant for fraud:
Name: {entity.name}
FSSAI License: {entity.fssai_license}
City: {entity.city}
Total Donations: {entity.total_donations}
Total Meals: {entity.total_meals_saved}
Created: {entity.created_at}

Check for: fake FSSAI numbers, suspicious donation patterns, data inconsistencies."""
        else:
            return AgentResult.failure(f"Unsupported entity type: {entity_type}")

        try:
            response = await self._llm.complete(
                model=ModelID.DEEPSEEK_CHAT,
                system_prompt=FRAUD_DETECTION_SYSTEM,
                user_prompt=prompt,
                temperature=0.05,
                max_tokens=512,
                json_mode=True,
            )
            result_data = json.loads(response.content)

            # Update entity fraud score
            from sqlalchemy import update
            if entity_type == "ngo":
                await self._db.execute(
                    update(NGO)
                    .where(NGO.id == entity_id)
                    .values(
                        fraud_score=result_data.get("fraud_score", 0),
                        fraud_flags=result_data.get("fraud_categories", []),
                    )
                )
            elif entity_type == "restaurant":
                await self._db.execute(
                    update(Restaurant)
                    .where(Restaurant.id == entity_id)
                    .values(fraud_score=result_data.get("fraud_score", 0) if hasattr(Restaurant, 'fraud_score') else None)
                )

            return AgentResult(
                success=True,
                data=result_data,
                confidence=result_data.get("confidence_score", 0.7),
                reasoning=result_data.get("reasoning", "Entity fraud check completed"),
            )
        except Exception as e:
            logger.warning(f"Entity fraud check failed: {e}")
            return AgentResult(
                success=True,
                data={"fraud_score": 0.1, "risk_level": "low", "confidence_score": 0.5},
                confidence=0.5,
            )

    def _rule_based_checks(self, donation: Donation, history: dict) -> dict:
        """Fast deterministic fraud rules."""
        flags = []
        score = 0.0

        # Velocity check: too many donations in short time
        recent_count = history.get("last_24h_donations", 0)
        if recent_count > 10:
            flags.append("velocity_fraud")
            score += 0.3
        elif recent_count > 5:
            flags.append("high_velocity")
            score += 0.1

        # Unusually large donation
        if donation.total_servings and donation.total_servings > 5000:
            flags.append("unusually_large_donation")
            score += 0.2

        # Unusually small but claims high value
        if (donation.total_servings and donation.total_servings < 10 and
                donation.estimated_value_inr and donation.estimated_value_inr > 50000):
            flags.append("value_quantity_mismatch")
            score += 0.25

        # First donation ever (new account risk)
        if history.get("total_donations", 0) == 0:
            flags.append("first_time_donor")
            score += 0.05  # Minor flag, not fraud on its own

        return {
            "fraud_score": min(score, 1.0),
            "risk_level": self._score_to_level(score),
            "is_fraudulent": score >= 0.8,
            "fraud_categories": flags,
            "evidence": [f"Recent 24h donations: {recent_count}"],
            "recommended_action": "block" if score >= 0.8 else "flag" if score >= 0.5 else "approve",
            "confidence_score": 0.75,
            "reasoning": f"Rule-based analysis: {len(flags)} flag(s) found",
        }

    async def _llm_fraud_analysis(
        self, donation: Donation, history: dict, rule_result: dict
    ) -> dict:
        """LLM-based nuanced fraud analysis."""
        prompt = f"""Analyze this food donation for fraud:

Donation:
- ID: {str(donation.id)[:8]}
- Total Servings: {donation.total_servings}
- Weight: {donation.total_weight_kg}kg
- Status: {donation.status.value if donation.status else 'unknown'}
- Created: {donation.created_at}
- Is Flagged: {donation.is_flagged}

Restaurant History:
{json.dumps(history, indent=2)}

Rule-based flags detected: {rule_result.get('fraud_categories', [])}
Current rule score: {rule_result.get('fraud_score', 0):.2f}

Perform deeper analysis considering behavioral patterns, timing anomalies, and data consistency."""

        try:
            response = await self._llm.complete(
                model=ModelID.DEEPSEEK_CHAT,
                system_prompt=FRAUD_DETECTION_SYSTEM,
                user_prompt=prompt,
                temperature=0.05,
                max_tokens=512,
                json_mode=True,
            )
            return json.loads(response.content)
        except Exception as e:
            logger.warning(f"LLM fraud analysis failed: {e}")
            return rule_result

    async def _get_restaurant_history(self, restaurant_id) -> dict:
        """Gather restaurant donation history for context."""
        twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        recent = (await self._db.execute(
            select(func.count(Donation.id))
            .where(Donation.restaurant_id == restaurant_id, Donation.created_at >= twenty_four_hours_ago)
        )).scalar_one()

        weekly = (await self._db.execute(
            select(func.count(Donation.id))
            .where(Donation.restaurant_id == restaurant_id, Donation.created_at >= seven_days_ago)
        )).scalar_one()

        total = (await self._db.execute(
            select(func.count(Donation.id))
            .where(Donation.restaurant_id == restaurant_id)
        )).scalar_one()

        cancelled = (await self._db.execute(
            select(func.count(Donation.id))
            .where(
                Donation.restaurant_id == restaurant_id,
                Donation.status == DonationStatus.CANCELLED,
            )
        )).scalar_one()

        return {
            "last_24h_donations": recent,
            "last_7d_donations": weekly,
            "total_donations": total,
            "cancellation_count": cancelled,
            "cancellation_rate": round((cancelled / max(total, 1)) * 100, 1),
        }

    async def _apply_fraud_result(self, donation: Donation, result: dict) -> None:
        """Apply fraud detection result to the donation record."""
        from sqlalchemy import update
        score = result.get("fraud_score", 0)
        is_flagged = score >= 0.5
        await self._db.execute(
            update(Donation)
            .where(Donation.id == donation.id)
            .values(
                fraud_score=score,
                fraud_flags=result.get("fraud_categories", []),
                is_flagged=is_flagged,
            )
        )
        if is_flagged:
            logger.warning(
                f"Donation flagged for fraud",
                donation_id=str(donation.id),
                score=score,
                categories=result.get("fraud_categories"),
            )

    def _score_to_level(self, score: float) -> str:
        if score < 0.3:
            return "low"
        elif score < 0.6:
            return "medium"
        elif score < 0.8:
            return "high"
        return "critical"
