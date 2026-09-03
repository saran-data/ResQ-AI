"""
ResQAI - Audit Log Middleware
Records all write operations (POST, PUT, PATCH, DELETE) for compliance and security auditing.
"""

import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

# Methods that require audit logging
AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Paths to skip (health checks, metrics)
SKIP_PATHS = {"/health", "/health/detailed", "/metrics"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware that records all mutating operations.
    Logs: timestamp, user, method, path, status code, duration, IP address.
    Audit records are persisted asynchronously to avoid impacting request latency.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in AUDITED_METHODS or request.url.path in SKIP_PATHS:
            return await call_next(request)

        start_time = time.monotonic()

        # Extract user identity before processing
        user_id = await self._extract_user_id(request)
        client_ip = self._get_client_ip(request)
        request_id = getattr(request.state, "request_id", None)

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        # Log the audit entry
        logger.bind(
            audit=True,
            user_id=user_id,
            method=request.method,
            path=request.url.path,
            query=str(request.query_params),
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
            request_id=request_id,
            user_agent=request.headers.get("User-Agent", ""),
        ).info(f"AUDIT: {request.method} {request.url.path} → {response.status_code}")

        # Persist audit record asynchronously (fire-and-forget)
        try:
            from app.tasks.audit_tasks import persist_audit_log
            persist_audit_log.delay(
                user_id=user_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                request_id=request_id,
            )
        except Exception:
            pass  # Audit persistence failure must never block the response

        return response

    async def _extract_user_id(self, request: Request) -> str:
        """Safely extract user ID from JWT without raising."""
        try:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                from app.core.security import decode_token
                payload = decode_token(auth[7:])
                return payload.get("sub", "anonymous")
        except Exception:
            pass
        return "anonymous"

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP handling reverse proxy headers."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"
