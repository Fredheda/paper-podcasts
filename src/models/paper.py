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
    metadata_filename: Optional[str] = None
    status: str = "new"  # new, downloaded, extracted, summarized, audio_generated

    def __post_init__(self):
        """Ensure arxiv_id is clean (without version number for storage)."""
        # Remove version number if present (e.g., "2301.12345v2" -> "2301.12345")
        if 'v' in self.arxiv_id:
            self.arxiv_id = self.arxiv_id.split('v')[0]

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

    @property
    def metadata_path(self) -> Optional[str]:
        """Get the full path to the metadata file."""
        if self.save_dir and self.metadata_filename:
            return str(Path(self.save_dir) / self.metadata_filename)
        return None

    def to_dict(self) -> dict:
        """Convert paper to dictionary for JSON serialization."""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": [{"name": a.name, "affiliation": a.affiliation} for a in self.authors],
            "abstract": self.abstract,
            "published": self.published.isoformat(),
            "updated": self.updated.isoformat(),
            "categories": self.categories,
            "primary_category": self.primary_category,
            "pdf_url": self.pdf_url,
            "comment": self.comment,
            "journal_ref": self.journal_ref,
            "doi": self.doi,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
            "save_dir": self.save_dir,
            "pdf_filename": self.pdf_filename,
            "metadata_filename": self.metadata_filename,
            "pdf_path": self.pdf_path,
            "metadata_path": self.metadata_path,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper from dictionary."""
        # Remove computed properties (they'll be automatically recreated)
        data.pop("pdf_path", None)
        data.pop("metadata_path", None)

        # Parse datetime strings
        data["published"] = datetime.fromisoformat(data["published"])
        data["updated"] = datetime.fromisoformat(data["updated"])
        if data.get("downloaded_at"):
            data["downloaded_at"] = datetime.fromisoformat(data["downloaded_at"])

        # Parse authors
        data["authors"] = [Author(**a) for a in data["authors"]]

        return cls(**data)
