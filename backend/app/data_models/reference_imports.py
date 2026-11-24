"""参考数据导入的批次、行认领与冲突元数据。

这些表只记录数据集标识、不可逆摘要、目标记录 ID 和冲突字段名，
不保存 JSON 原文、个人身份信息或冲突前后的字段值。
"""

from datetime import UTC, datetime

from ..extensions import db


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class LegacyImportBatch(db.Model):
    __tablename__ = "legacy_import_batches"
    __table_args__ = (
        db.UniqueConstraint("dataset", "source_sha256", name="uq_legacy_import_batch_dataset_hash"),
    )

    id = db.Column(db.Integer, primary_key=True)
    dataset = db.Column(db.String(80), nullable=False, index=True)
    source_sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="running", index=True)
    source_row_count = db.Column(db.Integer, nullable=False, default=0)
    inserted_count = db.Column(db.Integer, nullable=False, default=0)
    adopted_count = db.Column(db.Integer, nullable=False, default=0)
    conflict_count = db.Column(db.Integer, nullable=False, default=0)
    skipped_count = db.Column(db.Integer, nullable=False, default=0)
    failure_code = db.Column(db.String(120))
    started_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    completed_at = db.Column(db.DateTime)

    rows = db.relationship(
        "LegacyImportRow",
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    conflicts = db.relationship(
        "LegacyImportConflict",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class LegacyImportRow(db.Model):
    __tablename__ = "legacy_import_rows"
    __table_args__ = (
        db.UniqueConstraint("batch_id", "source_row_no", name="uq_legacy_import_row_batch_position"),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("legacy_import_batches.id"), nullable=False, index=True)
    source_row_no = db.Column(db.Integer, nullable=False)
    row_sha256 = db.Column(db.String(64), nullable=False, index=True)
    target_table = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.String(80))
    resolution = db.Column(db.String(24), nullable=False)  # inserted / adopted / conflict
    processed_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    batch = db.relationship("LegacyImportBatch", back_populates="rows")
    conflict = db.relationship(
        "LegacyImportConflict",
        back_populates="import_row",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LegacyImportConflict(db.Model):
    __tablename__ = "legacy_import_conflicts"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("legacy_import_batches.id"), nullable=False, index=True)
    import_row_id = db.Column(db.Integer, db.ForeignKey("legacy_import_rows.id"), nullable=False, unique=True)
    source_row_no = db.Column(db.Integer, nullable=False)
    row_sha256 = db.Column(db.String(64), nullable=False)
    target_table = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.String(80))
    conflict_code = db.Column(db.String(80), nullable=False, index=True)
    field_names = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    batch = db.relationship("LegacyImportBatch", back_populates="conflicts")
    import_row = db.relationship("LegacyImportRow", back_populates="conflict")
