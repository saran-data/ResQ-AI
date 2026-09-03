"""
ResQAI - Food Safety Agent
Uses Claude 3.5 Sonnet to evaluate food against FSSAI guidelines,
WHO standards, and custom safety rules.

Checks:
- Preparation-to-consumption time window
- Storage temperature compliance
- Allergen labeling requirements
- Expiry and freshness thresholds
- Food packaging and handling safety
- FSSAI regulatory compliance
"""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.food_item import FoodItem, FoodSafetyStatus
from app.models.donation import Donation
from app.core.logging import get_logger

logger = get_logger(__name__)

FOOD_SAFETY_SYSTEM = """You are a certified food safety officer with expertise in:
- FSSAI (Food Safety and Standards Authority of India) regulations
- WHO food safety guidelines
- Hazard Analysis Critical Control Points (HACCP)
- Temperature danger zone management (5°C - 60°C)
- Food handling and storage best practices

You evaluate donated food for safety before distribution to vulnerable populations
(orphans, elderly, homeless). Your assessment must be conservative and protective.

Respond ONLY with a JSON object:
{
  "is_safe": <boolean>,
  "safety_score": <float 0.0-1.0>,
  "risk_level": "low/medium/high/critical",
  "fssai_compliant": <boolean>,
  "violations": ["list of specific safety violations found"],
  "warnings": ["list of cautions that don't disqualify but need attention"],
  "recommendations": ["specific handling/storage instructions"],
  "max_safe_hours": <integer - hours food remains safe>,
  "rejection_reason": "null or specific reason for rejection",
  "confidence_score": <float 0.0-1.0>,
  "reasoning": "detailed safety assessment narrative"
}

REJECT food if:
- Freshness score < 0.3
- Estimated expiry < 1 hour
- Visible signs of spoilage, mold, or contamination
- Temperature abuse (cooked food > 2 hours in danger zone)
- High-risk items without proper cold chain
- Preparation time > 12 hours ago (cooked meals)
"""


class FoodSafetyAgent(BaseAgent):
    """
    AI Agent: Food Safety
    Primary model: Claude 3.5 Sonnet
    Rationale: Best long-context reasoning for regulatory document analysis

    Evaluates all food items in a donation against FSSAI/WHO standards.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.7  # Higher threshold for safety decisions

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.FOOD_SAFETY

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Run safety checks on all food items in the donation.

        Returns:
            AgentResult with is_safe bool and per-item safety data
        """
        # Fetch donation + food items
        donation_result = await self._db.execute(
            select(Donation).where(Donation.id == context.donation_id)
        )
        donation = donation_result.scalar_one_or_none()
        if not donation:
            return AgentResult.failure("Donation not found")

        food_result = await self._db.execute(
            select(FoodItem).where(FoodItem.donation_id == context.donation_id)
        )
        food_items = list(food_result.scalars().all())
        if not food_items:
            return AgentResult.failure("No food items to evaluate")

        # Get Food Analysis results from context (if available)
        analysis_results = context.get_result(AgentType.FOOD_ANALYSIS.value) or {}
        item_analyses = {
            a["food_item_id"]: a
            for a in analysis_results.get("analyses", [])
        }

        safety_results = []
        overall_safe = True
        lowest_safety_score = 1.0
        all_violations = []

        for item in food_items:
            item_analysis = item_analyses.get(str(item.id), {})
            safety = await self._check_item_safety(item, item_analysis)
            safety_results.append(safety)

            if not safety["is_safe"]:
                overall_safe = False
                all_violations.extend(safety.get("violations", []))

            if safety["safety_score"] < lowest_safety_score:
                lowest_safety_score = safety["safety_score"]

            # Update food item safety status in DB
            await self._db.execute(
                update(FoodItem)
                .where(FoodItem.id == item.id)
                .values(
                    safety_status=FoodSafetyStatus.SAFE if safety["is_safe"] else FoodSafetyStatus.UNSAFE,
                    safety_notes=safety.get("reasoning"),
                    rejection_reason=safety.get("rejection_reason") if not safety["is_safe"] else None,
                )
            )

        # Update donation safety score
        await self._db.execute(
            update(Donation)
            .where(Donation.id == context.donation_id)
            .values(
                ai_safety_score=lowest_safety_score,
                ai_rejection_reason="; ".join(all_violations) if all_violations and not overall_safe else None,
            )
        )

        reasoning = (
            f"Safety check: {'PASS' if overall_safe else 'FAIL'}. "
            f"Score: {lowest_safety_score:.2f}. "
            f"{len(all_violations)} violation(s) found."
        )

        return AgentResult(
            success=True,
            data={
                "is_safe": overall_safe,
                "overall_safety_score": lowest_safety_score,
                "items_checked": len(food_items),
                "violations": all_violations,
                "item_safety": safety_results,
            },
            confidence=lowest_safety_score,
            reasoning=reasoning,
        )

    async def _check_item_safety(self, item: FoodItem, prior_analysis: dict) -> dict:
        """Perform safety check on a single food item."""
        now = datetime.now(timezone.utc)
        hours_since_prep = 0
        if item.preparation_time:
            try:
                prep_time = datetime.fromisoformat(item.preparation_time.replace("Z", "+00:00"))
                hours_since_prep = (now - prep_time).total_seconds() / 3600
            except ValueError:
                hours_since_prep = 2  # Assume 2 hours if unknown

        freshness = prior_analysis.get("freshness_score", 0.8)
        expiry_hours = prior_analysis.get("estimated_expiry_hours", 6)

        # Quick rule-based pre-checks before calling LLM
        critical_failure = None
        if freshness < 0.2:
            critical_failure = "Freshness score critically low (< 0.2) — food likely spoiled"
        elif expiry_hours < 0:
            critical_failure = "Food has already expired"
        elif hours_since_prep > 12:
            critical_failure = f"Cooked food prepared {hours_since_prep:.1f} hours ago exceeds 12-hour safety limit"

        if critical_failure:
            return {
                "food_item_id": str(item.id),
                "food_name": item.name,
                "is_safe": False,
                "safety_score": 0.1,
                "risk_level": "critical",
                "fssai_compliant": False,
                "violations": [critical_failure],
                "warnings": [],
                "recommendations": ["Discard immediately"],
                "rejection_reason": critical_failure,
                "confidence_score": 0.95,
                "reasoning": critical_failure,
            }

        # LLM-based safety evaluation
        prompt = f"""Evaluate food safety for this donated food item:

Food Item: {item.name}
Category: {item.category.value if item.category else 'unknown'}
Quantity: {item.quantity} {item.unit}
Preparation Time: {item.preparation_time or 'unknown'} ({hours_since_prep:.1f} hours ago)
Best Before: {item.best_before or 'unknown'}
Storage Temperature Required: {item.storage_temperature_min or 0}°C to {item.storage_temperature_max or 25}°C
Requires Refrigeration: {item.requires_refrigeration}
Requires Freezing: {item.requires_freezing}
Allergens: {', '.join(item.allergens) if item.allergens else 'none declared'}
Is Vegetarian: {item.is_vegetarian}

AI Analysis Data:
- Freshness Score: {freshness:.2f}
- Estimated Expiry: {expiry_hours} hours remaining
- Quality Assessment: {prior_analysis.get('quality_assessment', 'unknown')}
- Safety Concerns from Vision: {prior_analysis.get('safety_concerns', [])}

This food will be distributed to orphans, elderly, and vulnerable populations.
Apply conservative FSSAI and WHO food safety standards."""

        try:
            response = await self._llm.complete(
                model=ModelID.CLAUDE_35_SONNET,
                system_prompt=FOOD_SAFETY_SYSTEM,
                user_prompt=prompt,
                temperature=0.05,  # Very low temperature for consistent safety decisions
                max_tokens=1024,
            )
            result = self._parse_safety_response(response.content, item)
        except Exception as e:
            logger.warning(f"Claude safety check failed, using rule-based: {e}")
            result = self._rule_based_safety_check(item, freshness, expiry_hours, hours_since_prep)

        result["food_item_id"] = str(item.id)
        result["food_name"] = item.name
        return result

    def _parse_safety_response(self, raw: str, item: FoodItem) -> dict:
        """Parse Claude's safety assessment response."""
        try:
            content = raw.strip()
            if "```" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]
            data = json.loads(content)
            return {
                "is_safe": bool(data.get("is_safe", True)),
                "safety_score": max(0.0, min(1.0, float(data.get("safety_score", 0.8)))),
                "risk_level": data.get("risk_level", "low"),
                "fssai_compliant": bool(data.get("fssai_compliant", True)),
                "violations": data.get("violations", []),
                "warnings": data.get("warnings", []),
                "recommendations": data.get("recommendations", []),
                "max_safe_hours": int(data.get("max_safe_hours", 4)),
                "rejection_reason": data.get("rejection_reason") if not data.get("is_safe") else None,
                "confidence_score": float(data.get("confidence_score", 0.8)),
                "reasoning": data.get("reasoning", "Safety assessment completed"),
            }
        except Exception as e:
            logger.warning(f"Safety parse error: {e}")
            return self._rule_based_safety_check(item, 0.7, 4, 2)

    def _rule_based_safety_check(
        self, item: FoodItem, freshness: float, expiry_hours: int, hours_since_prep: float
    ) -> dict:
        """Deterministic fallback safety check based on rules only."""
        violations = []
        warnings = []
        is_safe = True

        if freshness < 0.3:
            violations.append(f"Freshness score {freshness:.2f} below safe threshold (0.3)")
            is_safe = False
        elif freshness < 0.5:
            warnings.append(f"Freshness score {freshness:.2f} is marginal — handle with care")

        if expiry_hours < 1:
            violations.append("Food expiry is imminent (< 1 hour)")
            is_safe = False
        elif expiry_hours < 2:
            warnings.append("Less than 2 hours before expiry")

        if hours_since_prep > 8:
            violations.append(f"Prepared {hours_since_prep:.1f} hours ago — exceeds 8-hour guideline")
            is_safe = False
        elif hours_since_prep > 4:
            warnings.append(f"Prepared {hours_since_prep:.1f} hours ago")

        safety_score = max(0.1, freshness * 0.6 + min(expiry_hours / 12, 1.0) * 0.4) if is_safe else 0.2

        return {
            "is_safe": is_safe,
            "safety_score": safety_score,
            "risk_level": "low" if is_safe else "high",
            "fssai_compliant": is_safe,
            "violations": violations,
            "warnings": warnings,
            "recommendations": ["Store at safe temperature", "Distribute within 2 hours"],
            "max_safe_hours": max(0, int(expiry_hours)),
            "rejection_reason": "; ".join(violations) if violations else None,
            "confidence_score": 0.7,
            "reasoning": "Rule-based safety check applied",
        }
