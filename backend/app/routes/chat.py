"""Chat route: stream LLM answers grounded in selected library papers."""

from __future__ import annotations

import json
import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.models.api_schemas import ChatStreamRequest

from ..config import PROMPTS_DIR
from ..library_store import find_paper_dir_and_state
from ..state import state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _load_extract(arxiv_id: str) -> tuple[str, str]:
    """Return (title, extracted markdown) for a paper; raises 404 if missing."""
    paper_dir, paper_data = find_paper_dir_and_state(arxiv_id)
    extract_files = (
        list((paper_dir / "extracted").glob("*.md"))
        if (paper_dir / "extracted").exists()
        else []
    )
    if not extract_files:
        raise HTTPException(
            status_code=404,
            detail=f"No extracted text for {arxiv_id}",
        )
    title = str(paper_data.get("title", arxiv_id))
    return title, extract_files[0].read_text(encoding="utf-8")


def _build_system_prompt(arxiv_ids: list[str]) -> str:
    template_path = PROMPTS_DIR / "chat_system.txt"
    template = template_path.read_text(encoding="utf-8")

    blocks: list[str] = []
    for aid in arxiv_ids:
        title, text = _load_extract(aid)
        blocks.append(f"=== Paper: {title} ({aid}) ===\n{text}")
    return template.format(papers_block="\n\n".join(blocks))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
def stream_chat(payload: ChatStreamRequest) -> StreamingResponse:
    if state.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not initialized")

    system_prompt = _build_system_prompt(payload.arxiv_ids)
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    provider = state.llm_provider

    def event_stream() -> Iterator[str]:
        try:
            for chunk in provider.stream_chat(
                messages=messages,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.5,
            ):
                if chunk:
                    yield _sse("token", {"text": chunk})
            yield _sse("done", {})
        except Exception as exc:
            logger.exception("Chat stream failed")
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
