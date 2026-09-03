"""ResQAI - Notification Celery Tasks"""
from celery import shared_task
from loguru import logger


@shared_task(name="app.tasks.notification_tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, user_id: str, email: str, token: str) -> None:
    import asyncio
    try:
        async def _run():
            from app.notifications.email_sender import EmailSender
            sender = EmailSender()
            await sender.send_verification_email(email, token)
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Verification email failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.notification_tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, user_id: str, email: str, token: str) -> None:
    import asyncio
    try:
        async def _run():
            from app.notifications.email_sender import EmailSender
            sender = EmailSender()
            await sender.send_password_reset_email(email, token)
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="app.tasks.notification_tasks.send_donation_notification", bind=True, max_retries=3)
def send_donation_notification(self, donation_id: str, notification_type: str) -> None:
    import asyncio
    try:
        async def _run():
            from app.orchestrator.orchestrator import AIOrchestrator
            from app.core.database import get_db_context
            async with get_db_context() as db:
                orchestrator = AIOrchestrator(db)
                await orchestrator.run_notification_agent(donation_id, notification_type)
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
