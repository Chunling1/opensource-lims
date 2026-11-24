from __future__ import annotations

from datetime import datetime

from ..extensions import db


class SystemConfigSetting(db.Model):
    __tablename__ = "system_config_settings"

    key = db.Column(db.String(64), primary_key=True)
    value_json = db.Column(db.JSON, nullable=False, default=dict)
    updated_by = db.Column(db.String(80), nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomTemplate(db.Model):
    __tablename__ = "custom_templates"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(24), nullable=False, index=True)  # 'commission' | 'report'
    name = db.Column(db.String(120), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    stored_file_id = db.Column(db.Integer, db.ForeignKey("stored_files.id"), nullable=True)
    placeholders_json = db.Column(db.JSON, nullable=False, default=list)
    field_mapping_json = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_by = db.Column(db.String(80), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "fileName": self.file_name,
            "storedFileId": self.stored_file_id,
            "placeholders": list(self.placeholders_json or []),
            "fieldMapping": dict(self.field_mapping_json or {}),
            "isActive": bool(self.is_active),
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else "",
            "updatedAt": self.updated_at.isoformat() if self.updated_at else "",
        }
