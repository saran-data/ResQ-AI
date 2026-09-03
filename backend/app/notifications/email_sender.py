"""
ResQAI - Email Sender
Async SMTP email delivery with Jinja2 HTML templates.
"""

from typing import Optional
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, BaseLoader
from loguru import logger

from app.config import settings


# Simple inline templates (in production: load from files)
TEMPLATES = {
    "verification": """
    <h2>Verify your ResQAI account</h2>
    <p>Click the link below to verify your email address:</p>
    <a href="{url}">Verify Email</a>
    <p>This link expires in 24 hours.</p>
    """,
    "password_reset": """
    <h2>Reset your ResQAI password</h2>
    <p>Click the link below to reset your password:</p>
    <a href="{url}">Reset Password</a>
    <p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
    """,
    "donation_matched": """
    <h2>Your food donation has been matched!</h2>
    <p>Donation ID: {donation_id}</p>
    <p>Matched NGO: {ngo_name}</p>
    <p>Pickup time: {pickup_time}</p>
    """,
    "delivery_completed": """
    <h2>Food successfully delivered!</h2>
    <p>Your donation of {meals} meals has been delivered to {ngo_name}.</p>
    <p>Carbon saved: {carbon_kg}kg CO2</p>
    <p>Thank you for rescuing food!</p>
    """,
}


class EmailSender:
    """Async email sender using aiosmtplib."""

    async def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send an HTML email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text fallback

        Returns:
            True if sent successfully
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.email.FROM_NAME} <{settings.email.FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.email.HOST,
                port=settings.email.PORT,
                username=settings.email.USERNAME,
                password=settings.email.PASSWORD,
                use_tls=settings.email.USE_TLS,
            )
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email send failed to {to}: {e}")
            return False

    async def send_verification_email(self, email: str, token: str) -> bool:
        url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
        return await self.send(
            to=email,
            subject="Verify your ResQAI account",
            html_body=TEMPLATES["verification"].format(url=url),
        )

    async def send_password_reset_email(self, email: str, token: str) -> bool:
        url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        return await self.send(
            to=email,
            subject="Reset your ResQAI password",
            html_body=TEMPLATES["password_reset"].format(url=url),
        )

    async def send_donation_matched(
        self, email: str, donation_id: str, ngo_name: str, pickup_time: str
    ) -> bool:
        return await self.send(
            to=email,
            subject="Your food donation has been matched!",
            html_body=TEMPLATES["donation_matched"].format(
                donation_id=donation_id,
                ngo_name=ngo_name,
                pickup_time=pickup_time,
            ),
        )

    async def send_delivery_completed(
        self, email: str, meals: int, ngo_name: str, carbon_kg: float
    ) -> bool:
        return await self.send(
            to=email,
            subject="Food delivered successfully!",
            html_body=TEMPLATES["delivery_completed"].format(
                meals=meals, ngo_name=ngo_name, carbon_kg=carbon_kg
            ),
        )
