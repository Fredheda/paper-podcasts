"""Data models for extracted PDF content."""

from dataclasses import dataclass

@dataclass
class ExtractedContent:
    """Represents content extracted from a PDF using MarkItDown."""

    markdown: str  # Structured markdown content
