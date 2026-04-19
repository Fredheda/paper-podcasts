"""FastAPI application entrypoint.

This file is intentionally small: it only assembles the app.
Detailed logic is split into focused modules for readability:
- `config.py`: paths and environment bootstrap
- `state.py`: startup/shutdown lifecycle and shared services
- `security.py`: CORS + request security middleware
- `routes/`: endpoint groups by feature area
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .routes.chat import router as chat_router
from .routes.health import router as health_router
from .routes.jobs import router as jobs_router
from .routes.library import router as library_router
from .security import add_cors_middleware, security_middleware
from .state import lifespan

# Keep one consistent logging config for local debugging and server logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI app instance."""
    app = FastAPI(title="Paper Podcasts API", version="0.1.0", lifespan=lifespan)

    # Cross-cutting middleware first (applies to all routes).
    add_cors_middleware(app)
    app.middleware("http")(security_middleware)

    # Feature routers.
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(library_router)
    app.include_router(chat_router)

    return app


# Uvicorn target: `backend.app.main:app`
app = create_app()

