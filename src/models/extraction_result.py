"""Result models for PDF extraction operations."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from .extracted_content import ExtractedContent


@dataclass
class ExtractionResult:
    """Result of extracting content from a PDF."""
    content: ExtractedContent
    saved_path: Path
    extracted_at: datetime
    character_count: int = 0

    def __post_init__(self):
        """Calculate character count if not provided."""
        if self.character_count == 0 and self.content:
            self.character_count = len(self.content.markdown)
