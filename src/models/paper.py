"""Data models for research papers."""

import json
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

    def mark_listened(self, storage_dir: Path) -> None:
        """
        Mark this paper as listened and save the state to disk.

        Args:
            storage_dir: Root storage directory (e.g., "data")
        """
        self.listen_status = "listened"
        self.last_listened_at = datetime.now()
        self.save_to_disk(storage_dir)

    def mark_unlistened(self, storage_dir: Path) -> None:
        """
        Mark this paper as unlistened and save the state to disk.

        Args:
            storage_dir: Root storage directory (e.g., "data")
        """
        self.listen_status = "unlistened"
        self.last_listened_at = None
        self.save_to_disk(storage_dir)

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
            "pdf_path": self.pdf_path,
            "status": self.status,
            "listen_status": self.listen_status,
            "last_listened_at": self.last_listened_at.isoformat() if self.last_listened_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper from dictionary."""
        # Remove computed properties (they'll be automatically recreated)
        data.pop("pdf_path", None)

        # Parse datetime strings
        data["published"] = datetime.fromisoformat(data["published"])
        data["updated"] = datetime.fromisoformat(data["updated"])
        if data.get("downloaded_at"):
            data["downloaded_at"] = datetime.fromisoformat(data["downloaded_at"])
        if data.get("last_listened_at"):
            data["last_listened_at"] = datetime.fromisoformat(data["last_listened_at"])

        # Parse authors
        data["authors"] = [Author(**a) for a in data["authors"]]

        return cls(**data)

    def save_to_disk(self, storage_dir: Path) -> Path:
        """
        Save paper state to disk for persistence across runs.

        Args:
            storage_dir: Root storage directory (e.g., "data")

        Returns:
            Path to saved state file
        """
        paper_dir = storage_dir / "papers" / self.cleaned_title
        paper_dir.mkdir(parents=True, exist_ok=True)

        state_file = paper_dir / "paper_state.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

        return state_file

    @classmethod
    def load_from_disk(cls, title: str, storage_dir: Path) -> Optional["Paper"]:
        """
        Load paper state from disk using the paper title.

        Args:
            title: Paper title (will be cleaned automatically)
            storage_dir: Root storage directory (e.g., "data")

        Returns:
            Paper object if state file exists, None otherwise
        """
        cleaned_title = cls.clean_filename(title)
        state_file = storage_dir / "papers" / cleaned_title / "paper_state.json"

        if not state_file.exists():
            return None

        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)
