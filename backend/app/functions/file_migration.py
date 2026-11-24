from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ..data_models.files import StoredFile
from ..storage import FileStorage, StorageError


class LegacyFileMigrationError(RuntimeError):
    """Raised when legacy bytes cannot be reconciled with stored metadata."""


class LegacyFileMismatch(LegacyFileMigrationError):
    """Raised when existing metadata or disk content differs from legacy bytes."""


@dataclass(frozen=True, slots=True)
class FileMigrationResult:
    stored_file: StoredFile
    created: bool
    repaired: bool = False


def migrate_legacy_bytes(
    session: Session,
    storage: FileStorage,
    legacy_bytes: bytes | bytearray | memoryview | None,
    *,
    category: str,
    original_name: str,
    content_type: str = "application/octet-stream",
    created_by: str | None = None,
    existing: StoredFile | None = None,
    suffix: str | None = None,
    max_bytes: int | None = None,
) -> FileMigrationResult:
    """Persist legacy bytes without clearing their original database column.

    Repeated calls reuse only an explicitly supplied row. Different business
    records receive independent metadata and object keys so deleting one owner
    cannot invalidate another. The caller owns the surrounding transaction.
    """
    if legacy_bytes is None:
        raise LegacyFileMigrationError("legacy binary column is null")
    if not isinstance(legacy_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("legacy_bytes must be bytes-like")

    data = bytes(legacy_bytes)
    digest = hashlib.sha256(data).hexdigest()
    size_bytes = len(data)
    display_name = _safe_display_name(original_name)
    media_type = _safe_content_type(content_type)
    normalized_category = str(category or "").strip().lower()
    file_suffix = Path(display_name).suffix if suffix is None else suffix

    candidate = existing
    if candidate is not None:
        _assert_metadata_matches(candidate, digest, size_bytes, normalized_category)
        if storage.exists(candidate.storage_key):
            actual_size, actual_digest = storage.checksum(candidate.storage_key)
            if (actual_size, actual_digest) != (size_bytes, digest):
                raise LegacyFileMismatch("stored object checksum differs from legacy bytes")
            return FileMigrationResult(candidate, created=False)
        return _repair_missing_object(
            session,
            storage,
            candidate,
            data,
            category=normalized_category,
            suffix=file_suffix,
            max_bytes=max_bytes,
        )

    info = storage.store_bytes(
        data,
        category=normalized_category,
        suffix=file_suffix,
        max_bytes=max_bytes,
    )
    try:
        stored_file = StoredFile(
            storage_key=info.storage_key,
            original_name=display_name,
            content_type=media_type,
            size_bytes=info.size_bytes,
            sha256=info.sha256,
            category=normalized_category,
            status="active",
            created_by=created_by,
        )
        session.add(stored_file)
        session.flush()
    except Exception:
        _quarantine_uncommitted(storage, info.storage_key)
        raise
    return FileMigrationResult(stored_file, created=True)


def _repair_missing_object(
    session: Session,
    storage: FileStorage,
    stored_file: StoredFile,
    data: bytes,
    *,
    category: str,
    suffix: str,
    max_bytes: int | None,
) -> FileMigrationResult:
    info = storage.store_bytes(
        data,
        category=category,
        suffix=suffix,
        max_bytes=max_bytes,
    )
    try:
        stored_file.storage_key = info.storage_key
        stored_file.size_bytes = info.size_bytes
        stored_file.sha256 = info.sha256
        stored_file.status = "active"
        stored_file.deleted_at = None
        session.flush()
    except Exception:
        _quarantine_uncommitted(storage, info.storage_key)
        raise
    return FileMigrationResult(stored_file, created=False, repaired=True)


def _assert_metadata_matches(
    stored_file: StoredFile,
    digest: str,
    size_bytes: int,
    category: str,
) -> None:
    if (
        stored_file.sha256 != digest
        or stored_file.size_bytes != size_bytes
        or stored_file.category != category
        or stored_file.status != "active"
    ):
        raise LegacyFileMismatch("existing file metadata differs from legacy bytes")


def _safe_display_name(value: str) -> str:
    name = re.split(r"[\\/]", str(value or "").strip())[-1]
    name = "".join(character for character in name if character not in "\x00\r\n").strip()
    if not name:
        raise LegacyFileMigrationError("legacy file name is empty")
    return name[:255]


def _safe_content_type(value: str) -> str:
    content_type = str(value or "application/octet-stream").strip().lower()
    if any(character in content_type for character in "\x00\r\n"):
        raise LegacyFileMigrationError("legacy content type contains control characters")
    return content_type[:127]


def _quarantine_uncommitted(storage: FileStorage, storage_key: str) -> None:
    try:
        storage.discard(storage_key)
    except (OSError, StorageError):
        pass


__all__ = [
    "FileMigrationResult",
    "LegacyFileMigrationError",
    "LegacyFileMismatch",
    "migrate_legacy_bytes",
]
