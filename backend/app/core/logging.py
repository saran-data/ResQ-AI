"""
ResQAI - Structured Logging Configuration
Uses loguru for structured JSON logging with context propagation.
"""

import sys
import logging
from typing import Any

from loguru import logger

from app.config import settings


def configure_logging() -> None:
    """
    Configure application-wide logging.
    - JSON structured format in production
    - Human-readable format in development
    - Integrates with standard library logging (for third-party libs)
    """
    # Remove default loguru handler
    logger.remove()

    # Configure log format
    if settings.LOG_FORMAT == "json":
        log_format = (
            '{{"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"name": "{name}", '
            '"function": "{function}", '
            '"line": {line}, '
            '"message": "{message}", '
            '"extra": {extra}}}'
        )
    else:
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=settings.LOG_LEVEL,
        colorize=settings.is_development,
        backtrace=settings.is_development,
        diagnose=settings.is_development,
        enqueue=True,  # Thread-safe logging
    )

    # Add file handler with rotation
    logger.add(
        "logs/resqai_{time:YYYY-MM-DD}.log",
        format=log_format,
        level=settings.LOG_LEVEL,
        rotation="00:00",       # Rotate at midnight
        retention="30 days",    # Keep 30 days
        compression="gz",       # Compress old logs
        enqueue=True,
        backtrace=True,
    )

    # Intercept standard library logging
    class InterceptHandler(logging.Handler):
        """Redirect stdlib logging to loguru."""

        def emit(self, record: logging.LogRecord) -> None:
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno  # type: ignore

            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back  # type: ignore
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Redirect all standard logging to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    logger.info(
        "Logging configured",
        env=settings.APP_ENV,
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
    )


def get_logger(name: str) -> Any:
    """
    Get a named logger instance with bound context.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Loguru logger with bound name context
    """
    return logger.bind(logger_name=name)
