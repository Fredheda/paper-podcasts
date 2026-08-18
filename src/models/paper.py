"""Data models for research papers."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Author:
    """Represents a paper author."""
    name: str
    affiliation: Optional[str] = None


@dataclass
class Paper:
    """Represents a research paper from arXiv."""

    arxiv_id: str
    title: str
    authors: List[Author]
    abstract: str
    published: datetime
    updated: datetime
    categories: List[str]
    primary_category: str
    pdf_url: str
    comment: Optional[str] = None
    journal_ref: Optional[str] = None
    doi: Optional[str] = None

    # Local processing metadata
    downloaded_at: Optional[datetime] = None
    save_dir: Optional[str] = None
    pdf_filename: Optional[str] = None
    status: str = "new"  # States: new, downloading, downloaded, extracting, extracted, summarizing, summarized, generating_audio, completed, failed

    # Listen tracking metadata
    listen_status: str = "unlistened"  # States: unlistened, listened
    last_listened_at: Optional[datetime] = None

    def __post_init__(self):
        """Ensure arxiv_id is clean (without version number for storage)."""
        # Remove version number if present (e.g., "2301.12345v2" -> "2301.12345")
        if 'v' in self.arxiv_id:
            self.arxiv_id = self.arxiv_id.split('v')[0]

    @staticmethod
    def clean_filename(title: str, max_length: int = 200) -> str:
        """
        Clean a paper title for use as a filename or directory name.

        Removes invalid filename characters and normalizes whitespace.

        Args:
            title: The paper title to clean
            max_length: Maximum length for the filename (default: 200)

        Returns:
            Cleaned filename string
        """
        # Remove invalid filename characters: / \ : * ? " < > |
        invalid_chars = '/\\:*?"<>|'
        cleaned = title
        for char in invalid_chars:
            cleaned = cleaned.replace(char, '_')

        # Replace multiple spaces with single space, then spaces with underscores
        cleaned = ' '.join(cleaned.split())
        cleaned = cleaned.replace(' ', '_')

        # Limit length to avoid filesystem issues
        cleaned = cleaned[:max_length]

        return cleaned

    @property
    def cleaned_title(self) -> str:
        """Get the cleaned title for use in filenames and directories."""
        return self.clean_filename(self.title)

    @property
    def short_id(self) -> str:
        """Return the short form of the arxiv ID."""
        return self.arxiv_id

    @property
    def year(self) -> int:
        """Extract year from publication date."""
        return self.published.year

    @property
    def first_author(self) -> str:
        """Get the first author's name."""
        return self.authors[0].name if self.authors else "Unknown"

    @property
    def pdf_path(self) -> Optional[str]:
        """Get the full path to the PDF file."""
        if self.save_dir and self.pdf_filename:
            return str(Path(self.save_dir) / self.pdf_filename)
        return None

