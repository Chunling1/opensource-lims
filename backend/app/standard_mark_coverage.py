"""Standard authorization determines marks; parameter provenance is display only."""
from .models import CapabilityEntry
from .standard_control import capability_matches_standard, standard_authorized_marks
from .applications.quality_resources.testing_locations import (
    workbook_capability_owners, capability_accreditation,
)


def candidate_reasons(entry, item, department, when, capability_type, raw, owners):
    reasons = []
    if not capability_matches_standard(entry, item, owners):
        reasons.append('标准版本或受控来源关联不一致')
    from .authorization_scope import standard_matches_department
    if not standard_matches_department(item, department):
        reasons.append('未授权给当前部门')
    return reasons


def standard_mark_coverage(standards, department, when, capability_type, raw):
    from .standard_control import selected_controlled_standards
    controlled = [(verdict['code'], item, verdict) for item, verdict in selected_controlled_standards(standards, raw.get('standardItemIds'), department, when)]
    owners = workbook_capability_owners()
    owner_ids = {owners.get(item.id, item.id) for _, item, _ in controlled if item}
    entries = CapabilityEntry.query.filter(CapabilityEntry.standard_item_id.in_(owner_ids)).order_by(CapabilityEntry.id).all() if owner_ids else []
    groups = {}
    for entry in entries:
        groups.setdefault(entry.standard_item_id, []).append(entry)
    result = []
    for code, item, validation in controlled:
        marks, evidence, excluded = set(standard_authorized_marks(validation)), [], []
        if item and validation.get('valid'):
            for entry in groups.get(owners.get(item.id, item.id), []):
                mark = capability_accreditation(entry)
                reasons = candidate_reasons(entry, item, department, when, capability_type, raw, owners)
                row = {'id': entry.id, 'mark': mark, 'item': entry.item_name,
                       'object': entry.object_name, 'restriction': entry.restriction or '',
                       'source': entry.source_sha256, 'standard': entry.standard_code}
                if reasons:
                    excluded.append({**row, 'reasons': reasons})
                else:
                    evidence.append(row)
        result.append({'standard': code, 'standardId': item.id if item else None,
                       'marks': sorted(marks), 'evidence': evidence, 'excluded': excluded,
                       'standardValid': bool(validation.get('valid')),
                       'standardReason': validation.get('reason', '')})
    return result
