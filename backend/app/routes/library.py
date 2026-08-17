"""Library content and playback routes.

These routes power the library tab:
- list processed papers
- fetch summary text (full text is read on arXiv, not served here)
- stream audio
- update listened/unlistened state

Storage backend (state.metadata_service / state.blob_service) is selected
once in state.py based on STORAGE_BACKEND; every route here calls through
unconditionally -- no branching, no local-disk fallback. See
docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import StreamingResponse

from src.models.api_schemas import LibraryContentSchema, LibraryItemSchema, ListenStatusUpdateRequest

from ..arxiv_ids import normalize_arxiv_id
from ..config import ARXIV_ID_PATH
from ..state import state

router = APIRouter(prefix="/api/library", tags=["library"])


def _row_to_library_item(row: dict[str, Any]) -> dict[str, Any]:
    """Shape one metadata-store row (azure or local -- identical shape) into
    LibraryItemSchema's dict shape."""
    arxiv_id = row["arxiv_id"]
    has_audio = row["status"] in {"audio_generated", "completed"}
    return {
        "title": row["title"],
        "arxiv_id": arxiv_id,
        "authors": json.loads(row["authors"]),
        "status": row["status"],
        "listen_status": row["listen_status"],
        "last_listened_at": row["last_listened_at"].isoformat() if row["last_listened_at"] else None,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "audio_url": f"/api/library/{arxiv_id}/audio" if has_audio else None,
    }


@router.get("", response_model=List[LibraryItemSchema])
def get_library() -> List[LibraryItemSchema]:
    """Return all persisted paper entries for the library list."""
    rows = state.metadata_service.list_papers()
    return [LibraryItemSchema(**_row_to_library_item(row)) for row in rows]


@router.get("/{arxiv_id}/content", response_model=LibraryContentSchema)
def get_library_content(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
) -> LibraryContentSchema:
    """Return summary text for a single paper. Full text is read on arXiv,
    not served here -- see item.arxiv_url on the library list."""
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = state.metadata_service.get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    cleaned_title = metadata["cleaned_title"]
    summary_path = f"{cleaned_title}/summaries/summary_{cleaned_title}.txt"

    summary_text = (
        state.blob_service.download(summary_path).decode("utf-8")
        if state.blob_service.exists(summary_path)
        else None
    )

    return LibraryContentSchema(arxiv_id=normalized, summary_text=summary_text)


@router.get("/{arxiv_id}/audio")
def stream_library_audio(arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH)) -> StreamingResponse:
    """Stream generated MP3 for one paper."""
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = state.metadata_service.get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    cleaned_title = metadata["cleaned_title"]
    audio_path = f"{cleaned_title}/audio/{cleaned_title}.mp3"
    if not state.blob_service.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found for this paper")

    return StreamingResponse(state.blob_service.stream(audio_path), media_type="audio/mpeg")


@router.post("/{arxiv_id}/listen", response_model=LibraryItemSchema)
def update_listen_status(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
    payload: ListenStatusUpdateRequest = ...,
) -> LibraryItemSchema:
    """Persist listened/unlistened state and return the updated library row."""
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = state.metadata_service.get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    last_listened_at = datetime.now() if payload.listen_status == "listened" else None
    state.metadata_service.update_listen_status(normalized, payload.listen_status, last_listened_at)

    updated = state.metadata_service.get_paper(normalized)
    return LibraryItemSchema(**_row_to_library_item(updated))
