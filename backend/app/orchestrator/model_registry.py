"""
ResQAI - AI Model Registry
Multi-model architecture: each task type routes to the best model.
Manages client initialization, health checks, and capability mapping.
"""

from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field

from loguru import logger

from app.config import settings


# -------------------------------------------------------
# Model Identifiers
# -------------------------------------------------------
class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    MISTRAL = "mistral"
    OLLAMA = "ollama"


class ModelID(str, Enum):
    # OpenAI
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    # Anthropic
    CLAUDE_35_SONNET = "claude-3-5-sonnet-20241022"
    # Google
    GEMINI_15_PRO = "gemini-1.5-pro"
    # DeepSeek
    DEEPSEEK_CHAT = "deepseek-chat"
    # Mistral
    MISTRAL_SMALL = "mistral-small-latest"
    # Ollama (local)
    LLAMA3 = "llama3:8b"
    MISTRAL_LOCAL = "mistral:7b"


# -------------------------------------------------------
# Task → Model Routing Table
# -------------------------------------------------------
TASK_MODEL_MAP: dict[str, ModelID] = {
    # Food Analysis Agent — Gemini for vision/image understanding
    "food_analysis": ModelID.GEMINI_15_PRO,
    "food_image_analysis": ModelID.GEMINI_15_PRO,

    # Food Safety Agent — Claude for long-form guideline analysis
    "food_safety_check": ModelID.CLAUDE_35_SONNET,
    "fssai_compliance": ModelID.CLAUDE_35_SONNET,

    # NGO Matching — GPT-4o for complex multi-factor reasoning
    "ngo_matching": ModelID.GPT4O,
    "ngo_ranking": ModelID.GPT4O,

    # Route Optimization — DeepSeek for mathematical/algorithmic reasoning
    "route_optimization": ModelID.DEEPSEEK_CHAT,
    "vrp_solving": ModelID.DEEPSEEK_CHAT,
    "tsp_solving": ModelID.DEEPSEEK_CHAT,

    # Demand Prediction — GPT-4o for statistical analysis
    "demand_prediction": ModelID.GPT4O,
    "seasonal_analysis": ModelID.GPT4O,

    # Notification content generation — Mistral (fast, lightweight)
    "notification_content": ModelID.MISTRAL_SMALL,
    "sms_generation": ModelID.MISTRAL_SMALL,
    "email_generation": ModelID.MISTRAL_SMALL,

    # Volunteer Assignment — Llama 3 (local, privacy-preserving)
    "volunteer_matching": ModelID.LLAMA3,
    "volunteer_scoring": ModelID.LLAMA3,

    # Analytics narration — GPT-4o for insight generation
    "analytics_narration": ModelID.GPT4O,
    "kpi_analysis": ModelID.GPT4O,
    "trend_analysis": ModelID.GPT4O,

    # Fraud Detection — DeepSeek for pattern/anomaly detection
    "fraud_detection": ModelID.DEEPSEEK_CHAT,
    "anomaly_detection": ModelID.DEEPSEEK_CHAT,
    "ngo_verification": ModelID.DEEPSEEK_CHAT,

    # Admin Chatbot — Claude for conversational long-context
    "admin_chat": ModelID.CLAUDE_35_SONNET,
    "system_query": ModelID.CLAUDE_35_SONNET,

    # Fallback
    "default": ModelID.GPT4O_MINI,
}

# Fallback chain: if primary fails, try these in order
MODEL_FALLBACKS: dict[ModelID, list[ModelID]] = {
    ModelID.GEMINI_15_PRO: [ModelID.GPT4O, ModelID.CLAUDE_35_SONNET],
    ModelID.CLAUDE_35_SONNET: [ModelID.GPT4O, ModelID.GPT4O_MINI],
    ModelID.GPT4O: [ModelID.CLAUDE_35_SONNET, ModelID.GPT4O_MINI],
    ModelID.DEEPSEEK_CHAT: [ModelID.GPT4O_MINI, ModelID.MISTRAL_SMALL],
    ModelID.MISTRAL_SMALL: [ModelID.GPT4O_MINI, ModelID.LLAMA3],
    ModelID.LLAMA3: [ModelID.MISTRAL_LOCAL, ModelID.GPT4O_MINI],
}


@dataclass
class ModelStatus:
    model_id: ModelID
    provider: ModelProvider
    is_available: bool = True
    last_error: Optional[str] = None
    total_calls: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0


class ModelRegistry:
    """
    Central registry for all AI model clients.
    - Maps tasks to optimal models
    - Manages client lifecycle
    - Tracks model health and availability
    - Provides fallback routing when primary model fails
    """

    def __init__(self) -> None:
        self._clients: dict[ModelProvider, Any] = {}
        self._status: dict[ModelID, ModelStatus] = {}
        self._initialized = False

    # -------------------------------------------------------
    # Initialization
    # -------------------------------------------------------
    async def warm_up(self) -> None:
        """Initialize all available AI model clients."""
        logger.info("Warming up AI Model Registry...")

        await self._init_openai()
        await self._init_anthropic()
        await self._init_google()
        await self._init_deepseek()
        await self._init_mistral()
        await self._init_ollama()

        self._initialized = True
        available = [m.model_id.value for m in self._status.values() if m.is_available]
        logger.info(f"Model Registry ready. Available models: {available}")

    async def _init_openai(self) -> None:
        if not settings.openai.API_KEY or settings.openai.API_KEY.startswith("sk-your"):
            logger.warning("OpenAI API key not configured")
            self._mark_unavailable(ModelID.GPT4O, ModelID.GPT4O_MINI)
            return
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai.API_KEY, timeout=30)
            self._clients[ModelProvider.OPENAI] = client
            self._mark_available(ModelID.GPT4O, ModelProvider.OPENAI)
            self._mark_available(ModelID.GPT4O_MINI, ModelProvider.OPENAI)
            logger.info("OpenAI client initialized (GPT-4o, GPT-4o-mini)")
        except Exception as e:
            logger.error(f"OpenAI init failed: {e}")
            self._mark_unavailable(ModelID.GPT4O, ModelID.GPT4O_MINI)

    async def _init_anthropic(self) -> None:
        if not settings.anthropic.API_KEY or settings.anthropic.API_KEY.startswith("sk-ant-your"):
            logger.warning("Anthropic API key not configured")
            self._mark_unavailable(ModelID.CLAUDE_35_SONNET)
            return
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.anthropic.API_KEY, timeout=60)
            self._clients[ModelProvider.ANTHROPIC] = client
            self._mark_available(ModelID.CLAUDE_35_SONNET, ModelProvider.ANTHROPIC)
            logger.info("Anthropic client initialized (Claude 3.5 Sonnet)")
        except Exception as e:
            logger.error(f"Anthropic init failed: {e}")
            self._mark_unavailable(ModelID.CLAUDE_35_SONNET)

    async def _init_google(self) -> None:
        if not settings.gemini.AI_API_KEY or settings.gemini.AI_API_KEY.startswith("your"):
            logger.warning("Google AI API key not configured")
            self._mark_unavailable(ModelID.GEMINI_15_PRO)
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini.AI_API_KEY)
            self._clients[ModelProvider.GOOGLE] = genai
            self._mark_available(ModelID.GEMINI_15_PRO, ModelProvider.GOOGLE)
            logger.info("Google Gemini client initialized (Gemini 1.5 Pro)")
        except Exception as e:
            logger.error(f"Google Gemini init failed: {e}")
            self._mark_unavailable(ModelID.GEMINI_15_PRO)

    async def _init_deepseek(self) -> None:
        if not settings.deepseek.API_KEY or settings.deepseek.API_KEY.startswith("your"):
            logger.warning("DeepSeek API key not configured")
            self._mark_unavailable(ModelID.DEEPSEEK_CHAT)
            return
        try:
            from openai import AsyncOpenAI
            # DeepSeek is OpenAI-compatible
            client = AsyncOpenAI(
                api_key=settings.deepseek.API_KEY,
                base_url=settings.deepseek.BASE_URL,
                timeout=60,
            )
            self._clients[ModelProvider.DEEPSEEK] = client
            self._mark_available(ModelID.DEEPSEEK_CHAT, ModelProvider.DEEPSEEK)
            logger.info("DeepSeek client initialized")
        except Exception as e:
            logger.error(f"DeepSeek init failed: {e}")
            self._mark_unavailable(ModelID.DEEPSEEK_CHAT)

    async def _init_mistral(self) -> None:
        if not settings.mistral.API_KEY or settings.mistral.API_KEY.startswith("your"):
            logger.warning("Mistral API key not configured")
            self._mark_unavailable(ModelID.MISTRAL_SMALL)
            return
        try:
            from mistralai import Mistral
            client = Mistral(api_key=settings.mistral.API_KEY)
            self._clients[ModelProvider.MISTRAL] = client
            self._mark_available(ModelID.MISTRAL_SMALL, ModelProvider.MISTRAL)
            logger.info("Mistral client initialized")
        except Exception as e:
            logger.error(f"Mistral init failed: {e}")
            self._mark_unavailable(ModelID.MISTRAL_SMALL)

    async def _init_ollama(self) -> None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as http:
                r = await http.get(f"{settings.ollama.BASE_URL}/api/tags")
                if r.status_code == 200:
                    self._clients[ModelProvider.OLLAMA] = settings.ollama.BASE_URL
                    self._mark_available(ModelID.LLAMA3, ModelProvider.OLLAMA)
                    self._mark_available(ModelID.MISTRAL_LOCAL, ModelProvider.OLLAMA)
                    logger.info(f"Ollama ready at {settings.ollama.BASE_URL}")
                else:
                    self._mark_unavailable(ModelID.LLAMA3, ModelID.MISTRAL_LOCAL)
        except Exception:
            logger.warning("Ollama not reachable (local models unavailable)")
            self._mark_unavailable(ModelID.LLAMA3, ModelID.MISTRAL_LOCAL)

    # -------------------------------------------------------
    # Model Selection & Client Access
    # -------------------------------------------------------
    def get_model_for_task(self, task_name: str) -> ModelID:
        """
        Select the optimal model for a task, with fallback to available models.

        Args:
            task_name: Task identifier from TASK_MODEL_MAP

        Returns:
            Available ModelID (falls back to GPT-4o-mini if all fail)
        """
        primary = TASK_MODEL_MAP.get(task_name, TASK_MODEL_MAP["default"])

        if self._is_available(primary):
            return primary

        # Try fallback chain
        for fallback in MODEL_FALLBACKS.get(primary, []):
            if self._is_available(fallback):
                logger.warning(
                    f"Primary model {primary.value} unavailable, using fallback {fallback.value}",
                    task=task_name,
                )
                return fallback

        # Last resort: GPT-4o-mini
        logger.warning(f"All preferred models unavailable for task '{task_name}', using GPT-4o-mini")
        return ModelID.GPT4O_MINI

    def get_client(self, provider: ModelProvider) -> Any:
        """Get the raw client for a model provider."""
        client = self._clients.get(provider)
        if not client:
            raise RuntimeError(f"Model provider {provider} not initialized")
        return client

    def get_openai_client(self) -> Any:
        return self.get_client(ModelProvider.OPENAI)

    def get_anthropic_client(self) -> Any:
        return self.get_client(ModelProvider.ANTHROPIC)

    def get_google_client(self) -> Any:
        return self.get_client(ModelProvider.GOOGLE)

    def get_deepseek_client(self) -> Any:
        return self.get_client(ModelProvider.DEEPSEEK)

    def get_mistral_client(self) -> Any:
        return self.get_client(ModelProvider.MISTRAL)

    # -------------------------------------------------------
    # Health & Status
    # -------------------------------------------------------
    def _is_available(self, model_id: ModelID) -> bool:
        status = self._status.get(model_id)
        return status is not None and status.is_available

    def _mark_available(self, model_id: ModelID, provider: ModelProvider) -> None:
        self._status[model_id] = ModelStatus(
            model_id=model_id, provider=provider, is_available=True
        )

    def _mark_unavailable(self, *model_ids: ModelID) -> None:
        for m in model_ids:
            if m in self._status:
                self._status[m].is_available = False
            else:
                # Determine provider from model
                self._status[m] = ModelStatus(
                    model_id=m,
                    provider=ModelProvider.OPENAI,
                    is_available=False,
                )

    def get_health_report(self) -> dict:
        """Return health status of all registered models."""
        return {
            m.value: {
                "available": self._status[m].is_available if m in self._status else False,
                "total_calls": self._status[m].total_calls if m in self._status else 0,
                "error_rate": (
                    self._status[m].total_errors / max(self._status[m].total_calls, 1)
                    if m in self._status else 0
                ),
            }
            for m in ModelID
        }

    def record_call(self, model_id: ModelID, latency_ms: int, error: bool = False) -> None:
        """Track model usage statistics."""
        if model_id not in self._status:
            return
        status = self._status[model_id]
        status.total_calls += 1
        if error:
            status.total_errors += 1
        # Rolling average latency
        status.avg_latency_ms = (
            (status.avg_latency_ms * (status.total_calls - 1) + latency_ms)
            / status.total_calls
        )


# -------------------------------------------------------
# Module-level singleton
# -------------------------------------------------------
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get the global ModelRegistry instance (initialized during app startup)."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def set_model_registry(registry: ModelRegistry) -> None:
    global _registry
    _registry = registry
