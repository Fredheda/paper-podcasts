"""Search and queue/progress routes.

These routes cover the "ingestion" flow:
1) find papers
2) enqueue selected papers
3) poll queue/worker state
"""

from __future__ import annotations

from fastapi import APIRouter

from src.models.api_schemas import (
    EnqueueRequest,
    EnqueueResponse,
    JobCountsSchema,
    JobsResponse,
    JobSchema,
    SearchRequest,
    SearchResponse,
)

from ..mappers import to_domain_paper, to_paper_schema
from ..state import require_state

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/search", response_model=SearchResponse)
def search_papers(payload: SearchRequest) -> SearchResponse:
    """Search arXiv and return paper metadata for selection/enqueue."""
    arxiv_service, _ = require_state()
    papers = arxiv_service.search_by_topic(
        topic=payload.query,
        exact=payload.exact_match,
        max_results=payload.max_results,
    )
    return SearchResponse(papers=[to_paper_schema(p) for p in papers])


@router.post("/jobs/enqueue", response_model=EnqueueResponse)
def enqueue_jobs(payload: EnqueueRequest) -> EnqueueResponse:
    """Queue one or more selected papers for background pipeline processing."""
    _, processing = require_state()

    queued_count = 0
    skipped_count = 0

    for paper_schema in payload.papers:
        paper = to_domain_paper(paper_schema)
        if processing.enqueue(paper):
            queued_count += 1
        else:
            skipped_count += 1

    return EnqueueResponse(queued_count=queued_count, skipped_count=skipped_count)


@router.get("/jobs", response_model=JobsResponse)
def get_jobs() -> JobsResponse:
    """Return queue counters plus per-paper stage snapshots for frontend polling."""
    _, processing = require_state()
    counts = processing.get_counts()
    jobs = processing.get_jobs()

    return JobsResponse(
        counts=JobCountsSchema(**counts),
        jobs=[
            JobSchema(
                arxiv_id=j.arxiv_id,
                title=j.title,
                stage=j.stage,
                message=j.message,
                progress=j.progress,
                is_active=j.is_active,
                queue_position=j.queue_position,
                error=j.error,
                started_at=j.started_at,
                updated_at=j.updated_at,
                completed_at=j.completed_at,
            )
            for j in jobs
        ],
    )

