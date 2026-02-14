"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Minimal liveness endpoint used by frontend bootstrap and monitoring."""
    return {"status": "ok"}

