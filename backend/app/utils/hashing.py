"""File content hashing utilities for idempotency / dedup."""
import hashlib
from typing import BinaryIO

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_stream(stream: BinaryIO) -> str:
    """Compute sha256 of a readable binary stream without loading into RAM."""
    h = hashlib.sha256()
    while True:
        chunk = stream.read(_CHUNK_SIZE)
        if not chunk:
            break
        h.update(chunk)
    stream.seek(0)
    return h.hexdigest()
