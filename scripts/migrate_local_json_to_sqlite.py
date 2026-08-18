"""One-time migration: local paper_state.json files -> local SQLite database.

Run once, locally, after upgrading to the SQLite-backed local storage
backend. NOT part of deploy or the cloud store -- this only touches the
`local` STORAGE_BACKEND's data (spec decision #9), and is entirely separate
from decision #4's cloud store, which always starts empty regardless of
local state. See docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md.

Deletes each paper_state.json after a successful upsert. Fails loudly (and
leaves that paper's JSON file in place) on any error for that paper, rather
than deleting first and upserting second.

Usage: poetry run python scripts/migrate_local_json_to_sqlite.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.paper import Author, Paper  # noqa: E402
from src.services.sqlite_metadata_service import SqliteMetadataService  # noqa: E402


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def migrate(data_dir: Path, db_path: Path) -> int:
    """Upsert every data_dir/papers/*/paper_state.json into SQLite, deleting
    each JSON file after a successful upsert. Returns the count migrated."""
    metadata_service = SqliteMetadataService(db_path=db_path)
    papers_dir = data_dir / "papers"
    if not papers_dir.exists():
        return 0

    migrated = 0
    for paper_dir in sorted(papers_dir.iterdir()):
        if not paper_dir.is_dir():
            continue
        state_file = paper_dir / "paper_state.json"
        if not state_file.exists():
            continue

        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.pop("pdf_path", None)
        data.pop("downloaded_at", None)
        data.pop("save_dir", None)
        data.pop("pdf_filename", None)
        data["published"] = _parse_dt(data["published"])
        data["updated"] = _parse_dt(data["updated"])
        data["last_listened_at"] = _parse_dt(data.get("last_listened_at"))
        data["authors"] = [Author(**a) for a in data["authors"]]
        paper = Paper(**data)

        metadata_service.upsert_paper(paper)
        state_file.unlink()
        migrated += 1
        print(f"Migrated {paper.arxiv_id} ({paper.cleaned_title})")

    return migrated


if __name__ == "__main__":
    db_path = REPO_ROOT / "data" / "podcasts.db"
    count = migrate(data_dir=REPO_ROOT / "data", db_path=db_path)
    print(f"Migrated {count} paper(s) into {db_path}")
