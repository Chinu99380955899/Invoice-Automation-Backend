"""Storage service with pluggable backends (local FS or Azure Blob).

The backend is chosen via settings.storage_backend so the same service
interface works in dev (local) and production (Azure). The API and
worker layers depend only on the abstract `StorageBackend` protocol.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.exceptions import StorageError

log = get_logger(__name__)


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    """Filesystem-backed storage for dev and single-node deployments."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        # Prevent path traversal — reject any key that escapes the root.
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise StorageError("Invalid storage key")
        return candidate

    def save(self, key: str, data: bytes) -> str:
        try:
            path = self._full_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: write to tmp then rename
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)
            return str(path)
        except Exception as exc:
            log.error("local_storage_save_failed", key=key, error=str(exc))
            raise StorageError(f"Failed to save file: {exc}") from exc

    def read(self, key: str) -> bytes:
        try:
            return self._full_path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"File not found: {key}") from exc
        except Exception as exc:
            raise StorageError(f"Failed to read file: {exc}") from exc

    def delete(self, key: str) -> None:
        try:
            p = self._full_path(key)
            if p.exists():
                p.unlink()
        except Exception as exc:
            log.warning("local_storage_delete_failed", key=key, error=str(exc))


class AzureBlobStorage:
    """Azure Blob Storage backend. Initialized lazily."""

    def __init__(self, connection_string: str, container: str) -> None:
        from azure.storage.blob import BlobServiceClient  # lazy

        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container = container
        try:
            self._client.create_container(container)
        except Exception:
            # Already exists
            pass

    def save(self, key: str, data: bytes) -> str:
        try:
            blob = self._client.get_blob_client(self._container, key)
            blob.upload_blob(data, overwrite=True)
            return f"azure://{self._container}/{key}"
        except Exception as exc:
            log.error("azure_storage_save_failed", key=key, error=str(exc))
            raise StorageError(f"Failed to upload to Azure Blob: {exc}") from exc

    def read(self, key: str) -> bytes:
        try:
            blob = self._client.get_blob_client(self._container, key)
            return blob.download_blob().readall()
        except Exception as exc:
            raise StorageError(f"Failed to read from Azure Blob: {exc}") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.get_blob_client(self._container, key).delete_blob()
        except Exception as exc:
            log.warning("azure_storage_delete_failed", key=key, error=str(exc))


def get_storage() -> StorageBackend:
    """Factory returning the configured storage backend."""
    if settings.storage_backend == "azure" and settings.azure_storage_connection_string:
        return AzureBlobStorage(
            settings.azure_storage_connection_string,
            settings.azure_storage_container,
        )
    return LocalStorage(settings.local_storage_path)
