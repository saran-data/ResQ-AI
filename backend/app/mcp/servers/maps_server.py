"""
ResQAI - MCP Maps Server
Model Context Protocol server for Google Maps + OpenStreetMap integration.
Provides tools: geocoding, route directions, distance matrix, places search.
"""

from typing import Optional
import httpx
from loguru import logger
from app.config import settings


class MapsMCPServer:
    """
    MCP server wrapping Google Maps APIs.
    Used by: Route Optimization Agent, NGO Matching Agent.
    """

    BASE_URL = "https://maps.googleapis.com/maps/api"

    def __init__(self) -> None:
        self._api_key = settings.gemini.MAPS_API_KEY

    def _is_configured(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("your"))

    async def geocode(self, address: str) -> Optional[dict]:
        """
        Convert address to latitude/longitude coordinates.

        Args:
            address: Street address or place name

        Returns:
            Dict with lat, lng, formatted_address, or None
        """
        if not self._is_configured():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.BASE_URL}/geocode/json",
                    params={"address": address, "region": "in", "key": self._api_key},
                )
                data = r.json()
                if data["status"] == "OK" and data["results"]:
                    loc = data["results"][0]["geometry"]["location"]
                    return {
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "formatted_address": data["results"][0]["formatted_address"],
                        "place_id": data["results"][0]["place_id"],
                    }
        except Exception as e:
            logger.warning(f"Maps geocode failed: {e}")
        return None

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """Convert coordinates to human-readable address."""
        if not self._is_configured():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.BASE_URL}/geocode/json",
                    params={"latlng": f"{lat},{lng}", "key": self._api_key},
                )
                data = r.json()
                if data["status"] == "OK" and data["results"]:
                    return data["results"][0]["formatted_address"]
        except Exception as e:
            logger.warning(f"Maps reverse geocode failed: {e}")
        return None

    async def get_directions(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "driving",
    ) -> Optional[dict]:
        """
        Get turn-by-turn directions between two points.

        Returns:
            Dict with distance, duration, polyline, steps
        """
        if not self._is_configured():
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.BASE_URL}/directions/json",
                    params={
                        "origin": f"{origin_lat},{origin_lng}",
                        "destination": f"{dest_lat},{dest_lng}",
                        "mode": mode,
                        "departure_time": "now",
                        "traffic_model": "best_guess",
                        "key": self._api_key,
                    },
                )
                data = r.json()
                if data["status"] == "OK" and data["routes"]:
                    route = data["routes"][0]
                    leg = route["legs"][0]
                    return {
                        "distance_km": leg["distance"]["value"] / 1000,
                        "duration_minutes": leg.get("duration_in_traffic", leg["duration"])["value"] / 60,
                        "distance_text": leg["distance"]["text"],
                        "duration_text": leg["duration"]["text"],
                        "polyline": route["overview_polyline"]["points"],
                        "steps": [
                            {
                                "instruction": step["html_instructions"],
                                "distance": step["distance"]["text"],
                                "duration": step["duration"]["text"],
                            }
                            for step in leg["steps"][:10]  # First 10 steps
                        ],
                        "start_address": leg["start_address"],
                        "end_address": leg["end_address"],
                    }
        except Exception as e:
            logger.warning(f"Maps directions failed: {e}")
        return None

    async def distance_matrix(
        self,
        origins: list,
        destinations: list,
    ) -> Optional[list]:
        """
        Compute distance/duration matrix for multiple origins and destinations.
        Used for multi-pickup VRP optimization.
        """
        if not self._is_configured() or not origins or not destinations:
            return None
        try:
            origins_str = "|".join(f"{o[0]},{o[1]}" for o in origins)
            destinations_str = "|".join(f"{d[0]},{d[1]}" for d in destinations)

            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{self.BASE_URL}/distancematrix/json",
                    params={
                        "origins": origins_str,
                        "destinations": destinations_str,
                        "mode": "driving",
                        "departure_time": "now",
                        "key": self._api_key,
                    },
                )
                data = r.json()
                if data["status"] == "OK":
                    matrix = []
                    for row in data["rows"]:
                        row_data = []
                        for element in row["elements"]:
                            if element["status"] == "OK":
                                row_data.append({
                                    "distance_km": element["distance"]["value"] / 1000,
                                    "duration_minutes": element.get("duration_in_traffic", element["duration"])["value"] / 60,
                                })
                            else:
                                row_data.append({"distance_km": 999, "duration_minutes": 999})
                        matrix.append(row_data)
                    return matrix
        except Exception as e:
            logger.warning(f"Maps distance matrix failed: {e}")
        return None

    async def nearby_places(
        self,
        lat: float,
        lng: float,
        radius_meters: int = 5000,
        place_type: str = "restaurant",
    ) -> list:
        """Search for nearby places (restaurants, NGOs, hospitals)."""
        if not self._is_configured():
            return []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.BASE_URL}/place/nearbysearch/json",
                    params={
                        "location": f"{lat},{lng}",
                        "radius": radius_meters,
                        "type": place_type,
                        "key": self._api_key,
                    },
                )
                data = r.json()
                if data.get("status") == "OK":
                    return [
                        {
                            "name": p["name"],
                            "lat": p["geometry"]["location"]["lat"],
                            "lng": p["geometry"]["location"]["lng"],
                            "place_id": p["place_id"],
                            "rating": p.get("rating"),
                            "vicinity": p.get("vicinity"),
                        }
                        for p in data.get("results", [])[:10]
                    ]
        except Exception as e:
            logger.warning(f"Maps nearby places failed: {e}")
        return []
