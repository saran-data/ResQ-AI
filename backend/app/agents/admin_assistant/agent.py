"""
ResQAI - Admin Assistant Agent
Uses Claude 3.5 Sonnet as a conversational AI chatbot for platform admins.

Capabilities:
- Answer questions about system status, KPIs, NGOs, restaurants
- Explain AI decisions (Explainable AI)
- Help with complaint resolution
- Query donation analytics in natural language
- Generate reports on-demand
- System troubleshooting assistance
"""

import json
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.core.logging import get_logger

logger = get_logger(__name__)

ADMIN_ASSISTANT_SYSTEM = """You are the ResQAI Admin Assistant — an AI-powered chatbot helping
platform administrators manage the food rescue ecosystem.

You have access to real-time platform data and can answer questions about:
- Donation statistics and trends
- NGO performance and capacity
- Restaurant contribution metrics
- Volunteer activity and assignments
- AI agent decisions and explanations
- System health and performance
- Complaints and issues
- Food safety audit results
- Fraud detection findings

Provide precise, data-driven answers. When you don't have specific data, say so clearly.
Suggest actionable next steps when appropriate.
Maintain a professional but approachable tone.
"""

FUNCTION_DESCRIPTIONS = """
Available platform data:
- Total donations: {total_donations}
- Confirmed deliveries: {confirmed_deliveries}
- Active restaurants: {active_restaurants}
- Active NGOs: {active_ngos}
- Active volunteers: {active_volunteers}
- Flagged donations: {flagged_donations}
- Success rate: {success_rate}%
- Total meals saved: {total_meals}
"""


class AdminAssistantAgent(BaseAgent):
    """
    AI Agent: Admin Assistant
    Primary model: Claude 3.5 Sonnet (best conversational AI)

    Provides an intelligent chatbot for platform administrators.
    Supports multi-turn conversations via session_id tracking.
    Uses RAG to retrieve relevant platform documents for context.
    """

    MAX_RETRIES = 2
    CONFIDENCE_THRESHOLD = 0.3

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ADMIN_ASSISTANT

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """Process an admin chat message and generate a response."""
        user_message: str = context.metadata.get("user_message", "")
        conversation_history: list = context.metadata.get("history", [])

        if not user_message:
            return AgentResult.failure("No message provided")

        # Gather real-time platform data for context
        platform_data = await self._get_platform_summary()

        # Retrieve relevant RAG documents
        rag_context = await self._retrieve_rag_context(user_message)

        # Build enriched system prompt with live data
        enriched_system = ADMIN_ASSISTANT_SYSTEM + "\n\nCURRENT PLATFORM STATUS:\n" + \
            FUNCTION_DESCRIPTIONS.format(**platform_data)

        if rag_context:
            enriched_system += f"\n\nRELEVANT KNOWLEDGE BASE:\n{rag_context[:1500]}"

        # Build conversation history for multi-turn support
        history_text = ""
        for turn in conversation_history[-6:]:  # Last 3 exchanges
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_text += f"\n{role.upper()}: {content}"

        full_prompt = f"{history_text}\n\nADMIN: {user_message}"

        try:
            response = await self._llm.complete(
                model=ModelID.CLAUDE_35_SONNET,
                system_prompt=enriched_system,
                user_prompt=full_prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            # Cache conversation in Redis for multi-turn support
            await self._cache_conversation(
                session_id=context.session_id,
                user_message=user_message,
                assistant_response=response.content,
            )

            return AgentResult(
                success=True,
                data={
                    "response": response.content,
                    "session_id": context.session_id,
                    "tokens_used": response.total_tokens,
                    "model": response.model,
                },
                confidence=0.9,
                model_used=ModelID.CLAUDE_35_SONNET.value,
                reasoning="Admin assistant response generated",
            )

        except Exception as e:
            logger.error(f"Admin assistant failed: {e}")
            # Fallback: use platform data to answer directly
            fallback = self._generate_fallback_response(user_message, platform_data)
            return AgentResult(
                success=True,
                data={"response": fallback, "session_id": context.session_id},
                confidence=0.5,
                reasoning="Fallback response generated",
            )

    async def _get_platform_summary(self) -> dict:
        """Fetch real-time platform KPIs for chatbot context."""
        from app.models.donation import Donation, DonationStatus
        from app.models.restaurant import Restaurant
        from app.models.ngo import NGO
        from app.models.volunteer import Volunteer

        total = (await self._db.execute(select(func.count(Donation.id)))).scalar_one()
        confirmed = (await self._db.execute(
            select(func.count(Donation.id)).where(Donation.status == DonationStatus.CONFIRMED)
        )).scalar_one()
        meals = (await self._db.execute(select(func.sum(Donation.total_servings)))).scalar_one() or 0
        restaurants = (await self._db.execute(select(func.count(Restaurant.id)))).scalar_one()
        ngos = (await self._db.execute(select(func.count(NGO.id)))).scalar_one()
        volunteers = (await self._db.execute(select(func.count(Volunteer.id)))).scalar_one()
        flagged = (await self._db.execute(
            select(func.count(Donation.id)).where(Donation.is_flagged == True)  # noqa
        )).scalar_one()

        return {
            "total_donations": total,
            "confirmed_deliveries": confirmed,
            "active_restaurants": restaurants,
            "active_ngos": ngos,
            "active_volunteers": volunteers,
            "flagged_donations": flagged,
            "success_rate": round((confirmed / max(total, 1)) * 100, 1),
            "total_meals": int(meals),
        }

    async def _retrieve_rag_context(self, query: str) -> str:
        """Retrieve relevant documents from knowledge base."""
        try:
            from app.rag.retrievers.semantic_retriever import SemanticRetriever
            retriever = SemanticRetriever()
            results = await retriever.retrieve(query, collection="knowledge_base", limit=3)
            return "\n---\n".join(r.get("content", "") for r in results if r.get("content"))
        except Exception:
            return ""

    async def _cache_conversation(
        self, session_id: str, user_message: str, assistant_response: str
    ) -> None:
        """Cache conversation history in Redis for multi-turn support."""
        try:
            from app.core.redis_client import get_cache_manager
            cache = get_cache_manager()
            key = f"admin_chat:{session_id}"
            existing = await cache.get(key) or []
            existing.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response},
            ])
            # Keep last 20 turns
            await cache.set(key, existing[-20:], ttl=3600)
        except Exception:
            pass

    def _generate_fallback_response(self, query: str, data: dict) -> str:
        """Simple keyword-based fallback if LLM is unavailable."""
        query_lower = query.lower()
        if any(w in query_lower for w in ["donation", "rescue", "total"]):
            return (f"We've processed {data['total_donations']} total donations with "
                    f"{data['confirmed_deliveries']} confirmed deliveries "
                    f"({data['success_rate']}% success rate). "
                    f"{data['total_meals']:,} meals have been saved total.")
        elif any(w in query_lower for w in ["ngo", "receiver"]):
            return f"There are {data['active_ngos']} active NGOs on the platform."
        elif any(w in query_lower for w in ["restaurant", "donor"]):
            return f"There are {data['active_restaurants']} registered restaurants."
        elif any(w in query_lower for w in ["fraud", "flag", "suspicious"]):
            return f"There are currently {data['flagged_donations']} flagged donations requiring review."
        else:
            return ("I'm your ResQAI admin assistant. I can help with platform statistics, "
                    "donation tracking, NGO management, and system monitoring. What would you like to know?")
