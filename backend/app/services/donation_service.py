"""
ResQAI - Donation Service
Orchestrates the full food rescue lifecycle: create → analyze → match → deliver → confirm.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

import qrcode
import io
import base64
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import generate_otp
from app.models.donation import Donation, DonationStatus
from app.models.food_item import FoodItem
from app.repositories.donation_repository import DonationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.donation import DonationCreate, DonationOTPVerify, DonationConfirm
from app.core.logging import get_logger

logger = get_logger(__name__)


class DonationService:
    """
    Manages all donation lifecycle operations.
    Triggers AI agent processing via Kafka events after each status transition.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._donation_repo = DonationRepository(db)
        self._restaurant_repo = RestaurantRepository(db)

    # -------------------------------------------------------
    # Create
    # -------------------------------------------------------
    async def create_donation(
        self,
        restaurant_id: UUID,
        data: DonationCreate,
    ) -> Donation:
        """
        Create a new donation and trigger the AI processing pipeline.

        Steps:
        1. Validate restaurant is active and verified
        2. Create donation record with DRAFT status
        3. Create linked food item records
        4. Transition to PENDING_ANALYSIS
        5. Emit Kafka event to trigger Food Analysis Agent

        Args:
            restaurant_id: Verified restaurant UUID
            data: Validated donation form data

        Returns:
            Created Donation instance
        """
        restaurant = await self._restaurant_repo.get_or_raise(restaurant_id)
        if not restaurant.is_verified:
            raise HTTPException(status_code=403, detail="Restaurant is not verified")

        # Calculate expiry (6 hours from pickup window start by default)
        try:
            pickup_start = datetime.fromisoformat(data.pickup_window_start)
            expires_at = (pickup_start + timedelta(hours=6)).isoformat()
        except ValueError:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()

        # Create donation
        donation = await self._donation_repo.create({
            "restaurant_id": restaurant_id,
            "status": DonationStatus.DRAFT,
            "pickup_address": data.pickup_address,
            "pickup_latitude": data.pickup_latitude,
            "pickup_longitude": data.pickup_longitude,
            "pickup_window_start": data.pickup_window_start,
            "pickup_window_end": data.pickup_window_end,
            "special_instructions": data.special_instructions,
            "contact_at_pickup": data.contact_at_pickup,
            "expires_at": expires_at,
            "status_history": [{
                "status": DonationStatus.DRAFT.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": str(restaurant_id),
            }],
        })

        # Create food items
        total_servings = 0
        total_weight = 0.0

        for item_data in data.food_items:
            item = FoodItem(
                donation_id=donation.id,
                name=item_data.name,
                category=item_data.category,
                description=item_data.description,
                quantity=item_data.quantity,
                unit=item_data.unit,
                is_vegetarian=item_data.is_vegetarian,
                is_vegan=item_data.is_vegan,
                is_halal=item_data.is_halal,
                is_jain=item_data.is_jain,
                allergens=item_data.allergens,
                preparation_time=item_data.preparation_time,
                best_before=item_data.best_before,
                requires_refrigeration=item_data.requires_refrigeration,
                requires_freezing=item_data.requires_freezing,
            )
            # Convert to kg for weight tracking
            if item_data.unit == "kg":
                total_weight += item_data.quantity
            elif item_data.unit in ("g", "grams"):
                total_weight += item_data.quantity / 1000
            elif item_data.unit in ("portions", "servings", "pieces"):
                total_weight += item_data.quantity * 0.25  # ~250g per portion estimate

            self._db.add(item)

        await self._db.flush()

        # Update donation totals
        await self._donation_repo.update(donation.id, {
            "total_items": len(data.food_items),
            "total_weight_kg": round(total_weight, 2),
        })

        # Trigger AI pipeline
        await self._trigger_analysis(donation.id)
        logger.info(f"Donation created: {donation.id} by restaurant {restaurant_id}")

        return await self._donation_repo.get_with_items(donation.id)

    # -------------------------------------------------------
    # OTP Verification (at pickup)
    # -------------------------------------------------------
    async def generate_otp(self, donation_id: UUID, actor: str) -> str:
        """
        Generate a 6-digit OTP for pickup verification.
        Also generates a QR code containing the OTP.

        Returns:
            OTP string
        """
        donation = await self._donation_repo.get_or_raise(donation_id)

        if donation.status not in (
            DonationStatus.MATCHED,
            DonationStatus.PICKUP_SCHEDULED,
            DonationStatus.AWAITING_PICKUP,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot generate OTP for donation in status '{donation.status}'",
            )

        otp = generate_otp(6)
        otp_expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        qr_url = await self._generate_qr_code(donation_id, otp)

        await self._donation_repo.update(donation_id, {
            "otp": otp,
            "otp_expires_at": otp_expires,
            "qr_code_url": qr_url,
        })
        return otp

    async def verify_otp(self, donation_id: UUID, request: DonationOTPVerify) -> bool:
        """
        Verify OTP at pickup point and transition to PICKED_UP.

        Raises:
            HTTPException 400: Invalid or expired OTP
        """
        donation = await self._donation_repo.get_or_raise(donation_id)

        if donation.otp != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        if donation.otp_expires_at:
            try:
                exp = datetime.fromisoformat(donation.otp_expires_at)
                if datetime.now(timezone.utc) > exp:
                    raise HTTPException(status_code=400, detail="OTP has expired")
            except ValueError:
                pass

        await self._donation_repo.update(donation_id, {"otp_verified": True})
        await self._donation_repo.transition_status(
            donation_id, DonationStatus.PICKED_UP, actor="volunteer"
        )

        # Emit tracking event
        await self._emit_event("donation.picked_up", {"donation_id": str(donation_id)})
        return True

    # -------------------------------------------------------
    # NGO Confirmation
    # -------------------------------------------------------
    async def confirm_delivery(
        self,
        donation_id: UUID,
        ngo_id: UUID,
        request: DonationConfirm,
    ) -> Donation:
        """NGO confirms food received and rates the experience."""
        donation = await self._donation_repo.get_or_raise(donation_id)

        if donation.matched_ngo_id != ngo_id:
            raise HTTPException(status_code=403, detail="NGO mismatch")

        if donation.status != DonationStatus.DELIVERED:
            raise HTTPException(
                status_code=400, detail="Donation not yet in DELIVERED status"
            )

        update_data = {
            "ngo_rating": request.rating,
            "ngo_feedback": request.feedback,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }

        await self._donation_repo.update(donation_id, update_data)
        await self._donation_repo.transition_status(
            donation_id, DonationStatus.CONFIRMED, actor=str(ngo_id)
        )

        # Update impact metrics on both restaurant and NGO
        await self._update_impact_after_confirmation(donation)

        return await self._donation_repo.get(donation_id)

    # -------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------
    async def _trigger_analysis(self, donation_id: UUID) -> None:
        """
        Transition to PENDING_ANALYSIS and publish Kafka event
        to trigger the Food Analysis → Safety → Matching pipeline.
        """
        await self._donation_repo.transition_status(
            donation_id, DonationStatus.PENDING_ANALYSIS, actor="system"
        )
        await self._emit_event(
            settings.kafka.TOPIC_DONATIONS,
            {
                "event": "donation.created",
                "donation_id": str(donation_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _emit_event(self, topic: str, payload: dict) -> None:
        """Publish an event to Kafka (fire-and-forget; failures are logged not raised)."""
        if not settings.ENABLE_KAFKA:
            return
        try:
            from app.events.kafka_manager import get_kafka_manager
            kafka = get_kafka_manager()
            if kafka:
                await kafka.produce(topic, payload)
        except Exception as e:
            logger.warning(f"Kafka emit failed (non-fatal): {e}")

    async def _generate_qr_code(self, donation_id: UUID, otp: str) -> str:
        """
        Generate a QR code containing the donation ID + OTP.
        Uploads to Cloudinary and returns the URL.
        In dev mode, returns a data URI.
        """
        qr_data = f"resqai://pickup/{donation_id}?otp={otp}"
        img = qrcode.make(qr_data)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        # In production: upload to Cloudinary
        try:
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                buffer.getvalue(),
                public_id=f"resqai/qrcodes/{donation_id}",
                format="png",
            )
            return result["secure_url"]
        except Exception:
            # Fallback: base64 data URI
            b64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{b64}"

    async def _update_impact_after_confirmation(self, donation: Donation) -> None:
        """Update denormalized impact counters after delivery confirmation."""
        try:
            await self._restaurant_repo.update_impact_metrics(
                restaurant_id=donation.restaurant_id,
                meals_delta=donation.total_servings,
                weight_delta=donation.total_weight_kg,
                carbon_delta=donation.carbon_saved_kg or 0.0,
            )
        except Exception as e:
            logger.warning(f"Impact metric update failed: {e}")
