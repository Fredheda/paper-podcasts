"""Abstract interface for durable artifact storage (PDF, extracted text,
summary, audio). Two implementations, selected once in backend/app/state.py
based on STORAGE_BACKEND: BlobStorageService ("azure") and
LocalFileStorageService ("local"). Both are always constructed -- callers
never check which one is active. See
docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator


class ArtifactStore(ABC):
    """Content-addressed-by-path storage for one paper's stage outputs."""

    @abstractmethod
    def upload(self, path: str, data: bytes) -> None:
        """Write `data` to `path`, overwriting anything already there."""
        ...

    @abstractmethod
    def upload_file(self, path: str, local_path: Path) -> None:
        """Copy the local file at `local_path` to `path`."""
        ...

    @abstractmethod
    def download(self, path: str) -> bytes:
        """Return the full contents of `path`."""
        ...

    @abstractmethod
    def stream(self, path: str) -> Iterator[bytes]:
        """Yield `path`'s contents in chunks, without buffering it all in memory."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return whether `path` exists."""
        ...
