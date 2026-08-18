"""Local-filesystem ArtifactStore -- the "local" STORAGE_BACKEND
implementation. Rooted at data/papers/, stdlib only.

PaperPipeline already writes each stage's output directly under this same
root (see storage_dir/papers/<cleaned_title>/... in paper_pipeline.py), so
upload/upload_file's destination is usually the same path as the source --
that's expected, not a bug, and upload_file below is a same-path no-op in
that case. It still copies correctly for a genuinely different source (e.g.
the local library migration script).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterator

from .artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536


class LocalFileStorageService(ArtifactStore):
    """Filesystem-backed ArtifactStore rooted at `root_dir`."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        return self.root_dir / path

    def upload(self, path: str, data: bytes) -> None:
        dest = self._resolve(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.debug(f"Wrote {path} ({len(data)} bytes)")

    def upload_file(self, path: str, local_path: Path) -> None:
        dest = self._resolve(path)
        local_path = Path(local_path)
        if dest.resolve() == local_path.resolve():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, dest)
        logger.debug(f"Copied {local_path} to {path}")

    def download(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def stream(self, path: str) -> Iterator[bytes]:
        with open(self._resolve(path), "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                yield chunk

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()
