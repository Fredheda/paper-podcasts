"""Local SQLite MetadataStore -- the "local" STORAGE_BACKEND implementation.
Stdlib sqlite3 only. Same `papers` table shape as backend/sql/schema.sql
(Azure SQL), so both implementations are interchangeable from a caller's
point of view -- see MetadataStore.

Azure SQL's driver returns real datetime objects for DATETIME2 columns;
SQLite has no native datetime type and stores them as TEXT. _row_to_dict
below parses the four date columns back into datetime objects on every read
so both backends return byte-for-byte the same row shape.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..models.paper import Paper
from .metadata_store import MetadataStore

logger = logging.getLogger(__name__)

_DATETIME_COLUMNS = {"published", "last_listened_at", "created_at", "updated_at"}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id TEXT NOT NULL PRIMARY KEY,
    cleaned_title TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    abstract TEXT NOT NULL,
    published TEXT NOT NULL,
    status TEXT NOT NULL,
    listen_status TEXT NOT NULL DEFAULT 'unlistened',
    last_listened_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SqliteMetadataService(MetadataStore):
    """CRUD for the `papers` table in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for column in _DATETIME_COLUMNS:
            if result.get(column):
                result[column] = datetime.fromisoformat(result[column])
        return result

    def upsert_paper(self, paper: Paper) -> None:
        """Insert or update one paper's metadata row, keyed by arxiv_id."""
        authors_json = json.dumps(
            [{"name": a.name, "affiliation": a.affiliation} for a in paper.authors]
        )
        last_listened_at = paper.last_listened_at.isoformat() if paper.last_listened_at else None
        published = paper.published.isoformat()
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO papers
                    (arxiv_id, cleaned_title, title, authors, abstract, published,
                     status, listen_status, last_listened_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(arxiv_id) DO UPDATE SET
                    cleaned_title = excluded.cleaned_title,
                    title = excluded.title,
                    authors = excluded.authors,
                    abstract = excluded.abstract,
                    published = excluded.published,
                    status = excluded.status,
                    listen_status = excluded.listen_status,
                    last_listened_at = excluded.last_listened_at,
                    updated_at = excluded.updated_at
                """,
                (
                    paper.arxiv_id, paper.cleaned_title, paper.title, authors_json,
                    paper.abstract, published, paper.status, paper.listen_status,
                    last_listened_at, now, now,
                ),
            )
            conn.commit()
            logger.debug(f"Upserted metadata for {paper.arxiv_id}")
        finally:
            conn.close()

    def get_paper(self, arxiv_id: str) -> Optional[dict[str, Any]]:
        """Return one paper's row dict, or None if not found."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
            ).fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def list_papers(self) -> list[dict[str, Any]]:
        """Return all paper rows, most recently updated first."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM papers ORDER BY updated_at DESC").fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def update_listen_status(
        self, arxiv_id: str, listen_status: str, last_listened_at: Optional[datetime]
    ) -> None:
        """Persist a listened/unlistened change for one paper."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE papers SET listen_status = ?, last_listened_at = ?, "
                "updated_at = ? WHERE arxiv_id = ?",
                (
                    listen_status,
                    last_listened_at.isoformat() if last_listened_at else None,
                    datetime.now().isoformat(),
                    arxiv_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
