"""Shared API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AuthorSchema(BaseModel):
    name: str
    affiliation: Optional[str] = None


class PaperSchema(BaseModel):
    arxiv_id: str
    title: str
    authors: List[AuthorSchema]
    abstract: str
    published: datetime
    updated: datetime
    categories: List[str] = Field(default_factory=list)
    primary_category: str
    pdf_url: str
    comment: Optional[str] = None
    journal_ref: Optional[str] = None
    doi: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    exact_match: bool = True
    max_results: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    papers: List[PaperSchema]


class EnqueueRequest(BaseModel):
    papers: List[PaperSchema] = Field(default_factory=list)


class EnqueueResponse(BaseModel):
    queued_count: int
    skipped_count: int


class JobSchema(BaseModel):
    arxiv_id: str
    title: str
    stage: str
    message: str
    progress: float
    is_active: bool
    queue_position: Optional[int]
    error: Optional[str]
    started_at: Optional[datetime]
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]


class JobCountsSchema(BaseModel):
    queued: int
    active: int
    completed: int
    failed: int


class JobsResponse(BaseModel):
    counts: JobCountsSchema
    jobs: List[JobSchema]


class LibraryItemSchema(BaseModel):
    title: str
    arxiv_id: str
    authors: List[dict]
    status: str
    abstract: str
    listen_status: str
    last_listened_at: Optional[str]
    arxiv_url: Optional[str] = None
    audio_url: Optional[str] = None


class LibraryContentSchema(BaseModel):
    arxiv_id: str
    summary_text: Optional[str] = None
    extract_text: Optional[str] = None


class ListenStatusUpdateRequest(BaseModel):
    listen_status: Literal["listened", "unlistened"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatStreamRequest(BaseModel):
    arxiv_ids: List[str] = Field(min_length=1, max_length=5)
    messages: List[ChatMessage] = Field(min_length=1)
