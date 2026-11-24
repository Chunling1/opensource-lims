from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from . import (
    FileStorage,
    StorageError,
    StorageLimitExceeded,
    StoredFileInfo,
    StoredFileNotFound,
    UnsafeStorageKey,
    validate_storage_key,
)

_CATEGORY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,16}$")
_WINDOWS_DEVICE = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE)


class LocalFileStorage(FileStorage):
    """Private filesystem storage rooted outside application release folders."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        chunk_size: int = 1024 * 1024,
        directory_mode: int = 0o750,
        file_mode: int = 0o640,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        root_path = Path(root).expanduser()
        if os.path.lexists(root_path) and root_path.is_symlink():
            raise UnsafeStorageKey("storage root must not be a symbolic link")
        root_path.mkdir(parents=True, exist_ok=True)
        if not root_path.is_dir():
            raise StorageError("storage root is not a directory")

        self.root = root_path.resolve(strict=True)
        self.chunk_size = chunk_size
        self.directory_mode = directory_mode
        self.file_mode = file_mode
        self._uuid_factory = uuid_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ensure_directory(self.root / ".incoming")
        self._ensure_directory(self.root / "objects")
        self._ensure_directory(self.root / "trash")

    def store_stream(
        self,
        stream: BinaryIO,
        *,
        category: str,
        suffix: str = "",
        max_bytes: int | None = None,
    ) -> StoredFileInfo:
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        category = self._validate_category(category)
        suffix = self._normalize_suffix(suffix)
        object_id = self._uuid_factory().hex
        storage_key = (
            f"objects/{category}/{object_id[:2]}/{object_id[2:4]}/"
            f"{object_id}{suffix}"
        )
        final_path = self._path_for_key(storage_key, frozenset({"objects"}))
        self._ensure_directory(final_path.parent)

        temp_id = self._uuid_factory().hex
        temp_key = f".incoming/{temp_id}.part"
        temp_path = self._path_for_key(temp_key, frozenset({".incoming"}))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temp_path, flags, 0o600)
        final_created = False
        hasher = hashlib.sha256()
        size_bytes = 0

        try:
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = stream.read(self.chunk_size)
                    if chunk in (b"", None):
                        if chunk is None:
                            raise TypeError("binary stream returned None")
                        break
                    if not isinstance(chunk, (bytes, bytearray, memoryview)):
                        raise TypeError("binary stream returned non-bytes data")
                    chunk = bytes(chunk)
                    size_bytes += len(chunk)
                    if max_bytes is not None and size_bytes > max_bytes:
                        raise StorageLimitExceeded(
                            f"stream exceeds the {max_bytes}-byte storage limit"
                        )
                    output.write(chunk)
                    hasher.update(chunk)
                output.flush()
                os.fsync(output.fileno())

            self._assert_safe_parent(final_path)
            if os.path.lexists(final_path):
                raise StorageError("generated storage key already exists")
            os.chmod(temp_path, self.file_mode)
            os.replace(temp_path, final_path)
            final_created = True
            self._fsync_directory(final_path.parent)
            return StoredFileInfo(storage_key, size_bytes, hasher.hexdigest())
        except Exception:
            self._unlink_if_present(temp_path)
            if final_created:
                self._unlink_if_present(final_path)
            raise

    def open(self, storage_key: str) -> BinaryIO:
        path = self._path_for_key(storage_key, frozenset({"objects", "trash"}))
        self._assert_regular_file(path)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError as exc:
            raise StoredFileNotFound(storage_key) from exc
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise UnsafeStorageKey("storage key does not reference a regular file")
            return os.fdopen(descriptor, "rb")
        except Exception:
            os.close(descriptor)
            raise

    def exists(self, storage_key: str) -> bool:
        path = self._path_for_key(storage_key, frozenset({"objects", "trash"}))
        try:
            self._assert_regular_file(path)
        except StoredFileNotFound:
            return False
        return True

    def checksum(self, storage_key: str) -> tuple[int, str]:
        hasher = hashlib.sha256()
        size_bytes = 0
        with self.open(storage_key) as stream:
            while chunk := stream.read(self.chunk_size):
                size_bytes += len(chunk)
                hasher.update(chunk)
        return size_bytes, hasher.hexdigest()

    def soft_delete(self, storage_key: str) -> str:
        source = self._path_for_key(storage_key, frozenset({"objects"}))
        self._assert_regular_file(source)
        trash_id = self._uuid_factory().hex
        suffix = source.suffix if _SUFFIX.fullmatch(source.suffix) else ""
        day = self._clock().astimezone(UTC).strftime("%Y%m%d")
        trash_key = (
            f"trash/{day}/{trash_id[:2]}/{trash_id[2:4]}/{trash_id}{suffix}"
        )
        target = self._path_for_key(trash_key, frozenset({"trash"}))
        self._ensure_directory(target.parent)
        if os.path.lexists(target):
            raise StorageError("generated trash key already exists")
        self._assert_safe_parent(source)
        self._assert_safe_parent(target)
        try:
            os.replace(source, target)
        except FileNotFoundError as exc:
            raise StoredFileNotFound(storage_key) from exc
        self._fsync_directory(source.parent)
        self._fsync_directory(target.parent)
        return trash_key

    def restore(self, trash_key: str, storage_key: str) -> None:
        source = self._path_for_key(trash_key, frozenset({"trash"}))
        target = self._path_for_key(storage_key, frozenset({"objects"}))
        self._assert_regular_file(source)
        self._ensure_directory(target.parent)
        self._assert_safe_parent(target)
        if os.path.lexists(target):
            raise StorageError("restore target already exists")
        os.replace(source, target)
        self._fsync_directory(source.parent)
        self._fsync_directory(target.parent)

    def discard(self, storage_key: str) -> None:
        path = self._path_for_key(storage_key, frozenset({"objects"}))
        self._assert_regular_file(path)
        os.unlink(path)
        self._fsync_directory(path.parent)

    @staticmethod
    def _validate_category(category: str) -> str:
        value = str(category or "").strip().lower()
        if not _CATEGORY.fullmatch(value) or _WINDOWS_DEVICE.fullmatch(value):
            raise ValueError("category must be a portable lowercase identifier")
        return value

    @staticmethod
    def _normalize_suffix(suffix: str) -> str:
        value = str(suffix or "").strip().lower()
        if value and not _SUFFIX.fullmatch(value):
            raise ValueError("suffix must be a single portable file extension")
        return value

    def _path_for_key(
        self,
        storage_key: str,
        allowed_prefixes: frozenset[str],
    ) -> Path:
        safe_key = validate_storage_key(
            storage_key,
            allowed_prefixes=allowed_prefixes,
        )
        path = self.root.joinpath(*safe_key.split("/"))
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeStorageKey("storage key escapes the configured root") from exc
        return path

    def _ensure_directory(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeStorageKey("directory escapes the configured root") from exc
        current = self.root
        for part in relative.parts:
            current /= part
            try:
                metadata = os.lstat(current)
            except FileNotFoundError:
                try:
                    os.mkdir(current, self.directory_mode)
                except FileExistsError:
                    metadata = os.lstat(current)
                else:
                    os.chmod(current, self.directory_mode)
                    continue
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise UnsafeStorageKey("storage directory contains a symbolic link")

    def _assert_safe_parent(self, path: Path) -> None:
        try:
            relative = path.parent.relative_to(self.root)
        except ValueError as exc:
            raise UnsafeStorageKey("path escapes the configured root") from exc
        current = self.root
        for part in relative.parts:
            current /= part
            try:
                metadata = os.lstat(current)
            except FileNotFoundError as exc:
                raise StoredFileNotFound(str(path)) from exc
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise UnsafeStorageKey("storage path traverses a symbolic link")

    def _assert_regular_file(self, path: Path) -> None:
        self._assert_safe_parent(path)
        try:
            metadata = os.lstat(path)
        except FileNotFoundError as exc:
            raise StoredFileNotFound(str(path)) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise UnsafeStorageKey("storage key does not reference a regular file")

    @staticmethod
    def _unlink_if_present(path: Path) -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(path, flags)
        except (OSError, NotImplementedError):
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)
