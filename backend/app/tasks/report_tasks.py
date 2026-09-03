"""ResQAI - Report Generation Celery Tasks"""
from celery import shared_task
from loguru import logger


@shared_task(name="app.tasks.report_tasks.generate_report_task", bind=True, max_retries=2)
def generate_report_task(self, report_id: str) -> None:
    import asyncio
    from datetime import datetime, timezone
    async def _run():
        from app.core.database import get_db_context
        from app.models.report import Report, ReportStatus, ReportFormat
        from app.repositories.base import BaseRepository
        import io, csv, json
        async with get_db_context() as db:
            repo = BaseRepository(Report, db)
            report = await repo.get_or_raise(report_id)
            await repo.update(report_id, {"status": ReportStatus.PROCESSING, "progress_percent": 10})
            try:
                # Build report content based on type/format
                content = await _build_report_content(db, report)
                # Upload to Cloudinary
                try:
                    import cloudinary.uploader
                    result = cloudinary.uploader.upload(
                        content,
                        public_id=f"resqai/reports/{report_id}",
                        resource_type="raw",
                    )
                    file_url = result["secure_url"]
                except Exception:
                    file_url = None
                await repo.update(report_id, {
                    "status": ReportStatus.COMPLETED,
                    "progress_percent": 100,
                    "file_url": file_url,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"Report {report_id} generated")
            except Exception as e:
                await repo.update(report_id, {"status": ReportStatus.FAILED, "error_message": str(e)})
    asyncio.run(_run())


async def _build_report_content(db, report) -> bytes:
    """Build report content as bytes based on format."""
    import csv, io, json
    from app.models.donation import Donation
    from sqlalchemy import select
    result = await db.execute(select(Donation).limit(1000))
    donations = result.scalars().all()
    if report.format.value == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "Status", "Servings", "Weight KG", "Created At"])
        for d in donations:
            writer.writerow([str(d.id), d.status, d.total_servings, d.total_weight_kg, d.created_at])
        return buf.getvalue().encode()
    else:
        data = [{"id": str(d.id), "status": d.status, "servings": d.total_servings} for d in donations]
        return json.dumps(data, default=str).encode()
