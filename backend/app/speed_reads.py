"""Indexes and batched capability reads scoped to one read-only list invocation."""
from .preflight_reads import read_once


def standard_index(rows):
    from .standard_control import normalize_code
    def build():
        result = {}
        for row in rows:
            result.setdefault(normalize_code(row.code), []).append(row)
        return result
    return read_once('speed_standard_index', build)


def standard_candidates(rows, wanted):
    index = standard_index(rows)
    if wanted in index:
        return index[wanted]
    if not wanted:
        return []
    # Longest normalized prefix, preserving original database order within it.
    best = max((key for key in index if key and wanted.startswith(key)), key=len, default=None)
    return index.get(best, [])


def _capabilities():
    from .list_reads import _state
    state = _state.get()
    if state is None or 'scope_reports' not in state:
        return None
    def load():
        from sqlalchemy import or_
        from sqlalchemy.orm import selectinload
        from .models import StdLibraryItem, CapabilityEntry, CapabilityImportBatch, Department
        from .standard_control import normalize_code
        from .report_scope import standards_for
        from .applications.quality_resources.testing_locations import workbook_capability_owners
        standards = read_once('controlled_standard_rows', lambda:
            StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all())
        owners = workbook_capability_owners()
        owner_ids, entry_ids = set(), set()
        for report in state['scope_reports']:
            detail = report.detail or {}
            for code in standards_for(detail):
                owner_ids.update(owners.get(item.id, item.id)
                                 for item in standard_candidates(standards, normalize_code(code)))
            for value in (detail.get('rawSample') or {}).get('capabilityEntryIds') or []:
                try:
                    entry_ids.add(int(value))
                except (TypeError, ValueError):
                    pass
        by_owner, by_id = {key: [] for key in owner_ids}, {}
        owners_list, ids_list = sorted(owner_ids), sorted(entry_ids)
        for start in range(0, max(len(owners_list), len(ids_list)), 400):
            entries = CapabilityEntry.query.options(
                selectinload(CapabilityEntry.departments).load_only(Department.id, Department.name),
                selectinload(CapabilityEntry.batch).load_only(CapabilityImportBatch.id, CapabilityImportBatch.status),
            ).filter(or_(CapabilityEntry.standard_item_id.in_(owners_list[start:start+400]),
                         CapabilityEntry.id.in_(ids_list[start:start+400]))).all()
            for entry in entries:
                by_id[entry.id] = entry
        for entry in sorted(by_id.values(), key=lambda e: e.id):
            if entry.standard_item_id in by_owner:
                by_owner[entry.standard_item_id].append(entry)
        return by_owner, by_id, entry_ids
    return read_once('speed_capability_batch', load)


def linked_capabilities(owner, fallback):
    batch = _capabilities()
    return batch[0][owner] if batch is not None and owner in batch[0] else fallback()


def selected_capabilities(ids, fallback):
    batch = _capabilities()
    if batch is None or not set(ids).issubset(batch[2]):
        return fallback()
    return [batch[1][key] for key in sorted(set(ids)) if key in batch[1]]
