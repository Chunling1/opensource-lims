from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy.orm import validates

from ..extensions import db
from ..storage import validate_storage_key

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CATEGORY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
FILE_STATUSES = frozenset(
    {
        "pending",
        "scanning",
        "active",
        "rejected",
        "pending_delete",
        "deleted",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class StoredFile(db.Model):
    """File metadata only; binary content is stored outside the database."""

    __tablename__ = "stored_files"
    __table_args__ = (
        db.CheckConstraint("size_bytes >= 0", name="ck_stored_files_size_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    storage_key = db.Column(db.String(500), unique=True, nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    content_type = db.Column(
        db.String(127),
        nullable=False,
        default="application/octet-stream",
    )
    size_bytes = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="active", index=True)
    created_by = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at = db.Column(db.DateTime)

    @validates("storage_key")
    def _validate_storage_key(self, _key: str, value: str) -> str:
        return validate_storage_key(value)

    @validates("sha256")
    def _validate_sha256(self, _key: str, value: str) -> str:
        digest = str(value or "").strip().lower()
        if not _SHA256.fullmatch(digest):
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
        return digest

    @validates("size_bytes")
    def _validate_size(self, _key: str, value: int) -> int:
        size = int(value)
        if size < 0:
            raise ValueError("size_bytes must be non-negative")
        return size

    @validates("category")
    def _validate_category(self, _key: str, value: str) -> str:
        category = str(value or "").strip().lower()
        if not _CATEGORY.fullmatch(category):
            raise ValueError("category must be a portable lowercase identifier")
        return category

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        status = str(value or "").strip().lower()
        if status not in FILE_STATUSES:
            raise ValueError("unsupported stored file status")
        return status

    @validates("original_name")
    def _validate_original_name(self, _key: str, value: str) -> str:
        name = str(value or "").strip()
        if not name or any(character in name for character in ("\x00", "\r", "\n")):
            raise ValueError("original_name is empty or contains control characters")
        return name[:255]

    @validates("content_type")
    def _validate_content_type(self, _key: str, value: str) -> str:
        content_type = str(value or "application/octet-stream").strip().lower()
        if any(character in content_type for character in ("\x00", "\r", "\n")):
            raise ValueError("content_type contains control characters")
        return content_type[:127]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "storageKey": self.storage_key,
            "originalName": self.original_name,
            "contentType": self.content_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "category": self.category,
            "status": self.status,
            "createdBy": self.created_by or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
            "deletedAt": self.deleted_at.isoformat(timespec="seconds") if self.deleted_at else "",
        }
