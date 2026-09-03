"""
ResQAI - AI Celery Tasks
Background tasks that trigger AI agent processing.
Each task is a thin wrapper that loads the orchestrator and dispatches to the right agent.
"""

from celery import shared_task
from loguru import logger


@shared_task(
    name="app.tasks.ai_tasks.analyze_food_images_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="ai_tasks",
)
def analyze_food_images_task(self, donation_id: str, image_urls: list) -> dict:
    """Run Food Analysis Agent on uploaded images."""
    import asyncio
    try:
        async def _run():
            from app.orchestrator.orchestrator import AIOrchestrator
            from app.core.database import get_db_context
            async with get_db_context() as db:
                orchestrator = AIOrchestrator(db)
                return await orchestrator.run_food_analysis(donation_id, image_urls)
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Food analysis task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.ai_tasks.run_ngo_matching",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="ai_tasks",
)
def run_ngo_matching(self, donation_id: str) -> dict:
    """Run NGO Matching Agent after food safety check passes."""
    import asyncio
    try:
        async def _run():
            from app.orchestrator.orchestrator import AIOrchestrator
            from app.core.database import get_db_context
            async with get_db_context() as db:
                orchestrator = AIOrchestrator(db)
                return await orchestrator.run_ngo_matching(donation_id)
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"NGO matching task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.ai_tasks.route_optimization_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue="ai_tasks",
)
def route_optimization_task(self, donation_id: str) -> dict:
    """Run Route Optimization Agent after NGO is matched."""
    import asyncio
    try:
        async def _run():
            from app.orchestrator.orchestrator import AIOrchestrator
            from app.core.database import get_db_context
            async with get_db_context() as db:
                orchestrator = AIOrchestrator(db)
                return await orchestrator.run_route_optimization(donation_id)
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Route optimization task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    name="app.tasks.ai_tasks.run_agent_task",
    bind=True,
    max_retries=2,
    queue="ai_tasks",
)
def run_agent_task(self, agent_type: str, donation_id: str) -> dict:
    """Generic task to run any named agent."""
    import asyncio
    try:
        async def _run():
            from app.orchestrator.orchestrator import AIOrchestrator
            from app.core.database import get_db_context
            async with get_db_context() as db:
                orchestrator = AIOrchestrator(db)
                return await orchestrator.dispatch_agent(agent_type, {"donation_id": donation_id})
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(name="app.tasks.ai_tasks.run_demand_prediction")
def run_demand_prediction() -> None:
    """Weekly scheduled demand prediction for all active NGOs."""
    import asyncio
    async def _run():
        from app.orchestrator.orchestrator import AIOrchestrator
        from app.core.database import get_db_context
        async with get_db_context() as db:
            orchestrator = AIOrchestrator(db)
            await orchestrator.run_demand_prediction_all()
    asyncio.run(_run())


@shared_task(name="app.tasks.ai_tasks.expire_stale_donations")
def expire_stale_donations() -> None:
    """Mark expired donations that passed their pickup window."""
    import asyncio
    from datetime import datetime, timezone
    async def _run():
        from app.core.database import get_db_context
        from app.models.donation import Donation, DonationStatus
        from sqlalchemy import update, select
        async with get_db_context() as db:
            now = datetime.now(timezone.utc).isoformat()
            active_statuses = [
                DonationStatus.DRAFT, DonationStatus.PENDING_ANALYSIS,
                DonationStatus.ANALYZED, DonationStatus.MATCHING, DonationStatus.MATCHED,
            ]
            result = await db.execute(
                select(Donation).where(
                    Donation.status.in_(active_statuses),
                    Donation.expires_at < now,
                )
            )
            expired = result.scalars().all()
            for donation in expired:
                donation.status = DonationStatus.EXPIRED
            await db.commit()
            if expired:
                logger.info(f"Expired {len(expired)} stale donations")
    asyncio.run(_run())
