"""Tests for the local-filesystem ArtifactStore -- exercised against real
tmp_path fixtures, no mocking needed (there's no external system here)."""

from src.services.local_file_storage_service import LocalFileStorageService


def test_upload_and_download_roundtrip(tmp_path):
    service = LocalFileStorageService(root_dir=tmp_path)

    service.upload("foo/bar.txt", b"hello")

    assert service.download("foo/bar.txt") == b"hello"


def test_exists_true_and_false(tmp_path):
    service = LocalFileStorageService(root_dir=tmp_path)

    assert service.exists("missing.txt") is False
    service.upload("present.txt", b"x")
    assert service.exists("present.txt") is True


def test_upload_file_copies_a_local_file_into_the_store(tmp_path):
    root = tmp_path / "root"
    source = tmp_path / "source.txt"
    source.write_bytes(b"paper contents")
    service = LocalFileStorageService(root_dir=root)

    service.upload_file("cleaned/paper.txt", source)

    assert (root / "cleaned" / "paper.txt").read_bytes() == b"paper contents"


def test_upload_file_is_a_noop_when_source_is_already_the_destination(tmp_path):
    """PaperPipeline writes stage outputs directly under this same root, so
    _upload_artifact's blob_path always resolves back to local_path itself
    for this backend -- upload_file must not error or truncate in that case."""
    service = LocalFileStorageService(root_dir=tmp_path)
    dest = tmp_path / "cleaned" / "paper.pdf"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"original")

    service.upload_file("cleaned/paper.pdf", dest)

    assert dest.read_bytes() == b"original"


def test_stream_yields_full_contents_in_chunks(tmp_path):
    service = LocalFileStorageService(root_dir=tmp_path)
    service.upload("audio.mp3", b"x" * 200_000)

    chunks = list(service.stream("audio.mp3"))

    assert b"".join(chunks) == b"x" * 200_000
    assert len(chunks) > 1
