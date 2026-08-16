"""Tests for storage-backend wiring in PaperPipeline. blob_service and
metadata_service are required constructor params (no STORAGE_BACKEND
branching inside the pipeline itself) -- these tests use plain MagicMocks,
which duck-type against ArtifactStore/MetadataStore fine for this purpose."""

from datetime import datetime
from unittest.mock import MagicMock

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


def _make_pipeline(tmp_path, blob_service=None, metadata_service=None):
    return PaperPipeline(
        arxiv_service=MagicMock(),
        pdf_service=MagicMock(),
        llm_service=MagicMock(),
        audio_service=MagicMock(),
        storage_dir=tmp_path,
        blob_service=blob_service or MagicMock(),
        metadata_service=metadata_service or MagicMock(),
    )


def test_download_stage_uploads_artifact_and_saves_metadata(tmp_path):
    blob_service = MagicMock()
    metadata_service = MagicMock()
    paper = _make_paper()
    pdf_path = tmp_path / "papers" / paper.cleaned_title / f"{paper.cleaned_title}.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    pipe = _make_pipeline(tmp_path, blob_service=blob_service, metadata_service=metadata_service)
    pipe.arxiv.download_paper.return_value = DownloadResult(
        pdf_path=pdf_path, save_dir=pdf_path.parent, pdf_filename=pdf_path.name,
        downloaded_at=datetime.now(),
    )

    pipe.process_paper(paper, stages=["download"])

    blob_service.upload_file.assert_called_once()
    args, _ = blob_service.upload_file.call_args
    assert args == (f"{paper.cleaned_title}/{paper.cleaned_title}.pdf", pdf_path)
    metadata_service.upsert_paper.assert_called_once_with(paper)


def test_save_paper_state_does_not_write_json_to_disk(tmp_path):
    """paper_state.json is retired -- metadata lives only in the metadata store."""
    metadata_service = MagicMock()
    pipe = _make_pipeline(tmp_path, metadata_service=metadata_service)
    paper = _make_paper()

    pipe._save_paper_state(paper)

    metadata_service.upsert_paper.assert_called_once_with(paper)
    assert not (tmp_path / "papers" / paper.cleaned_title / "paper_state.json").exists()
