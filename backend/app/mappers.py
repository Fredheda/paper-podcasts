"""Schema/domain mapping helpers.

Why this exists:
- Keeps route handlers focused on request flow.
- Centralizes conversion logic between API schema models and shared domain models.
"""

from __future__ import annotations

from src.models.api_schemas import AuthorSchema, PaperSchema
from src.models.paper import Author as DomainAuthor
from src.models.paper import Paper as DomainPaper


def to_domain_paper(paper: PaperSchema) -> DomainPaper:
    """Convert API paper payload into a domain paper model."""
    return DomainPaper(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=[DomainAuthor(name=a.name, affiliation=a.affiliation) for a in paper.authors],
        abstract=paper.abstract,
        published=paper.published,
        updated=paper.updated,
        categories=paper.categories,
        primary_category=paper.primary_category,
        pdf_url=paper.pdf_url,
        comment=paper.comment,
        journal_ref=paper.journal_ref,
        doi=paper.doi,
    )


def to_paper_schema(paper: DomainPaper) -> PaperSchema:
    """Convert domain paper model into API schema."""
    return PaperSchema(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=[AuthorSchema(name=a.name, affiliation=a.affiliation) for a in paper.authors],
        abstract=paper.abstract,
        published=paper.published,
        updated=paper.updated,
        categories=paper.categories,
        primary_category=paper.primary_category,
        pdf_url=paper.pdf_url,
        comment=paper.comment,
        journal_ref=paper.journal_ref,
        doi=paper.doi,
    )

