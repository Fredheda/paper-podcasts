"""HTTP security middleware.

Why this exists:
- Security concerns are cross-cutting; centralizing them keeps routes simple.
- Includes optional controls that can be enabled by environment variables.

No CORS middleware: the browser only ever talks to whichever server is
serving the frontend (Vite dev server locally via vite.config.ts's
server.proxy, server.js in prod) -- that server proxies /api and /health to
the backend itself, server-side. The backend is never hit directly by a
browser from a different origin, so there's nothing for CORS to allow.
"""

from __future__ import annotations

import hmac
import os
import threading
import time
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() in {"1", "true", "yes", "on"}
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


def _is_rate_limited(client_id: str) -> bool:
    """Simple in-memory sliding-window limiter by client host."""
    if RATE_LIMIT_PER_MINUTE <= 0:
        return False

    now = time.time()
    window_start = now - 60.0

    with _RATE_LIMIT_LOCK:
        hits = _RATE_LIMIT_BUCKETS.get(client_id, [])
        hits = [timestamp for timestamp in hits if timestamp >= window_start]
        if len(hits) >= RATE_LIMIT_PER_MINUTE:
            _RATE_LIMIT_BUCKETS[client_id] = hits
            return True
        hits.append(now)
        _RATE_LIMIT_BUCKETS[client_id] = hits
        return False


async def security_middleware(request: Request, call_next: Callable[..., Response]) -> Response:
    """Global request checks + response hardening headers.

    Request checks:
    - Optional HTTPS enforcement
    - Optional API key auth
    - In-memory rate limiting

    Response headers:
    - X-Content-Type-Options
    - Referrer-Policy
    - X-Frame-Options
    - Optional HSTS when FORCE_HTTPS is enabled
    """
    if FORCE_HTTPS:
        # Trust X-Forwarded-Proto only when explicitly configured behind a trusted proxy.
        proto = request.headers.get("x-forwarded-proto", request.url.scheme) if TRUST_PROXY_HEADERS else request.url.scheme
        if proto != "https":
            return JSONResponse(status_code=400, content={"detail": "HTTPS is required"})

    client_id = request.client.host if request.client else "unknown"
    if request.url.path != "/health" and _is_rate_limited(client_id):
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})

    if BACKEND_API_KEY and request.method != "OPTIONS" and request.url.path != "/health":
        provided_key = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(provided_key, BACKEND_API_KEY):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if FORCE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

