"""Azure Blob Storage wrapper for paper artifacts (PDF, extracted text,
summary, audio). Used only when STORAGE_BACKEND=azure -- see
docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from .artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class BlobStorageService(ArtifactStore):
    """Thin wrapper over azure-storage-blob for the `paper-podcasts` container.

    Uses DefaultAzureCredential, which works locally via `az login` and in
    Azure via the container app's managed identity -- no stored keys. When
    AZURE_CLIENT_ID is set (deployed), DefaultAzureCredential's managed-identity
    step picks it up automatically; no manual auth-type branching needed here
    (unlike mssql_python's connection string in azure_sql_metadata_service.py).
    """

    def __init__(self, account_name: str, container_name: str = "paper-podcasts"):
        account_url = f"https://{account_name}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        self._client = BlobServiceClient(account_url=account_url, credential=credential)
        self._container = self._client.get_container_client(container_name)
        logger.info(f"Initialized BlobStorageService: {account_url}/{container_name}")

    def upload(self, blob_path: str, data: bytes) -> None:
        """Upload bytes to `blob_path`, overwriting any existing blob there."""
        self._container.upload_blob(name=blob_path, data=data, overwrite=True)
        logger.info(f"Uploaded blob: {blob_path} ({len(data)} bytes)")

    def upload_file(self, blob_path: str, local_path: Path) -> None:
        """Upload a local file's contents to `blob_path`."""
        with open(local_path, "rb") as f:
            self.upload(blob_path, f.read())

    def download(self, blob_path: str) -> bytes:
        """Download and return the full contents of `blob_path`."""
        return self._container.download_blob(blob_path).readall()

    def stream(self, blob_path: str) -> Iterator[bytes]:
        """Yield `blob_path`'s contents in chunks, without buffering it all in memory."""
        downloader = self._container.download_blob(blob_path)
        yield from downloader.chunks()

    def exists(self, blob_path: str) -> bool:
        """Return whether `blob_path` exists in the container."""
        return self._container.get_blob_client(blob_path).exists()
