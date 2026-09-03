"""ResQAI - AI Agents API Endpoints (manual triggers and status)"""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse
from app.services.rbac_service import get_admin_user, get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/trigger/{agent_type}/{donation_id}", summary="Manually trigger an AI agent")
async def trigger_agent(
    agent_type: str,
    donation_id: UUID,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin endpoint to manually re-trigger an AI agent for a donation."""
    try:
        from app.tasks.ai_tasks import run_agent_task
        run_agent_task.delay(agent_type, str(donation_id))
        return ApiResponse.ok(data={"queued": True, "agent": agent_type, "donation": str(donation_id)})
    except Exception as e:
        return ApiResponse.ok(data={"queued": False, "error": str(e)})

@router.get("/decisions/{donation_id}", summary="Get AI decisions for a donation")
async def get_ai_decisions(
    donation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.ai_decision import AIDecision
    result = await db.execute(
        select(AIDecision)
        .where(AIDecision.donation_id == donation_id)
        .order_by(AIDecision.created_at.asc())
    )
    decisions = result.scalars().all()
    return ApiResponse.ok(data=[{
        "id": str(d.id),
        "agent": d.agent_type,
        "status": d.status,
        "model": d.model_used,
        "confidence": d.confidence_score,
        "reasoning": d.reasoning,
        "latency_ms": d.latency_ms,
    } for d in decisions])

@router.get("/status", summary="Get all agent statuses")
async def get_agent_statuses(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, select
    from app.models.ai_decision import AIDecision, AgentType
    results = []
    for agent in AgentType:
        count = (await db.execute(
            select(func.count(AIDecision.id)).where(AIDecision.agent_type == agent)
        )).scalar_one()
        avg_conf = (await db.execute(
            select(func.avg(AIDecision.confidence_score)).where(AIDecision.agent_type == agent)
        )).scalar_one()
        results.append({
            "agent": agent.value,
            "total_decisions": count,
            "avg_confidence": round(avg_conf or 0, 3),
        })
    return ApiResponse.ok(data=results)
