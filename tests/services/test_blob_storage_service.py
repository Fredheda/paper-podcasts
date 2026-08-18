"""Tests for the Azure Blob Storage wrapper."""

from unittest.mock import MagicMock, patch

from src.services.blob_storage_service import BlobStorageService


def _make_service():
    with patch("src.services.blob_storage_service.DefaultAzureCredential"), \
         patch("src.services.blob_storage_service.BlobServiceClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.get_container_client.return_value = mock_container
        mock_client_cls.return_value = mock_client

        service = BlobStorageService(account_name="teststorage", container_name="paper-podcasts")
        return service, mock_client_cls, mock_container


def test_init_builds_account_url_and_container_client():
    service, mock_client_cls, mock_container = _make_service()

    _, kwargs = mock_client_cls.call_args
    assert kwargs["account_url"] == "https://teststorage.blob.core.windows.net"
    service._client.get_container_client.assert_called_once_with("paper-podcasts")


def test_upload_calls_upload_blob_with_overwrite():
    service, _, mock_container = _make_service()

    service.upload("foo/bar.txt", b"hello")

    mock_container.upload_blob.assert_called_once_with(name="foo/bar.txt", data=b"hello", overwrite=True)


def test_upload_file_reads_local_file_and_uploads_bytes(tmp_path):
    service, _, mock_container = _make_service()
    local_file = tmp_path / "sample.txt"
    local_file.write_bytes(b"paper contents")

    service.upload_file("cleaned/paper.txt", local_file)

    mock_container.upload_blob.assert_called_once_with(
        name="cleaned/paper.txt", data=b"paper contents", overwrite=True
    )


def test_download_returns_blob_bytes():
    service, _, mock_container = _make_service()
    mock_downloader = MagicMock()
    mock_downloader.readall.return_value = b"content"
    mock_container.download_blob.return_value = mock_downloader

    result = service.download("foo/bar.txt")

    assert result == b"content"
    mock_container.download_blob.assert_called_once_with("foo/bar.txt")


def test_exists_delegates_to_blob_client():
    service, _, mock_container = _make_service()
    mock_blob_client = MagicMock()
    mock_blob_client.exists.return_value = True
    mock_container.get_blob_client.return_value = mock_blob_client

    assert service.exists("foo/bar.txt") is True
    mock_container.get_blob_client.assert_called_once_with("foo/bar.txt")


def test_stream_yields_chunks_from_downloader():
    service, _, mock_container = _make_service()
    mock_downloader = MagicMock()
    mock_downloader.chunks.return_value = iter([b"chunk1", b"chunk2"])
    mock_container.download_blob.return_value = mock_downloader

    chunks = list(service.stream("foo/bar.mp3"))

    assert chunks == [b"chunk1", b"chunk2"]
