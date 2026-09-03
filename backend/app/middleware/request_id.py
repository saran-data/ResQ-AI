"""
ResQAI - Request ID Middleware
Attaches a unique X-Request-ID to every request for distributed tracing.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a unique request ID to every HTTP request.
    - Uses incoming X-Request-ID header if provided (from upstream proxy)
    - Generates a new UUID otherwise
    - Adds X-Request-ID to response headers for client-side correlation
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Accept X-Request-ID from upstream (e.g., nginx, API gateway) or generate new
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Attach to request state for use in logging and error handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Echo request ID back to client
        response.headers["X-Request-ID"] = request_id

        return response
