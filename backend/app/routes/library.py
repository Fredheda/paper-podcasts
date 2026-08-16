"""Library content and playback routes.

These routes power the library tab:
- list processed papers
- fetch summary/full text
- stream audio
- update listened/unlistened state

Storage backend: when STORAGE_BACKEND=azure, reads/writes go through
`state.metadata_service` (Azure SQL) and `state.blob_service` (Blob Storage)
instead of the local-disk helpers in `library_store.py`. See
docs/specs/2026-08-15-paper-podcasts-deployment.md.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import FileResponse, StreamingResponse

from src.models.api_schemas import LibraryContentSchema, LibraryItemSchema, ListenStatusUpdateRequest
from src.models.paper import Paper as DomainPaper

from ..config import ARXIV_ID_PATH, DATA_DIR, STORAGE_BACKEND
from ..library_store import build_library_item, find_paper_dir_and_state, load_library_from_disk, normalize_arxiv_id
from ..state import state

router = APIRouter(prefix="/api/library", tags=["library"])


def _require_metadata_service():
    if state.metadata_service is None:
        raise HTTPException(status_code=503, detail="Azure storage backend not initialized")
    return state.metadata_service


def _require_blob_service():
    if state.blob_service is None:
        raise HTTPException(status_code=503, detail="Azure storage backend not initialized")
    return state.blob_service


def _row_to_library_item(row: dict[str, Any]) -> dict[str, Any]:
    """Shape one Azure SQL `papers` row into `build_library_item`'s dict shape."""
    arxiv_id = row["arxiv_id"]
    has_audio = row["status"] in {"audio_generated", "completed"}
    return {
        "title": row["title"],
        "arxiv_id": arxiv_id,
        "authors": json.loads(row["authors"]),
        "status": row["status"],
        "abstract": row["abstract"],
        "listen_status": row["listen_status"],
        "last_listened_at": row["last_listened_at"].isoformat() if row["last_listened_at"] else None,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "audio_url": f"/api/library/{arxiv_id}/audio" if has_audio else None,
    }


@router.get("", response_model=List[LibraryItemSchema])
def get_library() -> List[LibraryItemSchema]:
    """Return all persisted paper entries for the library list."""
    if STORAGE_BACKEND == "azure":
        rows = _require_metadata_service().list_papers()
        items = [_row_to_library_item(row) for row in rows]
    else:
        items = load_library_from_disk()
    return [LibraryItemSchema(**item) for item in items]


@router.get("/{arxiv_id}/content", response_model=LibraryContentSchema)
def get_library_content(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
) -> LibraryContentSchema:
    """Return summary text and extracted full text for a single paper."""
    if STORAGE_BACKEND == "azure":
        return _get_library_content_azure(arxiv_id)

    paper_dir, paper_data = find_paper_dir_and_state(arxiv_id)

    summary_files = list((paper_dir / "summaries").glob("summary_*.txt")) if (paper_dir / "summaries").exists() else []
    extract_files = list((paper_dir / "extracted").glob("*.md")) if (paper_dir / "extracted").exists() else []

    summary_text = summary_files[0].read_text(encoding="utf-8") if summary_files else None
    extract_text = extract_files[0].read_text(encoding="utf-8") if extract_files else None

    return LibraryContentSchema(
        arxiv_id=normalize_arxiv_id(str(paper_data.get("arxiv_id", arxiv_id))),
        summary_text=summary_text,
        extract_text=extract_text,
    )


def _get_library_content_azure(arxiv_id: str) -> LibraryContentSchema:
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = _require_metadata_service().get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    blob = _require_blob_service()
    cleaned_title = metadata["cleaned_title"]
    summary_blob = f"{cleaned_title}/summaries/summary_{cleaned_title}.txt"
    extract_blob = f"{cleaned_title}/extracted/{cleaned_title}.md"

    summary_text = blob.download(summary_blob).decode("utf-8") if blob.exists(summary_blob) else None
    extract_text = blob.download(extract_blob).decode("utf-8") if blob.exists(extract_blob) else None

    return LibraryContentSchema(arxiv_id=normalized, summary_text=summary_text, extract_text=extract_text)


@router.get("/{arxiv_id}/audio")
def stream_library_audio(arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH)):
    """Stream generated MP3 for one paper."""
    if STORAGE_BACKEND == "azure":
        return _stream_library_audio_azure(arxiv_id)

    paper_dir, _ = find_paper_dir_and_state(arxiv_id)
    audio_files = list((paper_dir / "audio").glob("*.mp3")) if (paper_dir / "audio").exists() else []
    if not audio_files:
        raise HTTPException(status_code=404, detail="Audio not found for this paper")

    audio_path = audio_files[0]
    return FileResponse(path=audio_path, media_type="audio/mpeg", filename=audio_path.name)


def _stream_library_audio_azure(arxiv_id: str) -> StreamingResponse:
    normalized = normalize_arxiv_id(arxiv_id)
    metadata = _require_metadata_service().get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    blob = _require_blob_service()
    cleaned_title = metadata["cleaned_title"]
    audio_blob = f"{cleaned_title}/audio/{cleaned_title}.mp3"
    if not blob.exists(audio_blob):
        raise HTTPException(status_code=404, detail="Audio not found for this paper")

    return StreamingResponse(blob.stream(audio_blob), media_type="audio/mpeg")


@router.post("/{arxiv_id}/listen", response_model=LibraryItemSchema)
def update_listen_status(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
    payload: ListenStatusUpdateRequest = ...,
) -> LibraryItemSchema:
    """Persist listened/unlistened state and return the updated library row."""
    if STORAGE_BACKEND == "azure":
        return _update_listen_status_azure(arxiv_id, payload)

    paper_dir, paper_data = find_paper_dir_and_state(arxiv_id)
    paper = DomainPaper.from_dict(paper_data)

    if payload.listen_status == "listened":
        paper.mark_listened(DATA_DIR)
    else:
        paper.mark_unlistened(DATA_DIR)

    state_file = paper_dir / "paper_state.json"
    with open(state_file, "r", encoding="utf-8") as f:
        updated = json.load(f)
    return LibraryItemSchema(**build_library_item(paper_dir, updated))


def _update_listen_status_azure(arxiv_id: str, payload: ListenStatusUpdateRequest) -> LibraryItemSchema:
    normalized = normalize_arxiv_id(arxiv_id)
    service = _require_metadata_service()
    metadata = service.get_paper(normalized)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    last_listened_at = datetime.now() if payload.listen_status == "listened" else None
    service.update_listen_status(normalized, payload.listen_status, last_listened_at)

    updated = service.get_paper(normalized)
    return LibraryItemSchema(**_row_to_library_item(updated))
