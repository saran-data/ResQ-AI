"""
ResQAI - Food Analysis Agent
Uses Gemini 1.5 Pro Vision to analyze food images and extract:
- Quantity estimation, serving count
- Food classification and freshness score
- Expiry prediction, allergen detection
- Storage requirements
"""

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.food_item import FoodItem, FoodSafetyStatus
from app.agents.food_analysis.prompts import (
    FOOD_ANALYSIS_SYSTEM,
    FOOD_ANALYSIS_IMAGE_PROMPT,
    FOOD_ANALYSIS_TEXT_PROMPT,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class FoodAnalysisAgent(BaseAgent):
    """
    AI Agent: Food Analysis
    Primary model: Gemini 1.5 Pro Vision
    Fallback: GPT-4o (vision)

    Analyzes food donations to extract structured metadata.
    Updates FoodItem records with ai_analysis JSON.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.55

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.FOOD_ANALYSIS

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Analyze all food items in a donation.

        Args:
            context: Pipeline context with donation_id
            image_urls: List of food image URLs (optional)

        Returns:
            AgentResult with aggregated analysis data
        """
        image_urls: list = kwargs.get("image_urls", [])

        # Fetch food items for this donation
        result = await self._db.execute(
            select(FoodItem).where(FoodItem.donation_id == context.donation_id)
        )
        food_items = list(result.scalars().all())

        if not food_items:
            self._logger.warning(f"No food items found for donation {context.donation_id}")
            return AgentResult(
                success=True,
                data={"items_analyzed": 0, "total_servings": 0, "confidence": 0.5},
                confidence=0.5,
                reasoning="No food items to analyze",
            )

        all_analyses = []
        total_servings = 0
        total_weight_kg = 0.0
        min_confidence = 1.0

        for item in food_items:
            analysis = await self._analyze_food_item(item, image_urls)
            all_analyses.append(analysis)

            if analysis["confidence_score"] < min_confidence:
                min_confidence = analysis["confidence_score"]

            total_servings += analysis.get("estimated_servings", 0)
            total_weight_kg += analysis.get("estimated_quantity_kg", 0)

            # Persist AI analysis to the food item
            await self._update_food_item(item, analysis)

        # Update donation totals
        if context.donation_id:
            from sqlalchemy import update
            from app.models.donation import Donation
            await self._db.execute(
                update(Donation)
                .where(Donation.id == context.donation_id)
                .values(
                    total_servings=total_servings,
                    total_weight_kg=round(total_weight_kg, 2),
                    ai_confidence_score=min_confidence,
                )
            )

        return AgentResult(
            success=True,
            data={
                "items_analyzed": len(food_items),
                "total_servings": total_servings,
                "total_weight_kg": round(total_weight_kg, 2),
                "analyses": all_analyses,
                "overall_confidence": min_confidence,
            },
            confidence=min_confidence,
            reasoning=f"Analyzed {len(food_items)} food items. Total servings: {total_servings}",
        )

    async def _analyze_food_item(self, item: FoodItem, image_urls: list) -> dict:
        """
        Analyze a single food item using vision (if images) or text (if no images).
        """
        has_images = bool(image_urls or item.image_urls)

        if has_images:
            urls = image_urls or item.image_urls or []
            try:
                response = await self._llm.complete(
                    model=ModelID.GEMINI_15_PRO,
                    system_prompt=FOOD_ANALYSIS_SYSTEM,
                    user_prompt=FOOD_ANALYSIS_IMAGE_PROMPT,
                    images=urls[:3],  # Max 3 images per item
                    temperature=0.1,
                    max_tokens=1024,
                )
                return self._parse_analysis(response.content, item)
            except Exception as e:
                logger.warning(f"Gemini vision failed, falling back to text: {e}")

        # Text-based fallback
        prompt = FOOD_ANALYSIS_TEXT_PROMPT.format(
            food_name=item.name,
            category=item.category.value if item.category else "unknown",
            quantity=item.quantity,
            unit=item.unit,
            preparation_time=item.preparation_time or "unknown",
            description=item.description or "",
        )
        response = await self._llm.complete(
            model=ModelID.GPT4O_MINI,
            system_prompt=FOOD_ANALYSIS_SYSTEM,
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=1024,
            json_mode=True,
        )
        return self._parse_analysis(response.content, item)

    def _parse_analysis(self, raw_response: str, item: FoodItem) -> dict:
        """Parse and validate the LLM JSON response."""
        try:
            # Extract JSON if wrapped in markdown code blocks
            content = raw_response.strip()
            if "```" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                content = content[start:end]

            data = json.loads(content)

            # Validate and set defaults for required fields
            return {
                "food_item_id": str(item.id),
                "food_name": item.name,
                "detected_items": data.get("detected_items", [item.name]),
                "classification": data.get("classification", item.category.value if item.category else "cooked_meal"),
                "estimated_quantity_kg": float(data.get("estimated_quantity_kg", item.quantity)),
                "estimated_servings": int(data.get("estimated_servings", max(1, int(item.quantity * 4)))),
                "freshness_score": max(0.0, min(1.0, float(data.get("freshness_score", 0.8)))),
                "estimated_expiry_hours": max(1, int(data.get("estimated_expiry_hours", 6))),
                "requires_refrigeration": bool(data.get("requires_refrigeration", False)),
                "is_vegetarian": bool(data.get("is_vegetarian", item.is_vegetarian)),
                "is_vegan": bool(data.get("is_vegan", item.is_vegan)),
                "allergens": data.get("allergens", item.allergens or []),
                "storage_temperature_max_celsius": float(data.get("storage_temperature_max_celsius", 25.0)),
                "quality_assessment": data.get("quality_assessment", "good"),
                "safety_concerns": data.get("safety_concerns", []),
                "confidence_score": max(0.1, min(1.0, float(data.get("confidence_score", 0.75)))),
                "reasoning": data.get("reasoning", "Analysis completed"),
            }
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"Food analysis parse error: {e}, using defaults")
            return {
                "food_item_id": str(item.id),
                "food_name": item.name,
                "detected_items": [item.name],
                "estimated_servings": max(1, int(item.quantity * 4)),
                "estimated_quantity_kg": float(item.quantity),
                "freshness_score": 0.7,
                "estimated_expiry_hours": 6,
                "confidence_score": 0.4,
                "is_vegetarian": item.is_vegetarian,
                "is_vegan": item.is_vegan,
                "allergens": item.allergens or [],
                "requires_refrigeration": False,
                "reasoning": "Parse error — using defaults",
            }

    async def _update_food_item(self, item: FoodItem, analysis: dict) -> None:
        """Persist the analysis result to the food item record."""
        from sqlalchemy import update
        from datetime import datetime, timezone

        await self._db.execute(
            update(FoodItem)
            .where(FoodItem.id == item.id)
            .values(
                estimated_servings=analysis.get("estimated_servings"),
                weight_kg=analysis.get("estimated_quantity_kg"),
                requires_refrigeration=analysis.get("requires_refrigeration", False),
                storage_temperature_max=analysis.get("storage_temperature_max_celsius"),
                is_vegetarian=analysis.get("is_vegetarian", item.is_vegetarian),
                is_vegan=analysis.get("is_vegan", item.is_vegan),
                allergens=analysis.get("allergens", []),
                ai_analysis=analysis,
                ai_analyzed_at=datetime.now(timezone.utc).isoformat(),
                safety_status=FoodSafetyStatus.PENDING,  # Safety agent will update this
            )
        )
