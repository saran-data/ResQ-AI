"""
ResQAI - Application Settings
Centralized configuration using Pydantic Settings with full validation.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import AnyHttpUrl, EmailStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    HOST: str = "localhost"
    PORT: int = 5432
    NAME: str = "resqai_db"
    USER: str = "resqai_user"
    PASSWORD: str = "password"
    URL: Optional[str] = None
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 0
    ECHO: bool = False

    @model_validator(mode="after")
    def build_url(self) -> "DatabaseSettings":
        if not self.URL:
            self.URL = (
                f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}"
                f"@{self.HOST}:{self.PORT}/{self.NAME}"
            )
        return self


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    HOST: str = "localhost"
    PORT: int = 6379
    PASSWORD: Optional[str] = None
    DB: int = 0
    URL: Optional[str] = None
    CACHE_TTL: int = 3600

    @model_validator(mode="after")
    def build_url(self) -> "RedisSettings":
        if not self.URL:
            auth = f":{self.PASSWORD}@" if self.PASSWORD else ""
            self.URL = f"redis://{auth}{self.HOST}:{self.PORT}/{self.DB}"
        return self


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_", extra="ignore")

    HOST: str = "localhost"
    PORT: int = 6333
    GRPC_PORT: int = 6334
    API_KEY: Optional[str] = None
    URL: Optional[str] = None
    COLLECTION_NGO: str = "ngo_profiles"
    COLLECTION_RESTAURANT: str = "restaurant_profiles"
    COLLECTION_FOOD_SAFETY: str = "food_safety_guidelines"
    COLLECTION_DONATIONS: str = "donation_history"
    COLLECTION_KNOWLEDGE: str = "knowledge_base"

    @model_validator(mode="after")
    def build_url(self) -> "QdrantSettings":
        if not self.URL:
            self.URL = f"http://{self.HOST}:{self.PORT}"
        return self


class JWTSettings(BaseSettings):
    """JWT authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_", extra="ignore")

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


class OpenAISettings(BaseSettings):
    """OpenAI (GPT-4o) configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_", extra="ignore")

    API_KEY: str = ""
    MODEL_PRIMARY: str = "gpt-4o"
    MODEL_FAST: str = "gpt-4o-mini"
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.1


class AnthropicSettings(BaseSettings):
    """Anthropic (Claude) configuration."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", extra="ignore")

    API_KEY: str = ""
    MODEL: str = "claude-3-5-sonnet-20241022"
    MAX_TOKENS: int = 8192


class GeminiSettings(BaseSettings):
    """Google Gemini configuration."""

    model_config = SettingsConfigDict(env_prefix="GOOGLE_", extra="ignore")

    AI_API_KEY: str = ""
    MAPS_API_KEY: str = ""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""


class OllamaSettings(BaseSettings):
    """Ollama (local models) configuration."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_", extra="ignore")

    BASE_URL: str = "http://localhost:11434"
    MODEL_LLAMA: str = "llama3:8b"
    MODEL_MISTRAL: str = "mistral:7b"


class DeepSeekSettings(BaseSettings):
    """DeepSeek configuration."""

    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_", extra="ignore")

    API_KEY: str = ""
    BASE_URL: str = "https://api.deepseek.com"
    MODEL: str = "deepseek-chat"


class MistralSettings(BaseSettings):
    """Mistral configuration."""

    model_config = SettingsConfigDict(env_prefix="MISTRAL_", extra="ignore")

    API_KEY: str = ""
    MODEL: str = "mistral-small-latest"


class CloudinarySettings(BaseSettings):
    """Cloudinary storage configuration."""

    model_config = SettingsConfigDict(env_prefix="CLOUDINARY_", extra="ignore")

    CLOUD_NAME: str = ""
    API_KEY: str = ""
    API_SECRET: str = ""
    FOLDER: str = "resqai"


class EmailSettings(BaseSettings):
    """SMTP email configuration."""

    model_config = SettingsConfigDict(env_prefix="SMTP_", extra="ignore")

    HOST: str = "smtp.gmail.com"
    PORT: int = 587
    USERNAME: str = ""
    PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@resqai.org"
    FROM_NAME: str = "ResQAI Platform"
    USE_TLS: bool = True


class TwilioSettings(BaseSettings):
    """Twilio SMS/WhatsApp configuration."""

    model_config = SettingsConfigDict(env_prefix="TWILIO_", extra="ignore")

    ACCOUNT_SID: str = ""
    AUTH_TOKEN: str = ""
    PHONE_NUMBER: str = ""
    WHATSAPP_NUMBER: str = "whatsapp:+14155238886"


class KafkaSettings(BaseSettings):
    """Apache Kafka configuration."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_", extra="ignore")

    BOOTSTRAP_SERVERS: str = "kafka:9092"
    CONSUMER_GROUP: str = "resqai-consumers"
    TOPIC_DONATIONS: str = "resqai.donations"
    TOPIC_NOTIFICATIONS: str = "resqai.notifications"
    TOPIC_AI_DECISIONS: str = "resqai.ai-decisions"
    TOPIC_ANALYTICS: str = "resqai.analytics"
    TOPIC_ROUTES: str = "resqai.routes"


class Settings(BaseSettings):
    """
    Main application settings.
    Aggregates all sub-settings and provides application-wide configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ResQAI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Nested settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    qdrant: QdrantSettings = QdrantSettings()
    jwt: JWTSettings = JWTSettings()
    openai: OpenAISettings = OpenAISettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    gemini: GeminiSettings = GeminiSettings()
    ollama: OllamaSettings = OllamaSettings()
    deepseek: DeepSeekSettings = DeepSeekSettings()
    mistral: MistralSettings = MistralSettings()
    cloudinary: CloudinarySettings = CloudinarySettings()
    email: EmailSettings = EmailSettings()
    twilio: TwilioSettings = TwilioSettings()
    kafka: KafkaSettings = KafkaSettings()

    # External APIs
    OPENWEATHER_API_KEY: str = ""
    OPENWEATHER_BASE_URL: str = "https://api.openweathermap.org/data/2.5"
    FSSAI_API_KEY: str = ""
    FSSAI_BASE_URL: str = "https://api.fssai.gov.in/v1"
    GOVT_NGO_API_KEY: str = ""
    GOVT_NGO_BASE_URL: str = "https://ngodarpan.gov.in/api/v1"

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 1536

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Feature Flags
    ENABLE_AI_AGENTS: bool = True
    ENABLE_RAG: bool = True
    ENABLE_MCP: bool = True
    ENABLE_KAFKA: bool = True
    ENABLE_IOT: bool = False
    ENABLE_VOICE_ASSISTANT: bool = False

    # Sentry
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v

    def get_allowed_origins(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Return cached application settings.
    Uses lru_cache so the .env file is only read once.
    """
    return Settings()


# Global settings instance
settings = get_settings()
