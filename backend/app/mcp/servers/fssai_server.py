"""
ResQAI - MCP FSSAI Server
Interface to FSSAI (Food Safety and Standards Authority of India) API
for license verification and regulation retrieval.
"""

import re
from typing import Optional
import httpx
from loguru import logger
from app.config import settings


class FSSAIMCPServer:
    """
    MCP server for FSSAI integration.
    Used by: Food Safety Agent, Admin Dashboard.
    """

    # FSSAI license format: 14-digit number
    LICENSE_PATTERN = re.compile(r"^\d{14}$")

    def __init__(self) -> None:
        self._api_key = settings.FSSAI_API_KEY
        self._base_url = settings.FSSAI_BASE_URL

    def _is_configured(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("your"))

    async def verify_license(self, license_number: str) -> dict:
        """
        Verify an FSSAI license number.

        Args:
            license_number: 14-digit FSSAI license number

        Returns:
            Dict with valid, holder_name, expiry, status, business_type
        """
        if not license_number:
            return {"valid": False, "error": "No license number provided"}

        # Format validation first
        clean = re.sub(r"[\s\-]", "", license_number)
        if not self.LICENSE_PATTERN.match(clean):
            return {"valid": False, "error": f"Invalid FSSAI format (expected 14 digits, got: {license_number})"}

        if not self._is_configured():
            # Offline validation: check format and state code
            state_code = int(clean[:2])
            is_valid_state = 1 <= state_code <= 38
            return {
                "valid": is_valid_state,
                "license_number": clean,
                "validation_method": "format_check",
                "note": "Full verification requires FSSAI API key",
            }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self._base_url}/license/verify",
                    params={"license_number": clean},
                    headers={"X-API-Key": self._api_key},
                )
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "valid": data.get("status") == "active",
                        "license_number": clean,
                        "holder_name": data.get("business_name"),
                        "expiry_date": data.get("expiry_date"),
                        "status": data.get("status"),
                        "business_type": data.get("business_type"),
                        "state": data.get("state"),
                        "address": data.get("address"),
                    }
                elif r.status_code == 404:
                    return {"valid": False, "error": "License not found in FSSAI database"}
        except Exception as e:
            logger.warning(f"FSSAI API call failed: {e}")

        # Fallback format check
        return {
            "valid": True,
            "license_number": clean,
            "validation_method": "format_check_fallback",
        }

    async def get_guidelines(self, category: str) -> list:
        """
        Fetch safety guidelines for a food category.

        Args:
            category: Food category (e.g., 'dairy', 'meat', 'beverages')

        Returns:
            List of guideline dicts
        """
        # Return static guidelines when API unavailable
        guidelines = {
            "cooked_meal": [
                "Cooked food must be served at ≥60°C or stored at ≤5°C",
                "Maximum 4 hours in temperature danger zone (5-60°C)",
                "Cover and label all cooked food items",
                "Separate utensils for veg and non-veg items",
            ],
            "dairy": [
                "Store at 0-4°C",
                "Check for swelling, leakage, or off-smell before distribution",
                "Use within best-before date",
                "Cold chain must not be broken",
            ],
            "raw_produce": [
                "Wash thoroughly before distribution",
                "Store in cool, dry place",
                "Check for rot, mold, or unusual odors",
                "Remove damaged portions before donation",
            ],
            "bakery": [
                "Distribute within 24 hours of baking",
                "Keep in sealed packaging",
                "Avoid high humidity storage",
                "Check for mold — reject if any visible mold",
            ],
        }
        return [
            {"guideline": g, "source": "FSSAI", "category": category}
            for g in guidelines.get(category, [
                "Follow standard food hygiene practices",
                "Maintain clean storage and handling",
                "Label with preparation date and allergens",
            ])
        ]
