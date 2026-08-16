"""Chat route: stream LLM answers grounded in selected library papers."""

from __future__ import annotations

import json
import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.models.api_schemas import ChatStreamRequest

from ..arxiv_ids import normalize_arxiv_id
from ..config import PROMPTS_DIR
from ..state import state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _load_extract(arxiv_id: str) -> tuple[str, str]:
    """Return (title, extracted markdown) for a paper; raises 404 if missing."""
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = state.metadata_service.get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"No extracted text for {arxiv_id}")

    cleaned_title = metadata["cleaned_title"]
    extract_path = f"{cleaned_title}/extracted/{cleaned_title}.md"
    if not state.blob_service.exists(extract_path):
        raise HTTPException(status_code=404, detail=f"No extracted text for {arxiv_id}")

    text = state.blob_service.download(extract_path).decode("utf-8")
    return str(metadata["title"]), text


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
