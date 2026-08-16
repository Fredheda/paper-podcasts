"""Abstract interface for paper metadata storage (status, listen state).
Two implementations, selected once in backend/app/state.py based on
STORAGE_BACKEND: AzureSqlMetadataService ("azure") and
SqliteMetadataService ("local"). Both are always constructed -- callers
never check which one is active, and both return byte-for-byte the same row
shape (datetime columns come back as datetime objects on both sides). See
docs/specs/2026-08-15-paper-podcasts-deployment.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from ..models.paper import Paper


class MetadataStore(ABC):
    """CRUD for one paper's metadata row, keyed by arxiv_id."""

    @abstractmethod
    def upsert_paper(self, paper: Paper) -> None:
        """Insert or update one paper's metadata row."""
        ...

    @abstractmethod
    def get_paper(self, arxiv_id: str) -> Optional[dict[str, Any]]:
        """Return one paper's row dict, or None if not found."""
        ...

    @abstractmethod
    def list_papers(self) -> list[dict[str, Any]]:
        """Return all paper rows, most recently updated first."""
        ...

    @abstractmethod
    def update_listen_status(
        self, arxiv_id: str, listen_status: str, last_listened_at: Optional[datetime]
    ) -> None:
        """Persist a listened/unlistened change for one paper."""
        ...
