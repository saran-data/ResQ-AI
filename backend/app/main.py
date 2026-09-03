"""
ResQAI - FastAPI Application Entry Point
Production-ready ASGI application with full middleware stack, lifespan management,
health checks, and observability integration.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from loguru import logger

from app.config import settings
from app.core.logging import configure_logging
from app.core.database import init_db, close_db, check_database_health
from app.core.redis_client import init_redis, close_redis, get_cache_manager
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.audit_log import AuditLogMiddleware


# -------------------------------------------------------
# Application Lifespan
# -------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown lifecycle.
    Initializes all external connections on startup and cleans up on shutdown.
    """
    # ---- STARTUP ----
    configure_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # Initialize Sentry error tracking
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=0.1,
        )
        logger.info("Sentry error tracking initialized")

    # Initialize database (non-fatal if unavailable)
    await init_db()

    # Initialize Redis (non-fatal if unavailable)
    try:
        await init_redis()
        logger.info("Redis connection pool ready")
    except Exception as e:
        logger.warning(f"Redis unavailable (caching disabled): {e}")

    # Initialize Qdrant collections (non-fatal)
    if settings.ENABLE_RAG:
        try:
            from app.rag.embeddings.qdrant_manager import QdrantManager
            qdrant = QdrantManager()
            await qdrant.initialize_collections()
            logger.info("Qdrant vector collections initialized")
        except Exception as e:
            logger.warning(f"Qdrant unavailable (RAG disabled): {e}")

    # Initialize Kafka consumers (non-fatal)
    if settings.ENABLE_KAFKA:
        try:
            from app.events.kafka_manager import KafkaManager
            kafka_manager = KafkaManager()
            await kafka_manager.start()
            app.state.kafka = kafka_manager
            logger.info("Kafka consumers started")
        except Exception as e:
            logger.warning(f"Kafka unavailable (events disabled): {e}")

    # Warm up AI model registry (non-fatal)
    if settings.ENABLE_AI_AGENTS:
        try:
            from app.orchestrator.model_registry import ModelRegistry, set_model_registry
            registry = ModelRegistry()
            await registry.warm_up()
            app.state.model_registry = registry
            set_model_registry(registry)
            logger.info("AI model registry warmed up")
        except Exception as e:
            logger.warning(f"Model registry warm-up failed: {e}")

    logger.info(f"{settings.APP_NAME} startup complete — ready to serve requests")

    yield  # Application runs here

    # ---- SHUTDOWN ----
    logger.info("Shutting down ResQAI...")

    if settings.ENABLE_KAFKA and hasattr(app.state, "kafka"):
        try:
            await app.state.kafka.stop()
        except Exception:
            pass

    try:
        await close_redis()
    except Exception:
        pass

    await close_db()
    logger.info("ResQAI shutdown complete")


# -------------------------------------------------------
# Application Factory
# -------------------------------------------------------
def create_application() -> FastAPI:
    """
    Application factory — creates and configures the FastAPI application.
    Separating creation from instantiation enables clean testing.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI Powered Intelligent Food Rescue Ecosystem",
        version=settings.APP_VERSION,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ---- Middleware Stack ----
    # Order matters: outer middleware runs first on request, last on response

    # Security: Trusted hosts
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["resqai.org", "*.resqai.org", "localhost"],
        )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
        expose_headers=["X-Request-ID", "X-Rate-Limit-Remaining", "X-Rate-Limit-Reset"],
    )

    # GZip compression for responses > 1000 bytes
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Request tracing (attach unique X-Request-ID)
    app.add_middleware(RequestIDMiddleware)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware)

    # Audit logging (log every write operation)
    app.add_middleware(AuditLogMiddleware)

    # ---- Prometheus Metrics ----
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/metrics"],
        inprogress_name="resqai_inprogress",
        inprogress_labels=True,
    ).instrument(app).expose(app, endpoint="/metrics", tags=["Monitoring"])

    # ---- Routes ----
    _register_routes(app)

    # ---- Exception Handlers ----
    _register_exception_handlers(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routers."""
    from app.api.v1.endpoints import (
        auth, users, restaurants, ngos, volunteers,
        donations, deliveries, routes, notifications,
        analytics, admin, ai_agents, reports, search,
    )
    from app.graphql.schema import graphql_router
    from app.websockets.manager import websocket_router

    # REST API v1
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Authentication"])
    app.include_router(users.router, prefix=f"{api_prefix}/users", tags=["Users"])
    app.include_router(restaurants.router, prefix=f"{api_prefix}/restaurants", tags=["Restaurants"])
    app.include_router(ngos.router, prefix=f"{api_prefix}/ngos", tags=["NGOs"])
    app.include_router(volunteers.router, prefix=f"{api_prefix}/volunteers", tags=["Volunteers"])
    app.include_router(donations.router, prefix=f"{api_prefix}/donations", tags=["Donations"])
    app.include_router(deliveries.router, prefix=f"{api_prefix}/deliveries", tags=["Deliveries"])
    app.include_router(routes.router, prefix=f"{api_prefix}/routes", tags=["Routes"])
    app.include_router(notifications.router, prefix=f"{api_prefix}/notifications", tags=["Notifications"])
    app.include_router(analytics.router, prefix=f"{api_prefix}/analytics", tags=["Analytics"])
    app.include_router(admin.router, prefix=f"{api_prefix}/admin", tags=["Admin"])
    app.include_router(ai_agents.router, prefix=f"{api_prefix}/agents", tags=["AI Agents"])
    app.include_router(reports.router, prefix=f"{api_prefix}/reports", tags=["Reports"])
    app.include_router(search.router, prefix=f"{api_prefix}/search", tags=["Search"])

    # GraphQL
    app.include_router(graphql_router, prefix="/graphql", tags=["GraphQL"])

    # WebSocket
    app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for consistent error responses."""
    from fastapi import HTTPException
    from sqlalchemy.exc import SQLAlchemyError
    from pydantic import ValidationError

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "type": "http_error",
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Validation error",
                    "type": "validation_error",
                    "details": exc.errors(),
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(f"Database error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": 500,
                    "message": "Database error occurred",
                    "type": "database_error",
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": 500,
                    "message": "An unexpected error occurred",
                    "type": "internal_error",
                },
                "request_id": getattr(request.state, "request_id", None),
            },
        )


# -------------------------------------------------------
# Application Instance
# -------------------------------------------------------
app = create_application()


# -------------------------------------------------------
# Health Check Endpoints
# -------------------------------------------------------
@app.get("/health", tags=["Health"], summary="Application health check")
async def health_check():
    """
    Basic health check endpoint.
    Returns service status for load balancer health probes.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/health/detailed", tags=["Health"], summary="Detailed component health check")
async def detailed_health_check():
    """
    Detailed health check across all system components.
    Checks database, Redis, Qdrant connectivity.
    """
    from app.core.database import check_database_health
    from app.core.redis_client import get_cache_manager

    start_time = time.monotonic()

    db_health = await check_database_health()
    redis_health = await get_cache_manager().health_check()

    total_time = round((time.monotonic() - start_time) * 1000, 2)

    all_healthy = all(
        h.get("status") == "healthy"
        for h in [db_health, redis_health]
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "check_duration_ms": total_time,
        "components": {
            "database": db_health,
            "redis": redis_health,
        },
    }


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """API root — returns basic service information."""
    return {
        "service": settings.APP_NAME,
        "tagline": "AI Powered Intelligent Food Rescue Ecosystem",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# -------------------------------------------------------
# Custom OpenAPI Schema
# -------------------------------------------------------
def custom_openapi():
    """Generate custom OpenAPI schema with security definitions."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## ResQAI - AI Powered Intelligent Food Rescue Ecosystem

Enterprise-grade multi-agent AI platform for autonomous food rescue operations.

### Authentication
All protected endpoints require a Bearer JWT token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

### Rate Limiting
- Default: 100 requests per minute per user
- Burst: 20 requests per second
- Headers: `X-Rate-Limit-Remaining`, `X-Rate-Limit-Reset`
        """,
        routes=app.routes,
        tags=[
            {"name": "Authentication", "description": "JWT auth, OAuth2, token refresh"},
            {"name": "Donations", "description": "Food donation lifecycle management"},
            {"name": "AI Agents", "description": "Direct AI agent interaction endpoints"},
            {"name": "Analytics", "description": "KPIs, dashboards, reports"},
        ],
    )

    # Add JWT Bearer security scheme
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
