"""Result models for audio generation operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class AudioResult:
    """Result of generating audio from text."""

    audio_path: Path
    generated_at: datetime
    audio_duration_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "audio_path": str(self.audio_path),
            "generated_at": self.generated_at.isoformat(),
            "audio_duration_seconds": self.audio_duration_seconds,
        }
