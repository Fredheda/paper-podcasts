"""Tests for the library routes, against ArtifactStore/MetadataStore mocks.
Backend-agnostic -- no STORAGE_BACKEND branching in the routes themselves,
so there's only one test file (unlike the old azure-only variant)."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routes.library import router
from backend.app.state import state as app_state


@pytest.fixture
def client():
    app_state.metadata_service = MagicMock()
    app_state.blob_service = MagicMock()
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app), app_state.metadata_service, app_state.blob_service
    app_state.metadata_service = None
    app_state.blob_service = None


def _row(**overrides):
    row = {
        "arxiv_id": "2301.12345",
        "cleaned_title": "Test_Paper",
        "title": "Test Paper",
        "authors": '[{"name": "Ada Lovelace", "affiliation": null}]',
        "abstract": "An abstract.",
        "status": "completed",
        "listen_status": "unlistened",
        "last_listened_at": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    row.update(overrides)
    return row


def test_get_library_reads_from_metadata_service(client):
    test_client, metadata_service, _ = client
    metadata_service.list_papers.return_value = [_row()]

    response = test_client.get("/api/library")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["arxiv_id"] == "2301.12345"
    assert body[0]["audio_url"] == "/api/library/2301.12345/audio"
    assert "abstract" not in body[0]


def test_get_library_content_streams_from_artifact_store(client):
    test_client, metadata_service, blob_service = client
    metadata_service.get_paper.return_value = _row()
    blob_service.exists.return_value = True
    blob_service.download.return_value = b"summary text"

    response = test_client.get("/api/library/2301.12345/content")

    assert response.status_code == 200
    assert response.json()["summary_text"] == "summary text"
    blob_service.download.assert_any_call("Test_Paper/summaries/summary_Test_Paper.txt")


def test_get_library_content_404_when_metadata_missing(client):
    test_client, metadata_service, _ = client
    metadata_service.get_paper.return_value = None

    response = test_client.get("/api/library/9999.99999/content")

    assert response.status_code == 404


def test_stream_audio_returns_404_when_artifact_missing(client):
    test_client, metadata_service, blob_service = client
    metadata_service.get_paper.return_value = _row()
    blob_service.exists.return_value = False

    response = test_client.get("/api/library/2301.12345/audio")

    assert response.status_code == 404


def test_stream_audio_without_range_returns_full_body_with_length(client):
    test_client, metadata_service, blob_service = client
    metadata_service.get_paper.return_value = _row()
    blob_service.exists.return_value = True
    blob_service.download.return_value = b"0123456789"

    response = test_client.get("/api/library/2301.12345/audio")

    assert response.status_code == 200
    assert response.content == b"0123456789"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "10"


def test_stream_audio_honors_range_header(client):
    test_client, metadata_service, blob_service = client
    metadata_service.get_paper.return_value = _row()
    blob_service.exists.return_value = True
    blob_service.download.return_value = b"0123456789"

    response = test_client.get(
        "/api/library/2301.12345/audio", headers={"Range": "bytes=2-4"}
    )

    assert response.status_code == 206
    assert response.content == b"234"
    assert response.headers["content-range"] == "bytes 2-4/10"
    assert response.headers["content-length"] == "3"


def test_stream_audio_range_past_end_returns_416(client):
    test_client, metadata_service, blob_service = client
    metadata_service.get_paper.return_value = _row()
    blob_service.exists.return_value = True
    blob_service.download.return_value = b"0123456789"

    response = test_client.get(
        "/api/library/2301.12345/audio", headers={"Range": "bytes=999-"}
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == "bytes */10"


def test_update_listen_status_writes_to_metadata_service(client):
    test_client, metadata_service, _ = client
    metadata_service.get_paper.side_effect = [_row(), _row(listen_status="listened")]

    response = test_client.post(
        "/api/library/2301.12345/listen", json={"listen_status": "listened"}
    )

    assert response.status_code == 200
    assert response.json()["listen_status"] == "listened"
    metadata_service.update_listen_status.assert_called_once()
    args, _ = metadata_service.update_listen_status.call_args
    assert args[0] == "2301.12345"
    assert args[1] == "listened"


def test_update_listen_status_404_when_paper_missing(client):
    test_client, metadata_service, _ = client
    metadata_service.get_paper.return_value = None

    response = test_client.post(
        "/api/library/9999.99999/listen", json={"listen_status": "listened"}
    )

    assert response.status_code == 404
