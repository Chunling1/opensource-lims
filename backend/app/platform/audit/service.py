"""Compatibility boundary for transactional business-operation auditing."""

from ...audit import (
    add_operation_audit,
    completion_owned_by,
    edit_time_text,
    latest_operation_audit,
    records_by_edit_time,
)
from ...models import OperationAudit


def repoint_operation_audits(object_type: str, old_id: str, new_id: str) -> int:
    """Move an aggregate's audit reference without committing the transaction."""

    return OperationAudit.query.filter_by(
        object_type=object_type,
        object_id=old_id,
    ).update({"object_id": new_id}, synchronize_session=False)

__all__ = [name for name in globals() if not name.startswith("_")]
