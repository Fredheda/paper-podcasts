"""Tests for the local paper_state.json -> SQLite migration script."""

import json
import sqlite3

from scripts.migrate_local_json_to_sqlite import migrate


def _write_paper_state(papers_dir, cleaned_title: str, **overrides) -> "Path":
    paper_dir = papers_dir / cleaned_title
    paper_dir.mkdir(parents=True)
    data = {
        "arxiv_id": "2301.12345",
        "title": "Test Paper",
        "authors": [{"name": "Ada Lovelace", "affiliation": None}],
        "abstract": "An abstract.",
        "published": "2023-01-15T00:00:00",
        "updated": "2023-01-15T00:00:00",
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
        "pdf_url": "https://arxiv.org/pdf/2301.12345",
        "comment": None,
        "journal_ref": None,
        "doi": None,
        "downloaded_at": None,
        "save_dir": str(paper_dir),
        "pdf_filename": f"{cleaned_title}.pdf",
        "pdf_path": str(paper_dir / f"{cleaned_title}.pdf"),
        "status": "completed",
        "listen_status": "unlistened",
        "last_listened_at": None,
    }
    data.update(overrides)
    state_file = paper_dir / "paper_state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return state_file


def test_migrate_upserts_rows_and_deletes_json(tmp_path):
    papers_dir = tmp_path / "papers"
    state_file = _write_paper_state(papers_dir, "Test_Paper")
    db_path = tmp_path / "podcasts.db"

    count = migrate(data_dir=tmp_path, db_path=db_path)

    assert count == 1
    assert not state_file.exists()

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT arxiv_id, title FROM papers").fetchone()
    conn.close()
    assert row == ("2301.12345", "Test Paper")


def test_migrate_returns_zero_when_no_papers_dir(tmp_path):
    assert migrate(data_dir=tmp_path, db_path=tmp_path / "podcasts.db") == 0


def test_migrate_handles_multiple_papers(tmp_path):
    papers_dir = tmp_path / "papers"
    _write_paper_state(papers_dir, "Paper_One", arxiv_id="1111.11111", title="Paper One")
    _write_paper_state(papers_dir, "Paper_Two", arxiv_id="2222.22222", title="Paper Two")

    count = migrate(data_dir=tmp_path, db_path=tmp_path / "podcasts.db")

    assert count == 2
