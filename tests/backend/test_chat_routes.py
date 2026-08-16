"""Tests for the chat route's paper-lookup helper, against
ArtifactStore/MetadataStore mocks."""

from unittest.mock import MagicMock

import pytest

from backend.app.routes.chat import _load_extract
from backend.app.state import state as app_state
from fastapi import HTTPException


@pytest.fixture
def services():
    app_state.metadata_service = MagicMock()
    app_state.blob_service = MagicMock()
    yield app_state.metadata_service, app_state.blob_service
    app_state.metadata_service = None
    app_state.blob_service = None


def test_load_extract_returns_title_and_text(services):
    metadata_service, blob_service = services
    metadata_service.get_paper.return_value = {"title": "Test Paper", "cleaned_title": "Test_Paper"}
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
    metadata_service.get_paper.return_value = {"title": "Test Paper", "cleaned_title": "Test_Paper"}
    blob_service.exists.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        _load_extract("2301.12345")

    assert exc_info.value.status_code == 404
