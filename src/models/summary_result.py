"""Result models for summarization operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SummaryResult:
    """Result of summarizing a paper."""
    summary_text: str
    saved_path: Path
    summarized_at: datetime

    def to_dict(self) -> dict:
        """Convert summary result to dictionary for JSON serialization."""
        return {
            "summary_text": self.summary_text,
            "saved_path": str(self.saved_path),
            "summarized_at": self.summarized_at.isoformat(),
        }
