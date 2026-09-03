"""
ResQAI - AI Decision Model
Full audit trail for every AI agent decision: input, output, confidence, model, latency.
Supports Explainable AI and performance analysis.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .donation import Donation


class AgentType(str, enum.Enum):
    FOOD_ANALYSIS = "food_analysis"
    NGO_MATCHING = "ngo_matching"
    ROUTE_OPTIMIZATION = "route_optimization"
    FOOD_SAFETY = "food_safety"
    DEMAND_PREDICTION = "demand_prediction"
    NOTIFICATION = "notification"
    VOLUNTEER = "volunteer"
    ANALYTICS = "analytics"
    FRAUD_DETECTION = "fraud_detection"
    ADMIN_ASSISTANT = "admin_assistant"
    ORCHESTRATOR = "orchestrator"


class AgentDecisionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class AIDecision(BaseModel):
    """
    Complete record of an AI agent's decision for a specific donation.
    Used for:
    - Explainability (why did the AI choose X)
    - Performance monitoring (latency, confidence trends)
    - Debugging and audit
    - Model comparison and A/B testing
    """

    __tablename__ = "ai_decisions"
    __table_args__ = (
        Index("idx_ai_decisions_donation_id", "donation_id"),
        Index("idx_ai_decisions_agent_type", "agent_type"),
        Index("idx_ai_decisions_status", "status"),
        Index("idx_ai_decisions_model_used", "model_used"),
        Index("idx_ai_decisions_created_at", "created_at"),
        {"schema": "resqai"},
    )

    # ---- Context ----
    donation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.donations.id", ondelete="CASCADE"),
        nullable=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ---- Agent ----
    agent_type: Mapped[AgentType] = mapped_column(
        Enum(AgentType, name="agent_type", schema="resqai"),
        nullable=False,
        index=True,
    )
    task_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[AgentDecisionStatus] = mapped_column(
        Enum(AgentDecisionStatus, name="agent_decision_status", schema="resqai"),
        nullable=False,
        default=AgentDecisionStatus.PENDING,
        index=True,
    )

    # ---- Model ----
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    model_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- I/O ----
    input_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Raw input sent to the model (sanitized)"
    )
    output_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Full model output including reasoning"
    )
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Quality ----
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Human-readable explanation for Explainable AI"
    )
    citations: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, comment="RAG source citations"
    )

    # ---- Performance ----
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ---- Human Override ----
    was_overridden: Mapped[bool] = mapped_column(default=False, nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overridden_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ---- Relationships ----
    donation: Mapped[Optional["Donation"]] = relationship(
        "Donation", back_populates="ai_decisions"
    )
