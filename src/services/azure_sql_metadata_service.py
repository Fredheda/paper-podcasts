"""Azure SQL metadata store for paper-podcasts -- the "azure" STORAGE_BACKEND
implementation of MetadataStore. Replaces paper_state.json for that backend.

Adapted from Portfolio/backend/services/database_client.py's connection
pattern (copied, not imported -- no cross-project deps, per workspace
convention). Unlike that write-only client, this one needs full CRUD (reads
power the library list; writes cover status/listen-state updates), so the
granted SQL role is db_datareader + db_datawriter, not write-only -- see
sql/grant_identity.sql.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional

import mssql_python

from ..models.paper import Paper
from .metadata_store import MetadataStore

logger = logging.getLogger(__name__)

# PlaygroundDB is Azure SQL serverless (60 min auto-pause). The first query
# after a pause hits a resume window where every connection attempt raises
# OperationalError ("not currently available" / TCP timeout) until compute
# finishes waking up -- observed taking up to ~45s in practice, well beyond
# what's reasonable to block a single request on. This retry only smooths
# over the tail end of that window (a few seconds); the frontend's 2.5s poll
# loop is what actually rides out the rest of it across requests.
_CONNECT_MAX_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_SECONDS = 1.5


class AzureSqlMetadataService(MetadataStore):
    """CRUD for the `papers` table in Azure SQL (see sql/schema.sql)."""

    def __init__(self) -> None:
        self.server = os.getenv("AZURE_SQL_SERVER")
        self.database = os.getenv("AZURE_SQL_DATABASE")
        # Presence picks ActiveDirectoryMSI (deployed) over ActiveDirectoryDefault
        # (local `az login`) -- same trigger as Portfolio's database_client.py.
        self.managed_identity_client_id = os.getenv("AZURE_CLIENT_ID")
        if not self.server or not self.database:
            raise ValueError(
                "AZURE_SQL_SERVER and AZURE_SQL_DATABASE must be set to use the azure storage backend"
            )

    def _connection_string(self) -> str:
        if self.managed_identity_client_id:
            # mssql_python's connection-string parser only recognizes `Uid`
            # (-> canonical `UID`) -- `User Id` is rejected outright as an
            # unknown keyword. Confirmed against the real deployed container,
            # not just docs (the mocked unit tests only assert a substring,
            # so this slipped past them).
            auth = f"Authentication=ActiveDirectoryMSI;Uid={self.managed_identity_client_id};"
        else:
            auth = "Authentication=ActiveDirectoryDefault;"
        return f"Server={self.server};Database={self.database};{auth}Encrypt=yes;"

    def _connect(self) -> Any:
        """Open a connection, retrying a couple of times on OperationalError
        (see module-level comment on PlaygroundDB's auto-pause)."""
        for attempt in range(1, _CONNECT_MAX_ATTEMPTS + 1):
            try:
                return mssql_python.connect(self._connection_string())
            except mssql_python.OperationalError as e:
                if attempt == _CONNECT_MAX_ATTEMPTS:
                    raise
                logger.warning(
                    f"SQL connect attempt {attempt}/{_CONNECT_MAX_ATTEMPTS} failed "
                    f"(likely PlaygroundDB resuming from auto-pause), retrying in "
                    f"{_CONNECT_RETRY_DELAY_SECONDS}s: {e}"
                )
                time.sleep(_CONNECT_RETRY_DELAY_SECONDS)

    def upsert_paper(self, paper: Paper) -> None:
        """Insert or update one paper's metadata row, keyed by arxiv_id."""
        authors_json = json.dumps(
            [{"name": a.name, "affiliation": a.affiliation} for a in paper.authors]
        )
        last_listened_at = paper.last_listened_at.isoformat() if paper.last_listened_at else None
        published = paper.published.isoformat()

        params = (
            paper.arxiv_id,
            paper.cleaned_title, paper.title, authors_json, paper.abstract,
            published, paper.status, paper.listen_status, last_listened_at,
            paper.arxiv_id, paper.cleaned_title, paper.title, authors_json, paper.abstract,
            published, paper.status, paper.listen_status, last_listened_at,
        )

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                MERGE papers AS target
                USING (SELECT ? AS arxiv_id) AS source
                ON target.arxiv_id = source.arxiv_id
                WHEN MATCHED THEN UPDATE SET
                    cleaned_title = ?, title = ?, authors = ?, abstract = ?,
                    published = ?, status = ?, listen_status = ?, last_listened_at = ?,
                    updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (arxiv_id, cleaned_title, title, authors, abstract, published,
                     status, listen_status, last_listened_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME());
                """,
                params,
            )
            conn.commit()
            logger.debug(f"Upserted metadata for {paper.arxiv_id}")
        finally:
            conn.close()

    def get_paper(self, arxiv_id: str) -> Optional[dict[str, Any]]:
        """Return one paper's raw column dict, or None if not found."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [c[0] for c in cursor.description]
            return dict(zip(columns, row))
        finally:
            conn.close()

    def list_papers(self) -> list[dict[str, Any]]:
        """Return all paper rows, most recently updated first."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM papers ORDER BY updated_at DESC")
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_listen_status(
        self, arxiv_id: str, listen_status: str, last_listened_at: Optional[datetime]
    ) -> None:
        """Persist a listened/unlistened change for one paper."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE papers SET listen_status = ?, last_listened_at = ?, "
                "updated_at = SYSUTCDATETIME() WHERE arxiv_id = ?",
                (listen_status, last_listened_at.isoformat() if last_listened_at else None, arxiv_id),
            )
            conn.commit()
        finally:
            conn.close()
