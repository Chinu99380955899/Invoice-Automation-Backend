"""Local filesystem storage backend tests."""
import tempfile

import pytest

from app.services.storage_service import LocalStorage
from app.utils.exceptions import StorageError


def test_save_and_read_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalStorage(tmp)
        path = storage.save("a/b/test.txt", b"hello")
        assert storage.read("a/b/test.txt") == b"hello"
        assert "test.txt" in path


def test_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalStorage(tmp)
        with pytest.raises(StorageError):
            storage.save("../../etc/passwd", b"bad")
