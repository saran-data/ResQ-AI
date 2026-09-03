"""
ResQAI - SQLAlchemy Models Registry
Import all models here so Alembic can detect them for migrations.
"""

from .user import User, UserRole, UserStatus
from .restaurant import Restaurant, RestaurantStatus
from .ngo import NGO, NGOStatus, NGOType
from .volunteer import Volunteer, VolunteerStatus
from .donation import Donation, DonationStatus
from .food_item import FoodItem, FoodCategory, FoodSafetyStatus
from .delivery import Delivery, DeliveryStatus
from .vehicle import Vehicle, VehicleType
from .route import Route, RouteStatus
from .notification import Notification, NotificationChannel, NotificationType
from .analytics import AnalyticsSnapshot, DailyKPI
from .ai_decision import AIDecision, AgentType
from .audit_log import AuditLog
from .knowledge_base import KnowledgeDocument, KnowledgeChunk
from .report import Report, ReportType

__all__ = [
    "User", "UserRole", "UserStatus",
    "Restaurant", "RestaurantStatus",
    "NGO", "NGOStatus", "NGOType",
    "Volunteer", "VolunteerStatus",
    "Donation", "DonationStatus",
    "FoodItem", "FoodCategory", "FoodSafetyStatus",
    "Delivery", "DeliveryStatus",
    "Vehicle", "VehicleType",
    "Route", "RouteStatus",
    "Notification", "NotificationChannel", "NotificationType",
    "AnalyticsSnapshot", "DailyKPI",
    "AIDecision", "AgentType",
    "AuditLog",
    "KnowledgeDocument", "KnowledgeChunk",
    "Report", "ReportType",
]
