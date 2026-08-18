"""Shared arXiv ID normalization -- used by any route that keys off arxiv_id."""

from __future__ import annotations

import re


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Normalize arXiv IDs by removing a trailing version suffix (example: v3)."""
    return re.sub(r"v\d+$", "", arxiv_id.strip())
