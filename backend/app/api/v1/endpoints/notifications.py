"""ResQAI - Notifications API Endpoints"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("", summary="Get my notifications")
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.notification import Notification
    repo = BaseRepository(Notification, db)
    filters = {"user_id": current_user.id}
    if unread_only:
        filters["is_read"] = False
    notifications, total = await repo.get_all(
        skip=(page - 1) * page_size, limit=page_size, filters=filters
    )
    return PaginatedResponse.ok(
        data=[n.to_dict() for n in notifications], page=page, page_size=page_size, total=total
    )

@router.patch("/{notification_id}/read", summary="Mark notification as read")
async def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.base import BaseRepository
    from app.models.notification import Notification
    from datetime import datetime, timezone
    repo = BaseRepository(Notification, db)
    await repo.update(notification_id, {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()})
    return MessageResponse(message="Marked as read")

@router.patch("/read-all", summary="Mark all notifications as read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update
    from app.models.notification import Notification
    from datetime import datetime, timezone
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa
        .values(is_read=True, read_at=datetime.now(timezone.utc).isoformat())
    )
    return MessageResponse(message="All notifications marked as read")
