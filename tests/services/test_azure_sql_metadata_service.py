"""Tests for the Azure SQL metadata service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.paper import Author, Paper
from src.services.azure_sql_metadata_service import AzureSqlMetadataService


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AZURE_SQL_SERVER", "test-server.database.windows.net")
    monkeypatch.setenv("AZURE_SQL_DATABASE", "PlaygroundDB")
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)


def _make_paper() -> Paper:
    return Paper(
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


def test_init_raises_without_server_or_database(monkeypatch):
    monkeypatch.delenv("AZURE_SQL_SERVER", raising=False)
    monkeypatch.delenv("AZURE_SQL_DATABASE", raising=False)
    with pytest.raises(ValueError):
        AzureSqlMetadataService()


def test_connection_string_uses_msi_when_client_id_present(env, monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "abc-123")
    service = AzureSqlMetadataService()
    conn_str = service._connection_string()
    assert "Authentication=ActiveDirectoryMSI;User Id=abc-123;" in conn_str


def test_connection_string_uses_default_auth_locally(env):
    service = AzureSqlMetadataService()
    conn_str = service._connection_string()
    assert "Authentication=ActiveDirectoryDefault;" in conn_str


def test_upsert_paper_executes_merge_with_18_params(env):
    with patch("src.services.azure_sql_metadata_service.mssql_python") as mock_mssql:
        mock_conn = MagicMock()
        mock_mssql.connect.return_value = mock_conn
        service = AzureSqlMetadataService()

        service.upsert_paper(_make_paper())

        mock_conn.cursor.return_value.execute.assert_called_once()
        args, _ = mock_conn.cursor.return_value.execute.call_args
        sql, params = args
        assert "MERGE papers" in sql
        assert len(params) == 18
        assert params[0] == "2301.12345"
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


def test_get_paper_returns_none_when_not_found(env):
    with patch("src.services.azure_sql_metadata_service.mssql_python") as mock_mssql:
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = None
        mock_mssql.connect.return_value = mock_conn
        service = AzureSqlMetadataService()

        assert service.get_paper("9999.99999") is None


def test_get_paper_maps_row_to_dict(env):
    with patch("src.services.azure_sql_metadata_service.mssql_python") as mock_mssql:
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.description = [("arxiv_id",), ("title",)]
        mock_cursor.fetchone.return_value = ("2301.12345", "Test Paper")
        mock_mssql.connect.return_value = mock_conn
        service = AzureSqlMetadataService()

        result = service.get_paper("2301.12345")

        assert result == {"arxiv_id": "2301.12345", "title": "Test Paper"}


def test_list_papers_maps_all_rows(env):
    with patch("src.services.azure_sql_metadata_service.mssql_python") as mock_mssql:
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.description = [("arxiv_id",), ("title",)]
        mock_cursor.fetchall.return_value = [("id1", "Title 1"), ("id2", "Title 2")]
        mock_mssql.connect.return_value = mock_conn
        service = AzureSqlMetadataService()

        result = service.list_papers()

        assert result == [
            {"arxiv_id": "id1", "title": "Title 1"},
            {"arxiv_id": "id2", "title": "Title 2"},
        ]


def test_update_listen_status_executes_update(env):
    with patch("src.services.azure_sql_metadata_service.mssql_python") as mock_mssql:
        mock_conn = MagicMock()
        mock_mssql.connect.return_value = mock_conn
        service = AzureSqlMetadataService()

        service.update_listen_status("2301.12345", "listened", datetime(2026, 8, 15, 10, 0, 0))

        mock_conn.cursor.return_value.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
