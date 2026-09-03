"""
ResQAI - Report Model
Generated reports (PDF, CSV, Excel) requested by users or scheduled by the system.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class ReportType(str, enum.Enum):
    DONATION_SUMMARY = "donation_summary"
    IMPACT_REPORT = "impact_report"
    NGO_ACTIVITY = "ngo_activity"
    RESTAURANT_CONTRIBUTION = "restaurant_contribution"
    VOLUNTEER_PERFORMANCE = "volunteer_performance"
    FOOD_SAFETY_AUDIT = "food_safety_audit"
    FRAUD_ANALYSIS = "fraud_analysis"
    AI_PERFORMANCE = "ai_performance"
    CARBON_FOOTPRINT = "carbon_footprint"
    FINANCIAL_SUMMARY = "financial_summary"
    WEEKLY_DIGEST = "weekly_digest"
    MONTHLY_DIGEST = "monthly_digest"
    CUSTOM = "custom"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"


class ReportStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class Report(BaseModel):
    """
    Generated report metadata.
    The actual file is stored in Cloudinary and linked via file_url.
    Report generation is handled by Celery workers.
    """

    __tablename__ = "reports"
    __table_args__ = (
        Index("idx_reports_requested_by", "requested_by"),
        Index("idx_reports_type", "type"),
        Index("idx_reports_status", "status"),
        Index("idx_reports_created_at", "created_at"),
        {"schema": "resqai"},
    )

    # ---- Requester ----
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---- Classification ----
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type", schema="resqai"),
        nullable=False,
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format", schema="resqai"),
        nullable=False,
        default=ReportFormat.PDF,
    )

    # ---- Parameters ----
    parameters: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Filter params: date_from, date_to, entity_ids, etc."
    )
    date_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_to: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ---- Status ----
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", schema="resqai"),
        nullable=False,
        default=ReportStatus.QUEUED,
        index=True,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Output ----
    file_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cloudinary_public_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Lifecycle ----
    completed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
