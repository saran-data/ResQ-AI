"""
ResQAI - Celery Application
Async task queue for AI processing, notifications, reports, and scheduled jobs.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery app
celery_app = Celery(
    "resqai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ai_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.report_tasks",
        "app.tasks.audit_tasks",
        "app.tasks.analytics_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # Fair task distribution
    task_routes={
        "app.tasks.ai_tasks.*": {"queue": "ai_tasks"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.tasks.report_tasks.*": {"queue": "default"},
        "app.tasks.analytics_tasks.*": {"queue": "default"},
    },
    # Scheduled tasks
    beat_schedule={
        "daily-analytics-snapshot": {
            "task": "app.tasks.analytics_tasks.compute_daily_snapshot",
            "schedule": crontab(hour=0, minute=5),  # Every day at 00:05
        },
        "weekly-demand-prediction": {
            "task": "app.tasks.ai_tasks.run_demand_prediction",
            "schedule": crontab(day_of_week=0, hour=1, minute=0),  # Weekly on Monday
        },
        "expire-old-donations": {
            "task": "app.tasks.ai_tasks.expire_stale_donations",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
        "update-restaurant-rankings": {
            "task": "app.tasks.analytics_tasks.update_restaurant_rankings",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
        },
    },
)
