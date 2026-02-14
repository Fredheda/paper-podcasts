"""Library content and playback routes.

These routes power the library tab:
- list processed papers
- fetch summary/full text
- stream audio
- update listened/unlistened state
"""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import FileResponse

from src.models.api_schemas import LibraryContentSchema, LibraryItemSchema, ListenStatusUpdateRequest
from src.models.paper import Paper as DomainPaper

from ..config import ARXIV_ID_PATH, DATA_DIR
from ..library_store import build_library_item, find_paper_dir_and_state, load_library_from_disk, normalize_arxiv_id

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("", response_model=List[LibraryItemSchema])
def get_library() -> List[LibraryItemSchema]:
    """Return all persisted paper entries for the library list."""
    return [LibraryItemSchema(**item) for item in load_library_from_disk()]


@router.get("/{arxiv_id}/content", response_model=LibraryContentSchema)
def get_library_content(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
) -> LibraryContentSchema:
    """Return summary text and extracted full text for a single paper."""
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


@router.get("/{arxiv_id}/audio")
def stream_library_audio(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
) -> FileResponse:
    """Stream generated MP3 for one paper."""
    paper_dir, _ = find_paper_dir_and_state(arxiv_id)
    audio_files = list((paper_dir / "audio").glob("*.mp3")) if (paper_dir / "audio").exists() else []
    if not audio_files:
        raise HTTPException(status_code=404, detail="Audio not found for this paper")

    audio_path = audio_files[0]
    return FileResponse(path=audio_path, media_type="audio/mpeg", filename=audio_path.name)


@router.post("/{arxiv_id}/listen", response_model=LibraryItemSchema)
def update_listen_status(
    arxiv_id: str = ApiPath(..., **ARXIV_ID_PATH),
    payload: ListenStatusUpdateRequest = ...,
) -> LibraryItemSchema:
    """Persist listened/unlistened state and return the updated library row."""
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

