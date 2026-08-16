"""Tests for storage-backend wiring in PaperPipeline."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.models.download_result import DownloadResult
from src.models.paper import Author, Paper
from src.pipeline.paper_pipeline import PaperPipeline


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
    )


def test_download_stage_uploads_pdf_and_saves_metadata(tmp_path):
    arxiv_service = MagicMock()
    blob_service = MagicMock()
    metadata_service = MagicMock()

    paper = _make_paper()
    pdf_path = tmp_path / "papers" / paper.cleaned_title / f"{paper.cleaned_title}.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    arxiv_service.download_paper.return_value = DownloadResult(
        pdf_path=pdf_path, save_dir=pdf_path.parent, pdf_filename=pdf_path.name,
        downloaded_at=datetime.now(),
    )

    pipe = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=MagicMock(),
        llm_service=MagicMock(),
        audio_service=MagicMock(),
        storage_dir=tmp_path,
        blob_service=blob_service,
        metadata_service=metadata_service,
    )

    pipe.process_paper(paper, stages=["download"])

    blob_service.upload_file.assert_called_once()
    args, _ = blob_service.upload_file.call_args
    blob_path, local_path = args
    assert blob_path == f"{paper.cleaned_title}/{paper.cleaned_title}.pdf"
    assert local_path == pdf_path
    metadata_service.upsert_paper.assert_called_once_with(paper)


def test_no_upload_when_blob_service_not_configured(tmp_path):
    arxiv_service = MagicMock()
    paper = _make_paper()
    pdf_path = tmp_path / "papers" / paper.cleaned_title / f"{paper.cleaned_title}.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    arxiv_service.download_paper.return_value = DownloadResult(
        pdf_path=pdf_path, save_dir=pdf_path.parent, pdf_filename=pdf_path.name,
        downloaded_at=datetime.now(),
    )

    pipe = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=MagicMock(),
        llm_service=MagicMock(),
        audio_service=MagicMock(),
        storage_dir=tmp_path,
    )

    result = pipe.process_paper(paper, stages=["download"])

    assert not result.errors
