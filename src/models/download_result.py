"""Result models for download operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DownloadResult:
    """Result of downloading and saving a paper."""
    pdf_path: Path
    metadata_path: Path
    save_dir: Path
    pdf_filename: str
    metadata_filename: str
    downloaded_at: datetime
