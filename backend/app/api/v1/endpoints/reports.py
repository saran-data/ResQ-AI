"""ResQAI - Reports API Endpoints"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/generate", summary="Request a report generation")
async def generate_report(
    report_type: str,
    format: str = Query(default="pdf", pattern="^(pdf|csv|excel)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.report import Report, ReportType, ReportFormat, ReportStatus
    from app.repositories.base import BaseRepository
    repo = BaseRepository(Report, db)
    report = await repo.create({
        "requested_by": current_user.id,
        "title": f"{report_type.replace('_', ' ').title()} Report",
        "type": ReportType(report_type),
        "format": ReportFormat(format),
        "date_from": date_from,
        "date_to": date_to,
        "status": ReportStatus.QUEUED,
    })
    try:
        from app.tasks.report_tasks import generate_report_task
        generate_report_task.delay(str(report.id))
    except Exception:
        pass
    return ApiResponse.ok(data={"report_id": str(report.id), "status": "queued"})

@router.get("", summary="List my reports")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.report import Report
    repo = BaseRepository(Report, db)
    reports, total = await repo.get_all(
        skip=(page - 1) * page_size, limit=page_size,
        filters={"requested_by": current_user.id},
    )
    return PaginatedResponse.ok(
        data=[r.to_dict() for r in reports], page=page, page_size=page_size, total=total
    )

@router.get("/{report_id}", summary="Get report details")
async def get_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.report import Report
    repo = BaseRepository(Report, db)
    report = await repo.get_or_raise(report_id)
    return ApiResponse.ok(data=report.to_dict())
