"""
ResQAI - MCP Weather Server
Provides current conditions and 5-day forecast for route planning and demand prediction.
"""

from typing import Optional
import httpx
from loguru import logger
from app.config import settings


class WeatherMCPServer:
    """
    MCP server wrapping OpenWeatherMap API.
    Used by: Route Optimization Agent, Demand Prediction Agent.
    """

    def __init__(self) -> None:
        self._api_key = settings.OPENWEATHER_API_KEY
        self._base_url = settings.OPENWEATHER_BASE_URL

    def _is_configured(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("your"))

    async def get_current_weather(self, city: str) -> Optional[dict]:
        """Get current weather for a city."""
        if not self._is_configured():
            return {"status": "unavailable", "description": "API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    f"{self._base_url}/weather",
                    params={"q": f"{city},IN", "appid": self._api_key, "units": "metric"},
                )
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "city": city,
                        "temperature_c": data["main"]["temp"],
                        "feels_like_c": data["main"]["feels_like"],
                        "humidity_percent": data["main"]["humidity"],
                        "description": data["weather"][0]["description"],
                        "wind_speed_kmh": round(data["wind"]["speed"] * 3.6, 1),
                        "visibility_km": data.get("visibility", 10000) / 1000,
                        "is_raining": data["weather"][0]["main"].lower() in ("rain", "drizzle", "thunderstorm"),
                        "is_extreme": data["weather"][0]["main"].lower() in ("thunderstorm", "tornado", "squall"),
                    }
        except Exception as e:
            logger.warning(f"Weather API failed for {city}: {e}")
        return None

    async def get_forecast(self, city: str, days: int = 5) -> list:
        """Get weather forecast for route planning."""
        if not self._is_configured():
            return []
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    f"{self._base_url}/forecast",
                    params={"q": f"{city},IN", "cnt": days * 8, "appid": self._api_key, "units": "metric"},
                )
                if r.status_code == 200:
                    data = r.json()
                    return [
                        {
                            "datetime": item["dt_txt"],
                            "temp_c": item["main"]["temp"],
                            "description": item["weather"][0]["description"],
                            "is_raining": item["weather"][0]["main"].lower() in ("rain", "drizzle", "thunderstorm"),
                            "wind_speed_kmh": round(item["wind"]["speed"] * 3.6, 1),
                        }
                        for item in data.get("list", [])
                    ]
        except Exception as e:
            logger.warning(f"Forecast API failed: {e}")
        return []

    async def assess_delivery_conditions(self, city: str) -> dict:
        """
        Assess current weather suitability for food delivery.
        Returns a condition score and recommendation.
        """
        weather = await self.get_current_weather(city)
        if not weather:
            return {"suitable": True, "score": 1.0, "note": "Weather data unavailable"}

        score = 1.0
        issues = []

        if weather.get("is_extreme"):
            score -= 0.6
            issues.append("Extreme weather conditions — delivery not recommended")
        elif weather.get("is_raining"):
            score -= 0.2
            issues.append("Rain — use covered vehicle and extra packaging")

        if weather.get("temperature_c", 25) > 40:
            score -= 0.2
            issues.append("High temperature — prioritize refrigerated transport")
        elif weather.get("temperature_c", 25) < 5:
            score -= 0.1
            issues.append("Cold conditions — keep cooked food heated")

        if weather.get("wind_speed_kmh", 0) > 50:
            score -= 0.2
            issues.append("Strong winds — secure all food packaging")

        return {
            "suitable": score > 0.3,
            "score": max(0.0, round(score, 2)),
            "conditions": weather.get("description", "unknown"),
            "temperature_c": weather.get("temperature_c"),
            "issues": issues,
            "recommendation": "Proceed normally" if score > 0.7 else "Exercise caution" if score > 0.3 else "Delay delivery",
        }
