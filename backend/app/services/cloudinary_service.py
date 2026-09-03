"""
ResQAI - Cloudinary Storage Service
Handles all image/file uploads with transformation pipelines for food images.
"""

from typing import Optional
import io

import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException
from loguru import logger

from app.config import settings

# Configure Cloudinary globally on import
cloudinary.config(
    cloud_name=settings.cloudinary.CLOUD_NAME,
    api_key=settings.cloudinary.API_KEY,
    api_secret=settings.cloudinary.API_SECRET,
    secure=True,
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class CloudinaryService:
    """
    Manages all media uploads for ResQAI.
    Applies intelligent transformations for food images (resize, optimize, face-blur).
    """

    async def upload_food_image(
        self,
        file: UploadFile,
        donation_id: str,
        item_index: int = 0,
    ) -> dict:
        """
        Upload a food item image with optimization transformations.

        Args:
            file: FastAPI UploadFile object
            donation_id: Parent donation UUID (for folder organization)
            item_index: Index within the donation (for unique naming)

        Returns:
            Dict with secure_url, public_id, width, height, format

        Raises:
            HTTPException 400: Invalid file type or size
        """
        await self._validate_file(file)

        content = await file.read()
        public_id = f"{settings.cloudinary.FOLDER}/donations/{donation_id}/item_{item_index}"

        try:
            result = cloudinary.uploader.upload(
                content,
                public_id=public_id,
                overwrite=True,
                resource_type="image",
                transformation=[
                    {"width": 1200, "height": 900, "crop": "limit"},  # Max dimensions
                    {"quality": "auto:good"},                           # Smart compression
                    {"fetch_format": "auto"},                           # Modern formats (WebP/AVIF)
                ],
                tags=[f"donation:{donation_id}", "food"],
            )
            logger.info(f"Food image uploaded: {public_id}")
            return {
                "secure_url": result["secure_url"],
                "public_id": result["public_id"],
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
                "bytes": result.get("bytes"),
            }
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")
            raise HTTPException(status_code=500, detail="Image upload failed")

    async def upload_profile_image(
        self,
        file: UploadFile,
        entity_type: str,
        entity_id: str,
    ) -> dict:
        """
        Upload a profile/logo image for restaurant or NGO.
        Applies face-detection crop for profile photos.
        """
        await self._validate_file(file)
        content = await file.read()
        public_id = f"{settings.cloudinary.FOLDER}/{entity_type}/{entity_id}/profile"

        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            overwrite=True,
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "auto"},
                {"quality": "auto:good"},
                {"fetch_format": "auto"},
                {"radius": "max"},  # Circular crop
            ],
        )
        return {
            "secure_url": result["secure_url"],
            "public_id": result["public_id"],
        }

    async def upload_document(
        self,
        file: UploadFile,
        folder: str,
        public_id: str,
    ) -> dict:
        """Upload a document (PDF, DOCX) for the knowledge base."""
        content = await file.read()
        full_public_id = f"{settings.cloudinary.FOLDER}/{folder}/{public_id}"

        result = cloudinary.uploader.upload(
            content,
            public_id=full_public_id,
            resource_type="raw",
            overwrite=True,
        )
        return {
            "secure_url": result["secure_url"],
            "public_id": result["public_id"],
            "bytes": result.get("bytes"),
        }

    async def delete_file(self, public_id: str, resource_type: str = "image") -> bool:
        """Delete a file from Cloudinary by its public_id."""
        try:
            result = cloudinary.uploader.destroy(
                public_id, resource_type=resource_type
            )
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Cloudinary delete failed for {public_id}: {e}")
            return False

    def get_thumbnail_url(
        self,
        public_id: str,
        width: int = 300,
        height: int = 200,
    ) -> str:
        """Generate a CDN thumbnail URL without re-uploading."""
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=width,
            height=height,
            crop="fill",
            quality="auto",
            fetch_format="auto",
        )

    async def _validate_file(self, file: UploadFile) -> None:
        """Validate file type and size before upload."""
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
            )

        # Check file size via content-length or by reading header bytes
        if file.size and file.size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB",
            )
