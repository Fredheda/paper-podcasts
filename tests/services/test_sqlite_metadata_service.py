"""Tests for the local SQLite MetadataStore -- real sqlite3 against
tmp_path, no mocking needed. The last test asserts row-shape parity with
AzureSqlMetadataService: date columns must come back as datetime objects on
both sides, since routes/library.py calls .isoformat() on them
unconditionally."""

from datetime import datetime

from src.models.paper import Author, Paper
from src.services.sqlite_metadata_service import SqliteMetadataService


def _make_paper(**overrides) -> Paper:
    defaults = dict(
        arxiv_id="2301.12345",
        title="Test Paper",
        authors=[Author(name="Ada Lovelace")],
        abstract="An abstract.",
        published=datetime(2023, 1, 15),
        updated=datetime(2023, 1, 15),
        categories=["cs.AI"],
        primary_category="cs.AI",
        pdf_url="https://arxiv.org/pdf/2301.12345",
        status="completed",
    )
    defaults.update(overrides)
    return Paper(**defaults)


def test_upsert_then_get_paper_roundtrips(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")

    service.upsert_paper(_make_paper())
    row = service.get_paper("2301.12345")

    assert row["arxiv_id"] == "2301.12345"
    assert row["title"] == "Test Paper"


def test_get_paper_returns_none_when_not_found(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")

    assert service.get_paper("9999.99999") is None


def test_upsert_paper_is_idempotent_on_arxiv_id(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")

    service.upsert_paper(_make_paper(status="downloaded"))
    service.upsert_paper(_make_paper(status="completed"))
    rows = service.list_papers()

    assert len(rows) == 1
    assert rows[0]["status"] == "completed"


def test_list_papers_orders_most_recently_updated_first(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")

    service.upsert_paper(_make_paper(arxiv_id="1111.11111"))
    service.upsert_paper(_make_paper(arxiv_id="2222.22222"))
    rows = service.list_papers()

    assert [r["arxiv_id"] for r in rows] == ["2222.22222", "1111.11111"]


def test_update_listen_status_persists_change(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")
    service.upsert_paper(_make_paper())
    when = datetime(2026, 8, 15, 10, 0, 0)

    service.update_listen_status("2301.12345", "listened", when)
    row = service.get_paper("2301.12345")

    assert row["listen_status"] == "listened"
    assert row["last_listened_at"] == when


def test_datetime_columns_round_trip_as_datetime_objects(tmp_path):
    service = SqliteMetadataService(db_path=tmp_path / "podcasts.db")
    service.upsert_paper(_make_paper())

    row = service.get_paper("2301.12345")
    rows = service.list_papers()

    for column in ("published", "created_at", "updated_at"):
        assert isinstance(row[column], datetime)
        assert isinstance(rows[0][column], datetime)
    assert row["last_listened_at"] is None
