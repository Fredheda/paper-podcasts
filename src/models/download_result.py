"""Result models for download operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DownloadResult:
    """Result of downloading a paper PDF."""
    pdf_path: Path
    save_dir: Path
    pdf_filename: str
    downloaded_at: datetime
