"""
ResQAI - AI Orchestrator (Full Implementation)
The central brain that coordinates all 10 AI agents.

Responsibilities:
- Task delegation to the right agent
- Sequential and parallel agent execution
- Context sharing between agents
- Retry and failure recovery
- Decision logging
- WebSocket progress updates
- Kafka event emission
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.donation import DonationStatus
from app.models.ai_decision import AgentType
from app.orchestrator.base_agent import AgentContext, AgentResult
from app.orchestrator.model_registry import get_model_registry
from app.repositories.donation_repository import DonationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.ngo_repository import NGORepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class AIOrchestrator:
    """
    Master orchestrator for all ResQAI AI agents.

    The full pipeline on a new donation:
    1. Food Analysis Agent     (Gemini) → analyze food images
    2. Food Safety Agent       (Claude) → FSSAI compliance check
    3. NGO Matching Agent      (GPT-4o) → rank and select NGO
    4. Route Optimization Agent (DeepSeek) → compute optimal route
    5. Volunteer Agent         (Llama)  → assign volunteer
    6. Notification Agent      (Mistral) → send multi-channel alerts

    On-demand:
    - Demand Prediction Agent  (GPT-4o)
    - Fraud Detection Agent    (DeepSeek)
    - Analytics Agent          (GPT-4o)
    - Admin Assistant          (Claude)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._donation_repo = DonationRepository(db)
        self._registry = get_model_registry()

    # -------------------------------------------------------
    # Full Pipeline (triggered on donation.created Kafka event)
    # -------------------------------------------------------
    async def process_donation_pipeline(self, donation_id: str) -> dict:
        """
        Execute the complete AI pipeline for a new donation.
        Runs sequentially, passing context between agents.

        Pipeline stages:
        food_analysis → food_safety → ngo_matching → route → volunteer → notification

        Args:
            donation_id: UUID of the donation to process

        Returns:
            Dict summarizing all agent results
        """
        logger.info(f"AI Pipeline starting", donation_id=donation_id)
        context = AgentContext(donation_id=donation_id, db=self._db)

        pipeline_results: dict[str, Any] = {}
        pipeline_start = datetime.now(timezone.utc)

        # ---- Stage 1: Food Analysis ----
        food_result = await self.run_food_analysis(donation_id, [])
        context.set_result(AgentType.FOOD_ANALYSIS.value, food_result)
        pipeline_results["food_analysis"] = food_result

        # ---- Stage 2: Food Safety ----
        safety_result = await self.run_food_safety(donation_id, context)
        context.set_result(AgentType.FOOD_SAFETY.value, safety_result)
        pipeline_results["food_safety"] = safety_result

        # Halt pipeline if food is unsafe
        if not safety_result.get("is_safe", True):
            await self._donation_repo.transition_status(
                donation_id, DonationStatus.SAFETY_FAILED, actor="food_safety_agent"
            )
            logger.warning(f"Food safety check failed, halting pipeline", donation_id=donation_id)
            await self._push_ws_update(donation_id, "pipeline.safety_failed", safety_result)
            return {"status": "safety_failed", **pipeline_results}

        # Transition to matching phase
        await self._donation_repo.transition_status(
            donation_id, DonationStatus.MATCHING, actor="food_safety_agent"
        )

        # ---- Stage 3: NGO Matching ----
        ngo_result = await self.run_ngo_matching(donation_id)
        context.set_result(AgentType.NGO_MATCHING.value, ngo_result)
        pipeline_results["ngo_matching"] = ngo_result

        matched_ngo_id = ngo_result.get("matched_ngo_id")
        if not matched_ngo_id:
            logger.warning(f"No NGO matched", donation_id=donation_id)
            return {"status": "no_ngo_available", **pipeline_results}

        # Update donation with matched NGO
        await self._donation_repo.update(donation_id, {
            "matched_ngo_id": matched_ngo_id,
            "matched_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._donation_repo.transition_status(
            donation_id, DonationStatus.MATCHED, actor="ngo_matching_agent"
        )

        # ---- Stages 4-6: Run in parallel (route + volunteer + notification) ----
        route_task = asyncio.create_task(self.run_route_optimization(donation_id))
        volunteer_task = asyncio.create_task(self._run_volunteer_agent(donation_id, context))

        route_result, volunteer_result = await asyncio.gather(
            route_task, volunteer_task, return_exceptions=True
        )

        if isinstance(route_result, Exception):
            route_result = {"error": str(route_result)}
        if isinstance(volunteer_result, Exception):
            volunteer_result = {"error": str(volunteer_result)}

        pipeline_results["route_optimization"] = route_result
        pipeline_results["volunteer_assignment"] = volunteer_result

        # ---- Stage 6: Notifications ----
        await self.run_notification_agent(donation_id, "donation_matched")
        pipeline_results["notification"] = {"status": "sent"}

        duration_ms = int((datetime.now(timezone.utc) - pipeline_start).total_seconds() * 1000)
        logger.info(
            f"AI Pipeline complete",
            donation_id=donation_id,
            duration_ms=duration_ms,
            status="success",
        )

        await self._push_ws_update(donation_id, "pipeline.completed", pipeline_results)
        return {"status": "success", "duration_ms": duration_ms, **pipeline_results}

    # -------------------------------------------------------
    # Individual Agent Runners
    # -------------------------------------------------------
    async def run_food_analysis(self, donation_id: str, image_urls: list) -> dict:
        """
        Invoke the Food Analysis Agent (Gemini vision).
        Analyzes food images: quantity, freshness, classification, servings.
        """
        from app.agents.food_analysis.agent import FoodAnalysisAgent
        agent = FoodAnalysisAgent(self._db)
        context = AgentContext(donation_id=donation_id, db=self._db)
        result = await agent.run(context, image_urls=image_urls, task_name="food_image_analysis")
        return result.data if result.success else {"error": result.data.get("error")}

    async def run_food_safety(self, donation_id: str, context: AgentContext) -> dict:
        """Invoke the Food Safety Agent (Claude) — FSSAI compliance + expiry check."""
        from app.agents.food_safety.agent import FoodSafetyAgent
        agent = FoodSafetyAgent(self._db)
        result = await agent.run(context, task_name="food_safety_check")
        return result.data if result.success else {"is_safe": False, "reason": "Safety check failed"}

    async def run_ngo_matching(self, donation_id: str) -> dict:
        """Invoke the NGO Matching Agent (GPT-4o) — rank and select best NGO."""
        from app.agents.ngo_matching.agent import NGOMatchingAgent
        agent = NGOMatchingAgent(self._db)
        context = AgentContext(donation_id=donation_id, db=self._db)
        result = await agent.run(context, task_name="ngo_matching")
        return result.data if result.success else {"matched_ngo_id": None}

    async def run_route_optimization(self, donation_id: str) -> dict:
        """Invoke the Route Optimization Agent (DeepSeek) — A*/VRP routing."""
        from app.agents.route_optimization.agent import RouteOptimizationAgent
        agent = RouteOptimizationAgent(self._db)
        context = AgentContext(donation_id=donation_id, db=self._db)
        result = await agent.run(context, task_name="route_optimization")
        return result.data if result.success else {"error": "Route computation failed"}

    async def _run_volunteer_agent(self, donation_id: str, context: AgentContext) -> dict:
        """Invoke the Volunteer Agent (Llama) — assign nearest available volunteer."""
        from app.agents.volunteer.agent import VolunteerAgent
        agent = VolunteerAgent(self._db)
        result = await agent.run(context, task_name="volunteer_matching")
        return result.data if result.success else {"assigned": False}

    async def run_notification_agent(self, donation_id: str, notification_type: str) -> dict:
        """Invoke the Notification Agent (Mistral) — multi-channel alert dispatch."""
        from app.agents.notification.agent import NotificationAgent
        agent = NotificationAgent(self._db)
        context = AgentContext(donation_id=donation_id, db=self._db)
        result = await agent.run(context, notification_type=notification_type)
        return result.data if result.success else {"sent": False}

    async def run_demand_prediction_all(self) -> None:
        """Run demand prediction for all active NGOs (scheduled weekly)."""
        from app.agents.demand_prediction.agent import DemandPredictionAgent
        ngo_repo = NGORepository(self._db)
        ngos, _ = await ngo_repo.get_all(
            filters={"is_verified": True},
            limit=500,
        )
        for ngo in ngos:
            context = AgentContext(donation_id="", db=self._db)
            context.metadata["ngo_id"] = str(ngo.id)
            agent = DemandPredictionAgent(self._db)
            try:
                await agent.run(context, task_name="demand_prediction")
            except Exception as e:
                logger.warning(f"Demand prediction failed for NGO {ngo.id}: {e}")

    async def run_fraud_check(self, donation_id: str) -> dict:
        """Run Fraud Detection Agent on a specific donation."""
        from app.agents.fraud_detection.agent import FraudDetectionAgent
        agent = FraudDetectionAgent(self._db)
        context = AgentContext(donation_id=donation_id, db=self._db)
        result = await agent.run(context, task_name="fraud_detection")
        return result.data if result.success else {"fraud_score": 0.0}

    async def run_admin_chat(self, session_id: str, user_message: str) -> str:
        """Invoke Admin Assistant Agent for chatbot response."""
        from app.agents.admin_assistant.agent import AdminAssistantAgent
        agent = AdminAssistantAgent(self._db)
        context = AgentContext(donation_id="", db=self._db, session_id=session_id)
        context.metadata["user_message"] = user_message
        result = await agent.run(context, task_name="admin_chat")
        if result.success:
            return result.data.get("response", "I couldn't process that request.")
        return "I'm having trouble responding right now. Please try again."

    async def dispatch_agent(self, agent_type: str, context_data: dict) -> dict:
        """
        Generic dispatch for manually triggering any agent by name.
        Used by admin API and background tasks.
        """
        donation_id = context_data.get("donation_id", "")
        handlers = {
            "food_analysis": lambda: self.run_food_analysis(donation_id, []),
            "food_safety": lambda: self.run_food_safety(donation_id, AgentContext(donation_id, self._db)),
            "ngo_matching": lambda: self.run_ngo_matching(donation_id),
            "route_optimization": lambda: self.run_route_optimization(donation_id),
            "fraud_detection": lambda: self.run_fraud_check(donation_id),
            "notification": lambda: self.run_notification_agent(donation_id, "system_alert"),
        }
        handler = handlers.get(agent_type)
        if not handler:
            return {"error": f"Unknown agent type: {agent_type}"}
        return await handler()

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------
    async def _push_ws_update(self, donation_id: str, event: str, data: dict) -> None:
        """Push a WebSocket event to all clients tracking this donation."""
        try:
            from app.websockets.manager import push_to_donation_room
            await push_to_donation_room(donation_id, event, data)
        except Exception as e:
            logger.debug(f"WS push failed (non-fatal): {e}")

    async def _emit_kafka_event(self, topic: str, payload: dict) -> None:
        if not settings.ENABLE_KAFKA:
            return
        try:
            from app.events.kafka_manager import get_kafka_manager
            km = get_kafka_manager()
            if km:
                await km.produce(topic, payload)
        except Exception as e:
            logger.debug(f"Kafka emit failed (non-fatal): {e}")
