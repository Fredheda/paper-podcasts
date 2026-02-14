"""Disk-backed library helpers.

Why this exists:
- Library endpoints are backed by files in `data/papers/*`.
- Keeping file traversal/parsing in one module avoids repeating this logic in routes.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .config import DATA_DIR

logger = logging.getLogger(__name__)


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Normalize arXiv IDs by removing a trailing version suffix (example: v3)."""
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def build_library_item(paper_dir: Path, paper_data: dict[str, Any]) -> dict[str, Any]:
    """Build one API-ready library row from persisted state + file presence."""
    arxiv_id = normalize_arxiv_id(str(paper_data.get("arxiv_id", "")))
    audio_files = list((paper_dir / "audio").glob("*.mp3")) if (paper_dir / "audio").exists() else []
    has_audio = len(audio_files) > 0

    return {
        "title": paper_data.get("title", "Unknown"),
        "arxiv_id": arxiv_id,
        "authors": paper_data.get("authors", []),
        "status": paper_data.get("status", "unknown"),
        "abstract": paper_data.get("abstract", ""),
        "listen_status": paper_data.get("listen_status", "unlistened"),
        "last_listened_at": paper_data.get("last_listened_at"),
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        "audio_url": f"/api/library/{arxiv_id}/audio" if has_audio and arxiv_id else None,
    }


def load_library_from_disk() -> list[dict[str, Any]]:
    """Load all known paper entries from disk for the library list endpoint."""
    papers_dir = DATA_DIR / "papers"
    if not papers_dir.exists():
        return []

    library: list[dict[str, Any]] = []
    for paper_dir in papers_dir.iterdir():
        if not paper_dir.is_dir():
            continue

        state_file = paper_dir / "paper_state.json"
        if not state_file.exists():
            continue

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                paper_data = json.load(f)
            library.append(build_library_item(paper_dir, paper_data))
        except Exception as exc:
            logger.error("Error loading paper from %s: %s", paper_dir, exc)

    return library


def find_paper_dir_and_state(arxiv_id: str) -> tuple[Path, dict[str, Any]]:
    """Find a paper directory and parsed state JSON by normalized arXiv ID."""
    normalized = normalize_arxiv_id(arxiv_id)
    papers_dir = DATA_DIR / "papers"

    if not papers_dir.exists():
        raise HTTPException(status_code=404, detail="Paper not found")

    for paper_dir in papers_dir.iterdir():
        if not paper_dir.is_dir():
            continue
        state_file = paper_dir / "paper_state.json"
        if not state_file.exists():
            continue

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                paper_data = json.load(f)
            candidate = normalize_arxiv_id(str(paper_data.get("arxiv_id", "")))
            if candidate == normalized:
                return paper_dir, paper_data
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="Paper not found")

