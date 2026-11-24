from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(RuntimeError):
    """Base error for persistent file storage operations."""


class UnsafeStorageKey(StorageError, ValueError):
    """Raised when a storage key can escape or alias the configured root."""


class StoredFileNotFound(StorageError, FileNotFoundError):
    """Raised when a referenced stored object does not exist."""


class StorageLimitExceeded(StorageError, ValueError):
    """Raised when a stream exceeds its configured byte limit."""


@dataclass(frozen=True, slots=True)
class StoredFileInfo:
    storage_key: str
    size_bytes: int
    sha256: str


def validate_storage_key(
    storage_key: str,
    *,
    allowed_prefixes: frozenset[str] = frozenset({"objects", "trash"}),
) -> str:
    """Validate a portable POSIX-style relative key without normalizing it."""
    if not isinstance(storage_key, str) or not storage_key:
        raise UnsafeStorageKey("storage_key must be a non-empty string")
    if "\x00" in storage_key or "\\" in storage_key or storage_key.startswith("/"):
        raise UnsafeStorageKey("storage_key must be a POSIX-style relative path")
    parts = storage_key.split("/")
    if (
        not parts
        or parts[0] not in allowed_prefixes
        or any(part in {"", ".", ".."} for part in parts)
        or any(not _KEY_SEGMENT.fullmatch(part) for part in parts)
    ):
        raise UnsafeStorageKey("storage_key contains an unsafe path segment")
    return storage_key


class FileStorage(ABC):
    @abstractmethod
    def store_stream(
        self,
        stream: BinaryIO,
        *,
        category: str,
        suffix: str = "",
        max_bytes: int | None = None,
    ) -> StoredFileInfo:
        """Atomically persist a binary stream and return immutable metadata."""

    def store_bytes(
        self,
        data: bytes | bytearray | memoryview,
        *,
        category: str,
        suffix: str = "",
        max_bytes: int | None = None,
    ) -> StoredFileInfo:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        return self.store_stream(
            BytesIO(bytes(data)),
            category=category,
            suffix=suffix,
            max_bytes=max_bytes,
        )

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO:
        """Open a stored object for binary reading."""

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Return whether a safe key references a regular file."""

    @abstractmethod
    def checksum(self, storage_key: str) -> tuple[int, str]:
        """Stream a stored object and return its size and SHA-256."""

    @abstractmethod
    def soft_delete(self, storage_key: str) -> str:
        """Atomically move an active object into trash and return its new key."""

    @abstractmethod
    def restore(self, trash_key: str, storage_key: str) -> None:
        """Restore a trashed object to its original active key."""

    @abstractmethod
    def discard(self, storage_key: str) -> None:
        """Remove an uncommitted active object during transaction compensation."""


from .local import LocalFileStorage  # noqa: E402

__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "StorageError",
    "StorageLimitExceeded",
    "StoredFileInfo",
    "StoredFileNotFound",
    "UnsafeStorageKey",
    "validate_storage_key",
]
