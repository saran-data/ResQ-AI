"""
ResQAI - Base Agent
Abstract foundation that every AI agent inherits from.
Provides: model selection, retry logic, confidence scoring,
decision persistence, timing, and error recovery.
"""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_decision import AIDecision, AgentType, AgentDecisionStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentContext:
    """
    Shared context object passed through the agent pipeline.
    Carries the donation, food items, and accumulated results from previous agents.
    """

    def __init__(
        self,
        donation_id: str,
        db: AsyncSession,
        session_id: Optional[str] = None,
    ) -> None:
        self.donation_id = donation_id
        self.db = db
        self.session_id = session_id or str(uuid.uuid4())
        self.results: dict[str, Any] = {}   # Results from completed agents
        self.metadata: dict[str, Any] = {}  # Extra contextual data
        self.errors: list[dict] = []        # Accumulated non-fatal errors

    def set_result(self, agent: str, result: Any) -> None:
        self.results[agent] = result

    def get_result(self, agent: str) -> Optional[Any]:
        return self.results.get(agent)


class AgentResult:
    """
    Standardized output from any agent execution.
    Carries the payload, confidence, reasoning, and performance data.
    """

    def __init__(
        self,
        success: bool,
        data: Any,
        confidence: float = 1.0,
        reasoning: Optional[str] = None,
        model_used: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None,
        citations: Optional[list] = None,
    ) -> None:
        self.success = success
        self.data = data
        self.confidence = max(0.0, min(1.0, confidence))  # Clamp 0-1
        self.reasoning = reasoning
        self.model_used = model_used
        self.latency_ms = latency_ms
        self.tokens_used = tokens_used
        self.cost_usd = cost_usd
        self.citations = citations or []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "citations": self.citations,
            "timestamp": self.timestamp,
        }

    @classmethod
    def failure(cls, error: str, model: Optional[str] = None) -> "AgentResult":
        return cls(success=False, data={"error": error}, confidence=0.0, model_used=model)


class BaseAgent(ABC):
    """
    Abstract base agent.
    
    Subclasses must implement:
    - agent_type property
    - execute(context, **kwargs) method
    
    Provides out-of-the-box:
    - Configurable retry with exponential backoff
    - Decision persistence to ai_decisions table
    - Confidence threshold checking
    - Performance timing
    - Structured logging with agent context
    """

    # --- Configure per agent subclass ---
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 2.0
    CONFIDENCE_THRESHOLD: float = 0.6
    TIMEOUT_SECONDS: int = 60

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logger = get_logger(f"agent.{self.agent_type.value}")

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the AgentType enum value for this agent."""
        ...

    @abstractmethod
    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Core agent logic. Subclasses implement this.
        
        Args:
            context: Shared pipeline context
            **kwargs: Agent-specific parameters

        Returns:
            AgentResult with data, confidence, and reasoning
        """
        ...

    # -------------------------------------------------------
    # Public API
    # -------------------------------------------------------
    async def run(
        self,
        context: AgentContext,
        task_name: Optional[str] = None,
        **kwargs,
    ) -> AgentResult:
        """
        Execute the agent with full retry, timing, and persistence.
        This is the only entry point called by the Orchestrator.

        Args:
            context: Pipeline context
            task_name: Optional task label for logging
            **kwargs: Forwarded to execute()

        Returns:
            AgentResult (success or failure after all retries)
        """
        decision_id = await self._create_decision_record(context, task_name)
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                self._logger.info(
                    f"Agent executing",
                    donation_id=context.donation_id,
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                )

                if attempt > 0:
                    await self._update_decision_status(
                        decision_id, AgentDecisionStatus.RETRYING, retry_count=attempt
                    )

                result = await self.execute(context, **kwargs)
                latency_ms = int((time.monotonic() - start_time) * 1000)
                result.latency_ms = latency_ms

                if result.success:
                    # Confidence gate — retry if below threshold
                    if result.confidence < self.CONFIDENCE_THRESHOLD and attempt < self.MAX_RETRIES - 1:
                        self._logger.warning(
                            f"Low confidence {result.confidence:.2f}, retrying",
                            threshold=self.CONFIDENCE_THRESHOLD,
                        )
                        last_error = Exception(f"Confidence {result.confidence:.2f} below threshold")
                        await self._backoff(attempt)
                        continue

                    await self._persist_success(decision_id, result, context)
                    self._logger.info(
                        f"Agent completed",
                        confidence=result.confidence,
                        latency_ms=latency_ms,
                        model=result.model_used,
                    )
                    return result

                # Execution returned failure — retry
                last_error = Exception(result.data.get("error", "Unknown agent failure"))
                await self._backoff(attempt)

            except Exception as exc:
                last_error = exc
                self._logger.warning(
                    f"Agent attempt {attempt + 1} failed: {exc}",
                    exc_info=settings.is_development,
                )
                await self._backoff(attempt)

        # All retries exhausted
        latency_ms = int((time.monotonic() - start_time) * 1000)
        error_msg = str(last_error) if last_error else "Max retries exceeded"
        failure_result = AgentResult.failure(error_msg)
        failure_result.latency_ms = latency_ms

        await self._persist_failure(decision_id, error_msg, latency_ms)
        self._logger.error(
            f"Agent failed after {self.MAX_RETRIES} retries",
            error=error_msg,
            latency_ms=latency_ms,
        )

        return failure_result

    # -------------------------------------------------------
    # Decision Persistence
    # -------------------------------------------------------
    async def _create_decision_record(
        self, context: AgentContext, task_name: Optional[str]
    ) -> str:
        """Create an ai_decisions row and return its ID."""
        decision = AIDecision(
            donation_id=uuid.UUID(context.donation_id) if context.donation_id else None,
            session_id=context.session_id,
            agent_type=self.agent_type,
            task_name=task_name or self.agent_type.value,
            status=AgentDecisionStatus.RUNNING,
            model_used="pending",
        )
        self._db.add(decision)
        await self._db.flush()
        return str(decision.id)

    async def _persist_success(
        self, decision_id: str, result: AgentResult, context: AgentContext
    ) -> None:
        """Update the decision record with successful output."""
        from sqlalchemy import update
        await self._db.execute(
            update(AIDecision)
            .where(AIDecision.id == uuid.UUID(decision_id))
            .values(
                status=AgentDecisionStatus.SUCCESS,
                model_used=result.model_used or "unknown",
                output_data=result.data if isinstance(result.data, dict) else {"result": str(result.data)},
                confidence_score=result.confidence,
                reasoning=result.reasoning,
                explanation=result.reasoning,
                citations=result.citations,
                latency_ms=result.latency_ms,
                total_tokens=result.tokens_used,
                cost_usd=result.cost_usd,
                retry_count=0,
            )
        )

    async def _persist_failure(
        self, decision_id: str, error_msg: str, latency_ms: int
    ) -> None:
        """Update the decision record with failure details."""
        from sqlalchemy import update
        await self._db.execute(
            update(AIDecision)
            .where(AIDecision.id == uuid.UUID(decision_id))
            .values(
                status=AgentDecisionStatus.FAILED,
                model_used="failed",
                error_message=error_msg,
                latency_ms=latency_ms,
                retry_count=self.MAX_RETRIES,
            )
        )

    async def _update_decision_status(
        self, decision_id: str, new_status: AgentDecisionStatus, retry_count: int = 0
    ) -> None:
        from sqlalchemy import update
        await self._db.execute(
            update(AIDecision)
            .where(AIDecision.id == uuid.UUID(decision_id))
            .values(status=new_status, retry_count=retry_count)
        )

    async def _backoff(self, attempt: int) -> None:
        """Exponential backoff before retry."""
        import asyncio
        delay = self.RETRY_DELAY_SECONDS * (2 ** attempt)
        await asyncio.sleep(min(delay, 30))  # Cap at 30 seconds
