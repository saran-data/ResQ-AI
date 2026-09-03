"""
ResQAI - Database Connection Management
Async SQLAlchemy engine with connection pooling, health checks,
and graceful fallback when PostgreSQL is unavailable.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from loguru import logger

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


# -------------------------------------------------------
# Engine (created lazily)
# -------------------------------------------------------
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database.URL,
            pool_size=settings.database.POOL_SIZE,
            max_overflow=settings.database.MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.database.ECHO,
            future=True,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


# Public aliases kept for backwards compatibility
@property
def engine() -> AsyncEngine:
    return _get_engine()


@property
def AsyncSessionLocal() -> async_sessionmaker:
    return _get_session_factory()


# -------------------------------------------------------
# Dependency: Get DB Session
# -------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Automatically handles commit/rollback/close.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# -------------------------------------------------------
# Context Manager (for non-FastAPI usage)
# -------------------------------------------------------
@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside FastAPI."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# -------------------------------------------------------
# Health Check
# -------------------------------------------------------
async def check_database_health() -> dict:
    """Verify database connectivity and return health status."""
    import time
    try:
        start = time.monotonic()
        factory = _get_session_factory()
        async with factory() as session:
            result = await session.execute(text("SELECT version(), NOW()"))
            row = result.fetchone()
            latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "version": row[0].split(" ")[0] if row else "unknown",
        }
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# -------------------------------------------------------
# Init / Teardown
# -------------------------------------------------------
async def init_db() -> None:
    """Initialize database — create all tables if they don't exist."""
    try:
        eng = _get_engine()
        async with eng.begin() as conn:
            import app.models  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(
            f"Database init failed (app will run without DB): {e}\n"
            "To fix: ensure PostgreSQL is running and DATABASE_URL is correct in .env"
        )


async def close_db() -> None:
    """Gracefully close database connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
    logger.info("Database connections closed")
