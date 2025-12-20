"""Data models for paper summaries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PaperSummary:
    """Represents a generated summary of a research paper."""

    arxiv_id: str
    summary_text: str
    prompt_name: str
    model_name: str
    generated_at: datetime
    token_count: Optional[int] = None
    temperature: float = 0.7
    max_tokens: int = 4096

    def to_dict(self) -> dict:
        """Convert summary to dictionary for JSON serialization."""
        return {
            "arxiv_id": self.arxiv_id,
            "summary_text": self.summary_text,
            "prompt_name": self.prompt_name,
            "model_name": self.model_name,
            "generated_at": self.generated_at.isoformat(),
            "token_count": self.token_count,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperSummary":
        """Create PaperSummary from dictionary."""
        data["generated_at"] = datetime.fromisoformat(data["generated_at"])
        return cls(**data)
