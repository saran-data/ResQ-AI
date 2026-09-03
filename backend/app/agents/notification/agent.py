"""
ResQAI - Notification Agent
Uses Mistral (lightweight) to generate personalized notification content
and dispatches via Email, SMS, WhatsApp, and Push simultaneously.
"""

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.base_agent import BaseAgent, AgentContext, AgentResult
from app.orchestrator.llm_client import LLMClient
from app.orchestrator.model_registry import ModelID
from app.models.ai_decision import AgentType
from app.models.donation import Donation
from app.models.ngo import NGO
from app.models.notification import Notification, NotificationChannel, NotificationType, NotificationStatus
from app.core.logging import get_logger

logger = get_logger(__name__)

NOTIFICATION_SYSTEM = """You are a notification content writer for ResQAI food rescue platform.
Generate concise, warm, and actionable notification messages.

Respond with JSON:
{
  "email_subject": "<subject line>",
  "email_body": "<full HTML email body>",
  "sms_message": "<max 160 chars>",
  "whatsapp_message": "<formatted WhatsApp message with emojis>",
  "push_title": "<max 50 chars>",
  "push_body": "<max 100 chars>"
}
"""


class NotificationAgent(BaseAgent):
    """
    AI Agent: Notification
    Primary model: Mistral Small (fast, lightweight)

    Generates and dispatches multi-channel notifications for donation events.
    Channels: Email, SMS, WhatsApp, Push notifications, In-app.
    """

    MAX_RETRIES = 3
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._llm = LLMClient()

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NOTIFICATION

    async def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """Generate and send notifications for a donation event."""
        notification_type: str = kwargs.get("notification_type", "donation_matched")

        donation_result = await self._db.execute(
            select(Donation).where(Donation.id == context.donation_id)
        )
        donation = donation_result.scalar_one_or_none()
        if not donation:
            return AgentResult.failure("Donation not found")

        # Generate notification content using Mistral
        content = await self._generate_content(donation, notification_type)

        # Determine recipients based on notification type
        recipients = await self._get_recipients(donation, notification_type)

        notifications_sent = []
        for recipient in recipients:
            for channel in recipient.get("channels", [NotificationChannel.IN_APP]):
                notif = await self._create_notification(
                    donation=donation,
                    recipient=recipient,
                    channel=channel,
                    notification_type=notification_type,
                    content=content,
                )
                notifications_sent.append(notif)

        # Dispatch via actual channels (async, fire-and-forget per channel)
        for notif in notifications_sent:
            await self._dispatch_notification(notif)

        return AgentResult(
            success=True,
            data={
                "notifications_sent": len(notifications_sent),
                "channels": [n.channel.value for n in notifications_sent],
                "notification_type": notification_type,
            },
            confidence=0.9,
            model_used=ModelID.MISTRAL_SMALL.value,
            reasoning=f"Sent {len(notifications_sent)} notifications via {set(n.channel.value for n in notifications_sent)}",
        )

    async def _generate_content(self, donation: Donation, notification_type: str) -> dict:
        """Use Mistral to generate personalized notification content."""
        ngo_name = "the NGO"
        if donation.matched_ngo_id:
            ngo_r = await self._db.execute(select(NGO).where(NGO.id == donation.matched_ngo_id))
            ngo = ngo_r.scalar_one_or_none()
            if ngo:
                ngo_name = ngo.name

        event_descriptions = {
            "donation_matched": f"A food donation of {donation.total_servings} servings has been matched to {ngo_name}.",
            "pickup_scheduled": f"Pickup scheduled for donation of {donation.total_servings} servings.",
            "delivery_started": f"Volunteer is on the way to pick up {donation.total_servings} servings.",
            "delivery_completed": f"Food delivery of {donation.total_servings} servings completed successfully!",
            "safety_rejected": "A food donation was rejected due to safety concerns.",
            "otp_generated": f"OTP for pickup verification: {donation.otp or '######'}",
            "volunteer_assigned": "A volunteer has been assigned to your donation.",
        }

        event_desc = event_descriptions.get(notification_type, f"Donation update: {notification_type}")

        try:
            response = await self._llm.complete(
                model=ModelID.MISTRAL_SMALL,
                system_prompt=NOTIFICATION_SYSTEM,
                user_prompt=f"""Generate notification for this event:
Event: {event_desc}
Platform: ResQAI Food Rescue
Donation ID: {str(donation.id)[:8]}
Total Servings: {donation.total_servings}
NGO: {ngo_name}
Tone: warm, brief, action-oriented""",
                temperature=0.3,
                max_tokens=512,
                json_mode=True,
            )
            return json.loads(response.content)
        except Exception as e:
            logger.warning(f"Notification content generation failed: {e}")
            return self._default_content(notification_type, donation, ngo_name)

    def _default_content(self, notification_type: str, donation: Donation, ngo_name: str) -> dict:
        """Fallback notification content templates."""
        templates = {
            "donation_matched": {
                "email_subject": "Your food donation has been matched!",
                "sms_message": f"ResQAI: Your donation matched with {ngo_name}. {donation.total_servings} servings will reach those in need.",
                "whatsapp_message": f"🎉 Your food donation has been matched!\n\n📍 NGO: {ngo_name}\n🍽 Servings: {donation.total_servings}\n\nThank you for rescuing food! 🙏",
                "push_title": "Donation Matched!",
                "push_body": f"{donation.total_servings} servings matched to {ngo_name}",
            },
            "delivery_completed": {
                "email_subject": "Food delivered successfully!",
                "sms_message": f"ResQAI: Food delivery confirmed! {donation.total_servings} meals reached {ngo_name}.",
                "whatsapp_message": f"✅ Delivery Complete!\n\n🍽 {donation.total_servings} meals delivered to {ngo_name}\n💚 Thank you for making a difference!",
                "push_title": "Delivery Complete!",
                "push_body": "Food successfully delivered",
            },
        }
        return templates.get(notification_type, {
            "email_subject": "ResQAI Update",
            "sms_message": "ResQAI: Your donation status has been updated.",
            "whatsapp_message": "📱 ResQAI donation update. Check the app for details.",
            "push_title": "Donation Update",
            "push_body": "Check app for details",
        })

    async def _get_recipients(self, donation: Donation, notification_type: str) -> list:
        """Determine who should receive notifications for this event."""
        from sqlalchemy import select
        from app.models.user import User
        from app.models.restaurant import Restaurant

        recipients = []

        # Restaurant owner always receives notifications
        rest_result = await self._db.execute(
            select(Restaurant).where(Restaurant.id == donation.restaurant_id)
        )
        restaurant = rest_result.scalar_one_or_none()
        if restaurant:
            owner_result = await self._db.execute(
                select(User).where(User.id == restaurant.owner_id)
            )
            owner = owner_result.scalar_one_or_none()
            if owner:
                prefs = owner.notification_preferences or {}
                channels = []
                if prefs.get("email", True) and owner.email:
                    channels.append(NotificationChannel.EMAIL)
                if prefs.get("sms", True) and owner.phone:
                    channels.append(NotificationChannel.SMS)
                if prefs.get("push", True):
                    channels.append(NotificationChannel.PUSH)
                channels.append(NotificationChannel.IN_APP)
                recipients.append({
                    "user_id": owner.id,
                    "email": owner.email,
                    "phone": owner.phone,
                    "channels": channels,
                    "role": "restaurant",
                })

        # NGO manager receives for matching/delivery events
        if donation.matched_ngo_id and notification_type in (
            "donation_matched", "pickup_scheduled", "delivery_completed", "delivery_started"
        ):
            ngo_result = await self._db.execute(select(NGO).where(NGO.id == donation.matched_ngo_id))
            ngo = ngo_result.scalar_one_or_none()
            if ngo:
                mgr_result = await self._db.execute(select(User).where(User.id == ngo.manager_id))
                mgr = mgr_result.scalar_one_or_none()
                if mgr:
                    recipients.append({
                        "user_id": mgr.id,
                        "email": mgr.email,
                        "phone": mgr.phone,
                        "channels": [NotificationChannel.EMAIL, NotificationChannel.PUSH, NotificationChannel.IN_APP],
                        "role": "ngo",
                    })

        return recipients

    async def _create_notification(
        self, donation: Donation, recipient: dict, channel: NotificationChannel,
        notification_type: str, content: dict
    ) -> Notification:
        """Persist notification record to database."""
        notif_type_map = {
            "donation_matched": NotificationType.DONATION_MATCHED,
            "pickup_scheduled": NotificationType.PICKUP_SCHEDULED,
            "delivery_started": NotificationType.DELIVERY_STARTED,
            "delivery_completed": NotificationType.DELIVERY_COMPLETED,
            "otp_generated": NotificationType.OTP_GENERATED,
            "volunteer_assigned": NotificationType.VOLUNTEER_ASSIGNED,
        }

        notif = Notification(
            user_id=recipient.get("user_id"),
            donation_id=donation.id,
            type=notif_type_map.get(notification_type, NotificationType.SYSTEM_ALERT),
            channel=channel,
            title=content.get("push_title", "ResQAI Update"),
            message=content.get("sms_message", "Donation status updated"),
            recipient_email=recipient.get("email") if channel == NotificationChannel.EMAIL else None,
            recipient_phone=recipient.get("phone") if channel in (NotificationChannel.SMS, NotificationChannel.WHATSAPP) else None,
            status=NotificationStatus.QUEUED,
            data=content,
        )
        self._db.add(notif)
        await self._db.flush()
        return notif

    async def _dispatch_notification(self, notif: Notification) -> None:
        """Send notification via the appropriate channel."""
        try:
            if notif.channel == NotificationChannel.EMAIL:
                await self._send_email(notif)
            elif notif.channel == NotificationChannel.SMS:
                await self._send_sms(notif)
            elif notif.channel == NotificationChannel.WHATSAPP:
                await self._send_whatsapp(notif)
            elif notif.channel in (NotificationChannel.PUSH, NotificationChannel.IN_APP):
                await self._send_push(notif)
        except Exception as e:
            logger.warning(f"Notification dispatch failed [{notif.channel}]: {e}")

    async def _send_email(self, notif: Notification) -> None:
        if not notif.recipient_email:
            return
        from app.notifications.email_sender import EmailSender
        sender = EmailSender()
        content = notif.data or {}
        await sender.send(
            to=notif.recipient_email,
            subject=content.get("email_subject", notif.title),
            html_body=content.get("email_body", f"<p>{notif.message}</p>"),
        )
        from sqlalchemy import update
        from datetime import datetime, timezone
        await self._db.execute(
            update(Notification).where(Notification.id == notif.id)
            .values(status=NotificationStatus.SENT, sent_at=datetime.now(timezone.utc).isoformat())
        )

    async def _send_sms(self, notif: Notification) -> None:
        if not notif.recipient_phone:
            return
        from app.config import settings
        if not settings.twilio.ACCOUNT_SID or settings.twilio.ACCOUNT_SID.startswith("your"):
            return
        try:
            from twilio.rest import Client
            client = Client(settings.twilio.ACCOUNT_SID, settings.twilio.AUTH_TOKEN)
            content = notif.data or {}
            client.messages.create(
                body=content.get("sms_message", notif.message)[:160],
                from_=settings.twilio.PHONE_NUMBER,
                to=notif.recipient_phone,
            )
        except Exception as e:
            logger.warning(f"SMS send failed: {e}")

    async def _send_whatsapp(self, notif: Notification) -> None:
        if not notif.recipient_phone:
            return
        from app.config import settings
        if not settings.twilio.ACCOUNT_SID or settings.twilio.ACCOUNT_SID.startswith("your"):
            return
        try:
            from twilio.rest import Client
            client = Client(settings.twilio.ACCOUNT_SID, settings.twilio.AUTH_TOKEN)
            content = notif.data or {}
            client.messages.create(
                body=content.get("whatsapp_message", notif.message),
                from_=settings.twilio.WHATSAPP_NUMBER,
                to=f"whatsapp:{notif.recipient_phone}",
            )
        except Exception as e:
            logger.warning(f"WhatsApp send failed: {e}")

    async def _send_push(self, notif: Notification) -> None:
        """Send Firebase push notification."""
        if not notif.recipient_device_token:
            return
        from app.config import settings
        if not settings.FIREBASE_PROJECT_ID if hasattr(settings, 'FIREBASE_PROJECT_ID') else True:
            return
        try:
            from firebase_admin import messaging
            content = notif.data or {}
            message = messaging.Message(
                notification=messaging.Notification(
                    title=content.get("push_title", notif.title),
                    body=content.get("push_body", notif.message),
                ),
                token=notif.recipient_device_token,
            )
            messaging.send(message)
        except Exception as e:
            logger.debug(f"Push send failed: {e}")
