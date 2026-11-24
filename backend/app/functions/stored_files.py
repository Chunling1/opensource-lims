from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from flask import current_app
from sqlalchemy import event
from sqlalchemy.orm import Session

from ..data_models.files import StoredFile
from ..extensions import db
from ..storage import LocalFileStorage, StorageError, StoredFileNotFound

_NEW_FILES = "lims_new_storage_files"
_TRASHED_FILES = "lims_trashed_storage_files"


@event.listens_for(Session, "after_commit")
def _clear_storage_compensation(session: Session) -> None:
    session.info.pop(_NEW_FILES, None)
    session.info.pop(_TRASHED_FILES, None)


@event.listens_for(Session, "after_rollback")
def _run_storage_compensation(session: Session) -> None:
    for storage, storage_key in session.info.pop(_NEW_FILES, []):
        try:
            storage.discard(storage_key)
        except (OSError, StorageError):
            pass
    for storage, trash_key, storage_key in reversed(session.info.pop(_TRASHED_FILES, [])):
        try:
            storage.restore(trash_key, storage_key)
        except (OSError, StorageError):
            pass


def storage_backend() -> LocalFileStorage:
    root = current_app.config.get("STORAGE_ROOT")
    if not root:
        raise RuntimeError("STORAGE_ROOT is not configured")
    return LocalFileStorage(root)


def persist_stream(
    stream: BinaryIO,
    *,
    category: str,
    original_name: str,
    content_type: str,
    created_by: str | None,
    max_bytes: int | None = None,
) -> StoredFile:
    name = safe_file_name(original_name)
    media_type = safe_content_type(content_type)
    suffix = Path(name).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,16}", suffix):
        suffix = ""
    storage = storage_backend()
    info = storage.store_stream(
        stream,
        category=category,
        suffix=suffix,
        max_bytes=max_bytes,
    )
    try:
        row = StoredFile(
            storage_key=info.storage_key,
            original_name=name,
            content_type=media_type,
            size_bytes=info.size_bytes,
            sha256=info.sha256,
            category=category,
            status="active",
            created_by=created_by,
        )
        db.session.add(row)
        db.session.flush()
        db.session().info.setdefault(_NEW_FILES, []).append((storage, info.storage_key))
        return row
    except Exception:
        try:
            storage.discard(info.storage_key)
        except (OSError, StorageError):
            pass
        raise


def persist_bytes(
    data: bytes,
    *,
    category: str,
    original_name: str,
    content_type: str,
    created_by: str | None,
    max_bytes: int | None = None,
) -> StoredFile:
    from io import BytesIO

    return persist_stream(
        BytesIO(data),
        category=category,
        original_name=original_name,
        content_type=content_type,
        created_by=created_by,
        max_bytes=max_bytes,
    )


def read_file_bytes(file_row: StoredFile | None, legacy: bytes | None = None) -> bytes:
    if file_row and file_row.status == "active":
        try:
            with storage_backend().open(file_row.storage_key) as handle:
                return handle.read()
        except StoredFileNotFound:
            if legacy is None:
                raise
    return legacy or b""


def mark_stored_file_deleted(file_row: StoredFile) -> None:
    if file_row.status != "active":
        return
    if file_row.id is not None and _active_reference_count(file_row.id) > 1:
        return
    storage = storage_backend()
    storage_key = file_row.storage_key
    trash_key = storage.soft_delete(storage_key)
    db.session().info.setdefault(_TRASHED_FILES, []).append(
        (storage, trash_key, storage_key)
    )
    file_row.storage_key = trash_key
    file_row.status = "deleted"
    file_row.deleted_at = datetime.utcnow()


def _active_reference_count(file_id: int) -> int:
    from ..models import (
        ExternalCustomerDocument,
        ReportAttachment,
        ReportDocumentVersion,
    )

    attachments = ReportAttachment.query.filter(
        ReportAttachment.file_id == file_id,
        ReportAttachment.deleted_at.is_(None),
    ).count()
    documents = ReportDocumentVersion.query.filter(
        (ReportDocumentVersion.docx_file_id == file_id)
        | (ReportDocumentVersion.pdf_file_id == file_id)
    ).count()
    customer_documents = ExternalCustomerDocument.query.filter(
        ExternalCustomerDocument.stored_file_id == file_id
    ).count()
    return attachments + documents + customer_documents


def safe_file_name(value: str, *, max_length: int = 255) -> str:
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    name = re.split(r"[\\/]", str(value or "").strip())[-1]
    name = "".join(char for char in name if char not in "\x00\r\n").strip()
    if not name:
        raise ValueError("文件名不能为空")
    if len(name) <= max_length:
        return name
    suffix = Path(name).suffix
    if suffix and len(suffix) < max_length:
        return f"{name[:max_length - len(suffix)]}{suffix}"
    return name[:max_length]


def safe_content_type(value: str, *, max_length: int = 127) -> str:
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    content_type = str(value or "application/octet-stream").strip().lower()
    if any(char in content_type for char in "\x00\r\n"):
        raise ValueError("文件类型包含非法字符")
    return content_type[:max_length]


__all__ = [
    "persist_bytes",
    "persist_stream",
    "read_file_bytes",
    "mark_stored_file_deleted",
    "safe_content_type",
    "safe_file_name",
    "storage_backend",
]
