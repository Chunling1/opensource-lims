"""Compatibility boundary for metadata-backed file storage.

Consumers must use these operations instead of manipulating storage paths.
Transaction compensation and reference checks remain in the proven legacy
implementation until the owning module is extracted in a later phase.
"""

from ...functions.stored_files import (
    mark_stored_file_deleted,
    persist_bytes,
    persist_stream,
    read_file_bytes,
    safe_content_type,
    safe_file_name,
    storage_backend,
)

__all__ = [name for name in globals() if not name.startswith("_")]
