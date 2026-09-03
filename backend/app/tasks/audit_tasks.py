"""ResQAI - Audit Log Celery Tasks"""
from celery import shared_task


@shared_task(name="app.tasks.audit_tasks.persist_audit_log")
def persist_audit_log(
    user_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str,
    request_id: str,
) -> None:
    import asyncio
    async def _run():
        from app.core.database import get_db_context
        from app.models.audit_log import AuditLog
        async with get_db_context() as db:
            log = AuditLog(
                user_id=user_id if user_id != "anonymous" else None,
                http_method=method,
                http_path=path,
                http_status=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                request_id=request_id,
                resource_type=path.split("/")[3] if len(path.split("/")) > 3 else "unknown",
                action=f"{method}:{path}",
            )
            db.add(log)
    asyncio.run(_run())
