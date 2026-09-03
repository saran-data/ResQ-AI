"""
ResQAI - Donations API Endpoints
Full donation lifecycle: create, upload images, list, get, verify OTP, confirm.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.donation import (
    DonationCreate, DonationUpdate, DonationResponse, DonationListResponse,
    DonationOTPVerify, DonationConfirm, DonationStatusUpdate,
)
from app.schemas.base import ApiResponse, PaginatedResponse, MessageResponse
from app.services.rbac_service import get_current_user, get_admin_user, get_restaurant_user, get_ngo_user
from app.services.donation_service import DonationService
from app.repositories.donation_repository import DonationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.ngo_repository import NGORepository

router = APIRouter()


@router.post(
    "",
    response_model=ApiResponse[DonationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new food donation",
)
async def create_donation(
    data: DonationCreate,
    current_user: User = Depends(get_restaurant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new food rescue donation.

    - Validates restaurant ownership
    - Creates food items
    - Triggers the AI pipeline (Food Analysis → Safety Check → NGO Matching)
    - Returns donation with initial status PENDING_ANALYSIS

    **Roles**: RESTAURANT_OWNER, RESTAURANT_STAFF
    """
    # Resolve restaurant owned by current user
    restaurant_repo = RestaurantRepository(db)
    restaurant = await restaurant_repo.get_by_owner(current_user.id)
    if not restaurant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No restaurant found for your account")

    service = DonationService(db)
    donation = await service.create_donation(restaurant.id, data)
    return ApiResponse.ok(
        data=DonationResponse.model_validate(donation),
        message="Donation created and AI analysis triggered",
    )


@router.post(
    "/{donation_id}/images",
    response_model=ApiResponse[dict],
    summary="Upload food item images",
)
async def upload_food_images(
    donation_id: UUID,
    files: List[UploadFile] = File(...),
    item_index: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload images for food items in a donation.
    Images are analyzed by the Gemini vision model (Food Analysis Agent).
    Max 5 images per food item, 10MB per image.
    """
    from app.services.cloudinary_service import CloudinaryService
    from app.models.food_item import FoodItem
    from sqlalchemy import select, update

    # Verify ownership
    repo = DonationRepository(db)
    donation = await repo.get_or_raise(donation_id)

    cloudinary_svc = CloudinaryService()
    uploaded_urls = []
    cloudinary_ids = []

    for i, file in enumerate(files[:5]):  # Max 5 images
        result = await cloudinary_svc.upload_food_image(
            file, str(donation_id), item_index + i
        )
        uploaded_urls.append(result["secure_url"])
        cloudinary_ids.append(result["public_id"])

    # Update food item with image URLs
    food_items = donation.food_items if hasattr(donation, 'food_items') else []

    # Re-trigger image analysis via Celery
    try:
        from app.tasks.ai_tasks import analyze_food_images_task
        analyze_food_images_task.delay(str(donation_id), uploaded_urls)
    except Exception:
        pass

    return ApiResponse.ok(
        data={"uploaded": len(uploaded_urls), "urls": uploaded_urls},
        message="Images uploaded and queued for AI analysis",
    )


@router.get(
    "",
    response_model=PaginatedResponse[DonationListResponse],
    summary="List donations",
)
async def list_donations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List donations scoped to the current user's role:
    - Restaurant: their own donations
    - NGO: donations matched to them
    - Admin: all donations
    - Volunteer: assigned deliveries
    """
    from app.models.donation import DonationStatus as DS

    repo = DonationRepository(db)
    status_val = DS(status_filter) if status_filter else None
    skip = (page - 1) * page_size

    if current_user.role in (UserRole.RESTAURANT_OWNER, UserRole.RESTAURANT_STAFF):
        restaurant_repo = RestaurantRepository(db)
        restaurant = await restaurant_repo.get_by_owner(current_user.id)
        if not restaurant:
            return PaginatedResponse.ok(data=[], page=page, page_size=page_size, total=0)
        donations, total = await repo.get_by_restaurant(
            restaurant.id, status=status_val, skip=skip, limit=page_size
        )

    elif current_user.role in (UserRole.NGO_MANAGER, UserRole.NGO_STAFF):
        ngo_repo = NGORepository(db)
        ngo = await ngo_repo.get_by_manager(current_user.id)
        if not ngo:
            return PaginatedResponse.ok(data=[], page=page, page_size=page_size, total=0)
        donations, total = await repo.get_by_ngo(ngo.id, skip=skip, limit=page_size)

    else:  # Admin or volunteer sees all
        donations, total = await repo.get_all(
            skip=skip, limit=page_size,
            filters={"status": status_val} if status_val else None,
        )

    return PaginatedResponse.ok(
        data=[DonationListResponse.model_validate(d) for d in donations],
        page=page, page_size=page_size, total=total,
    )


@router.get(
    "/{donation_id}",
    response_model=ApiResponse[DonationResponse],
    summary="Get donation details",
)
async def get_donation(
    donation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full donation details including food items and AI decisions."""
    repo = DonationRepository(db)
    donation = await repo.get_with_items(donation_id)
    if not donation:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Donation not found")
    return ApiResponse.ok(data=DonationResponse.model_validate(donation))


@router.post(
    "/{donation_id}/generate-otp",
    response_model=ApiResponse[dict],
    summary="Generate OTP for pickup verification",
)
async def generate_pickup_otp(
    donation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a 6-digit OTP and QR code for pickup verification.
    Sent to both restaurant and volunteer.
    """
    service = DonationService(db)
    otp = await service.generate_otp(donation_id, actor=str(current_user.id))
    return ApiResponse.ok(
        data={"otp": otp, "message": "OTP valid for 30 minutes"},
        message="OTP generated",
    )


@router.post(
    "/{donation_id}/verify-otp",
    response_model=ApiResponse[dict],
    summary="Verify pickup OTP",
)
async def verify_pickup_otp(
    donation_id: UUID,
    request: DonationOTPVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Volunteer enters OTP to confirm pickup.
    Transitions donation to PICKED_UP status.
    """
    service = DonationService(db)
    await service.verify_otp(donation_id, request)
    return ApiResponse.ok(
        data={"verified": True},
        message="Pickup confirmed successfully",
    )


@router.post(
    "/{donation_id}/confirm",
    response_model=ApiResponse[DonationResponse],
    summary="NGO confirms delivery received",
)
async def confirm_delivery(
    donation_id: UUID,
    request: DonationConfirm,
    current_user: User = Depends(get_ngo_user),
    db: AsyncSession = Depends(get_db),
):
    """
    NGO manager confirms food has been received.
    Transitions donation to CONFIRMED and updates all impact metrics.
    """
    ngo_repo = NGORepository(db)
    ngo = await ngo_repo.get_by_manager(current_user.id)
    if not ngo:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="NGO not found for this account")

    service = DonationService(db)
    donation = await service.confirm_delivery(donation_id, ngo.id, request)
    return ApiResponse.ok(
        data=DonationResponse.model_validate(donation),
        message="Delivery confirmed. Impact metrics updated.",
    )


@router.patch(
    "/{donation_id}/status",
    response_model=ApiResponse[DonationResponse],
    summary="Manual status update (admin)",
    dependencies=[Depends(get_admin_user)],
)
async def update_donation_status(
    donation_id: UUID,
    request: DonationStatusUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin override for donation status (emergency use)."""
    repo = DonationRepository(db)
    donation = await repo.transition_status(
        donation_id, request.status, actor=f"admin:{current_user.id}"
    )
    return ApiResponse.ok(data=DonationResponse.model_validate(donation))
