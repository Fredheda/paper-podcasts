"""Backend configuration and path bootstrap.

Why this exists:
- Keeps environment/path setup in one place instead of repeating it across modules.
- Makes it explicit which values are runtime configuration vs business logic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Resolve repository paths once so all modules can import shared code/data reliably.
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

# Load `.env` from repo root early so all config consumers see consistent values.
load_dotenv(REPO_ROOT / ".env")

# Shared domain modules live under `src/`. Ensure imports like `src.services...` work
# regardless of whether uvicorn is started from repo root or `backend/`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Shared artifact/prompts locations used by both backend and legacy Streamlit app.
DATA_DIR = REPO_ROOT / "data"
PROMPTS_DIR = REPO_ROOT / "prompts"

# Background worker concurrency for processing jobs.
DEFAULT_MAX_CONCURRENT = 5

# Storage backend selection: "local" (default, disk-based, zero Azure setup)
# or "azure" (Blob Storage + Azure SQL) -- see
# docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md.
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

# Common path validation for arXiv IDs in route parameters.
ARXIV_ID_PATH = dict(min_length=4, max_length=32, pattern=r"^[a-zA-Z0-9.\-]+$")


def parse_allowed_origins() -> list[str]:
    """Read and normalize CORS origins from `CORS_ORIGINS` env var."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]

