"""
ResQAI - Analytics Models
Pre-aggregated KPI snapshots and daily metrics for fast dashboard queries.
Populated by the Analytics Agent via scheduled Celery tasks.
"""

import enum
import uuid
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class SnapshotType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class AnalyticsSnapshot(BaseModel):
    """
    System-wide KPI snapshot for a given time period.
    Pre-aggregated to avoid expensive real-time queries on the dashboard.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        Index("idx_analytics_snapshots_date", "snapshot_date"),
        Index("idx_analytics_snapshots_type", "snapshot_type"),
        {"schema": "resqai"},
    )

    snapshot_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    snapshot_type: Mapped[SnapshotType] = mapped_column(
        Enum(SnapshotType, name="snapshot_type", schema="resqai"),
        nullable=False,
        default=SnapshotType.DAILY,
    )

    # ---- Volume KPIs ----
    total_donations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_meals_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ---- Environmental Impact ----
    carbon_saved_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    water_saved_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    land_saved_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    methane_prevented_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Operational KPIs ----
    avg_pickup_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_delivery_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_total_time_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    on_time_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ---- Entity Counts ----
    active_restaurants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_ngos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_volunteers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_restaurants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_ngos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ---- AI Agent Stats ----
    ai_decisions_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_accuracy_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fraud_cases_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ---- Detailed breakdowns (stored as JSON for flexibility) ----
    by_city: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    by_food_category: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    by_ngo_type: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    by_restaurant_type: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    top_restaurants: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    top_ngos: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    top_volunteers: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)


class DailyKPI(BaseModel):
    """
    Per-entity daily KPI tracking for leaderboards and trend analysis.
    One row per entity per day.
    """

    __tablename__ = "daily_kpis"
    __table_args__ = (
        Index("idx_daily_kpis_date", "kpi_date"),
        Index("idx_daily_kpis_entity", "entity_type", "entity_id"),
        {"schema": "resqai"},
    )

    kpi_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # restaurant/ngo/volunteer
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    donations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meals_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    carbon_saved_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    deliveries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
