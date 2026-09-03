"""
ResQAI - Vehicle Model
Tracks volunteer vehicles used for food pickup and delivery.
"""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .volunteer import Volunteer


class VehicleType(str, enum.Enum):
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"
    AUTO_RICKSHAW = "auto_rickshaw"
    CAR = "car"
    VAN = "van"
    TEMPO = "tempo"
    TRUCK = "truck"
    REFRIGERATED_VAN = "refrigerated_van"
    ELECTRIC_BIKE = "electric_bike"
    ELECTRIC_CAR = "electric_car"


class Vehicle(BaseModel):
    """
    Vehicle registered to a volunteer.
    Capacity and refrigeration availability influence Route Optimization Agent decisions.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        Index("idx_vehicles_volunteer_id", "volunteer_id"),
        Index("idx_vehicles_type", "type"),
        {"schema": "resqai"},
    )

    volunteer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resqai.volunteers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    type: Mapped[VehicleType] = mapped_column(
        Enum(VehicleType, name="vehicle_type", schema="resqai"),
        nullable=False,
    )

    registration_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ---- Capacity ----
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    capacity_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_boxes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ---- Features ----
    has_refrigeration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refrigeration_temp_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    refrigeration_temp_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_food_grade: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ---- Insurance & Compliance ----
    insurance_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_expiry: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pollution_cert_expiry: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ---- Relationships ----
    volunteer: Mapped["Volunteer"] = relationship("Volunteer", back_populates="vehicle")
