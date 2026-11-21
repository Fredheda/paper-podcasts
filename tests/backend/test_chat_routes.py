"""Tests for the chat route: the paper-lookup helper, against
ArtifactStore/MetadataStore mocks, and the failing stream."""

import logging
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.routes import chat as chat_module
from backend.app.routes.chat import _load_extract
from backend.app.safe_errors import GENERIC_CHAT_ERROR
from backend.app.state import state as app_state


@pytest.fixture
def services():
    app_state.metadata_service = MagicMock()
    app_state.blob_service = MagicMock()
    yield app_state.metadata_service, app_state.blob_service
    app_state.metadata_service = None
    app_state.blob_service = None


def test_load_extract_returns_title_and_text(services):
    metadata_service, blob_service = services
    metadata_service.get_paper.return_value = {
        "title": "Test Paper",
        "cleaned_title": "Test_Paper",
    }
    blob_service.exists.return_value = True
    blob_service.download.return_value = b"extracted markdown"

    title, text = _load_extract("2301.12345")

    assert title == "Test Paper"
    assert text == "extracted markdown"
    blob_service.download.assert_called_once_with("Test_Paper/extracted/Test_Paper.md")


def test_load_extract_404s_when_metadata_missing(services):
    metadata_service, _ = services
    metadata_service.get_paper.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        _load_extract("9999.99999")

    assert exc_info.value.status_code == 404


def test_load_extract_404s_when_extract_artifact_missing(services):
    metadata_service, blob_service = services
    metadata_service.get_paper.return_value = {
        "title": "Test Paper",
        "cleaned_title": "Test_Paper",
    }
    blob_service.exists.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        _load_extract("2301.12345")

    assert exc_info.value.status_code == 404


PLANTED = (
    "RateLimitError: key sk-proj-PLANTEDKEY1234 org-PLANTEDORG99 req_PLANTEDREQ99 "
    "at https://planted.invalid/v1/chat?code=PLANTEDQUERY"
)
PLANTED_FRAGMENTS = (
    "PLANTEDKEY",
    "PLANTEDORG",
    "PLANTEDREQ",
    "planted.invalid",
    "PLANTEDQUERY",
)


class _FailingProvider:
    def __init__(self, chunks_before_error: int) -> None:
        self.chunks_before_error = chunks_before_error

    def stream_chat(self, **_: object) -> Iterator[str]:
        for i in range(self.chunks_before_error):
            yield f"chunk{i} "
        raise RuntimeError(PLANTED)


@pytest.fixture
def stream_client(monkeypatch):
    monkeypatch.setattr(chat_module, "_build_system_prompt", lambda _ids: "system")
    app = FastAPI()
    app.include_router(chat_module.router)
    return TestClient(app)


def _post(client: TestClient):
    return client.post(
        "/api/chat/stream",
        json={
            "arxiv_ids": ["2301.12345"],
            "messages": [{"role": "user", "content": "hi"}],
        },
    )


@pytest.mark.parametrize("chunks_before_error", [0, 1])
def test_stream_failure_sends_only_the_fixed_text(
    stream_client, monkeypatch, chunks_before_error
):
    monkeypatch.setattr(
        app_state, "llm_provider", _FailingProvider(chunks_before_error)
    )

    response = _post(stream_client)

    assert response.status_code == 200
    assert "event: error" in response.text
    assert GENERIC_CHAT_ERROR in response.text
    assert response.text.count("event: token") == chunks_before_error
    for fragment in (*PLANTED_FRAGMENTS, "RuntimeError", "RateLimitError"):
        assert fragment not in response.text


def test_stream_failure_logs_the_redacted_error_without_a_traceback(
    stream_client, monkeypatch, caplog
):
    monkeypatch.setattr(app_state, "llm_provider", _FailingProvider(1))
    caplog.set_level(logging.INFO)

    _post(stream_client)

    text = caplog.text
    assert "Chat stream failed: RuntimeError: " in text
    assert "[redacted-key]" in text
    assert "[redacted-url]" in text
    for fragment in PLANTED_FRAGMENTS:
        assert fragment not in text
    assert all(record.exc_info is None for record in caplog.records)
