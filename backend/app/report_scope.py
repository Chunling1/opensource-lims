"""Standard authorization and parameter library membership, separate from seal approval."""
import hashlib

from .preflight_reads import reuse_existing_preflight_reads
import json
import re
from datetime import date
from .models import CapabilityEntry
from .seal_requirements import requested_seal
from .standard_control import find_controlled_standard, split_standard_codes, standard_scope_failures, standard_authorized_marks
from .applications.quality_resources.testing_locations import (
    capability_accreditation, capability_address,
)

VERSION = 'standard-identity-paired-v7'


def report_seal(detail):
    resolution = detail.get('complianceResolution') or {}
    if 'finalSeal' in resolution:
        return str(resolution['finalSeal'] or '')
    review = detail.get('contractReview') or {}
    if review.get('sealRequirement'):
        return str(review['sealRequirement'])
    raw = detail.get('rawSample') or {}
    if raw.get('seal'):
        return str(raw['seal'])
    for source in (review, detail.get('sampleConfiguration') or {}):
        if 'requiredCma' in source or 'requiredCnas' in source:
            return '+'.join(m for k, m in [('requiredCma', 'CMA'), ('requiredCnas', 'CNAS')] if source.get(k))
    for section in detail.get('summary') or []:
        if section.get('title') == '委托信息':
            for field in section.get('fields') or []:
                if len(field) > 1 and field[0] == '盖章要求':
                    return str(field[1] or '')
    return str((detail.get('checkInput') or {}).get('seal') or '')


def standards_for(detail):
    from .report_standard_selection import standards_for_authorization
    return standards_for_authorization(detail)


def _date(value):
    try:
        return date.fromisoformat(str(value or '')[:10])
    except ValueError:
        return None


@reuse_existing_preflight_reads
def assess_scope(report):
    """Read-only classification. Missing evidence is NOT proof of accreditation or exclusion."""
    d = report.detail or {}; raw = d.get('rawSample') or {}; ci = d.get('checkInput') or {}
    when = _date(ci.get('testDate') or raw.get('sendDate') or raw.get('entrustDate')) or date.today()
    standards = standards_for(d)
    at = when or date.today()
    from .standard_control import selected_controlled_standards
    controlled = selected_controlled_standards(standards, raw.get('standardItemIds'), report.department, at)
    ids, errors, pending, rows = [], [], [], []
    for value in raw.get('capabilityEntryIds') or []:
        try:
            ids.append(int(value))
        except (ValueError, TypeError):
            pending.append('能力项目编号无效')
    from .list_reads import capability_entries
    entries = capability_entries(ids, lambda: CapabilityEntry.query.filter(CapabilityEntry.id.in_(ids)).all()) if ids else []
    by_id = {e.id: e for e in entries}
    requested = requested_seal(d)
    marks = [mark for mark in ('CMA', 'CNAS') if mark in requested.upper()]
    standard_rows = []
    if not standards:
        pending.append('未填写检测依据')
    for item, result in controlled:
        code = result["code"]
        failures = standard_scope_failures(result, marks)
        reasons = [f['message'] for f in failures]
        standard_rows.append({'standard': code, 'valid': not failures, 'reasons': reasons,
            'marks': standard_authorized_marks(result),
            'singleList': bool(result.get('singleList'))})
        (pending if result.get('identityUnresolved') else errors).extend(code + '：' + reason for reason in reasons)
    for eid in dict.fromkeys(ids):
        entry = by_id.get(eid)
        if not entry:
            pending.append(f'参数记录 {eid} 不存在，无法确认库内身份')
            continue
        reasons = []
        rows.append({'id': eid, 'standard': entry.standard_code, 'object': entry.object_name,
            'item': entry.item_name, 'matchedStandard': entry.standard_code,
            'site': entry.site, 'mark': capability_accreditation(entry), 'valid': True,
            'inLibrary': True, 'reasons': reasons, 'pending': [], 'restriction': entry.restriction or '',
            'effectiveDate': str(entry.effective_date or ''), 'expiresOn': str(entry.expires_on or ''),
            'source': entry.source_sha256, 'address': capability_address(entry)})
    state = 'out_of_scope' if errors else ('needs_review' if pending else 'in_scope')
    evidence = {'version': VERSION, 'department': report.department, 'standards': standards,
                'date': str(when or ''), 'requestedSeal': requested, 'standardRows': standard_rows, 'raw': {k: raw.get(k) for k in ('capabilityEntryIds', 'manualCapabilityItems', 'testLocation', 'actualTestLocations', 'isOnsiteTesting', 'onsiteTestLocation')},
                'controlled': [(item.id if item else None, result) for item, result in controlled], 'rows': rows,
                'state': state, 'errors': errors, 'pending': pending}
    fingerprint = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    from .audit import latest_operation_audit
    review_row = latest_operation_audit('report', report.report_no, 'report.scope.review')
    override = (review_row.after_data or {}) if review_row else {}
    applied = bool(override.get('fingerprint') == fingerprint and override.get('decision') in ('in_scope', 'out_of_scope'))
    effective = override['decision'] if applied else state
    return {'state': effective, 'computedState': state, 'outOfScope': effective == 'out_of_scope',
            'note': override.get('reason', '') if applied else '；'.join(errors + pending), 'rows': rows, 'standardRows': standard_rows,
            'fingerprint': fingerprint, 'reviewApplied': applied,
            'reviewStale': bool(override.get('decision') in ('in_scope', 'out_of_scope') and not applied), 'review': override,
            'seal': report_seal(d)}


def scope_projection(report):
    # Request-local display reuse only. No cross-request authorization cache.
    from flask import g, has_request_context
    if not has_request_context():
        return assess_scope(report)
    cache = getattr(g, '_report_scope_display', None)
    if cache is None:
        cache = {}; g._report_scope_display = cache
    key = (report.id, json.dumps(report.detail or {}, sort_keys=True, default=str), report.department, report.template)
    if key not in cache:
        cache[key] = assess_scope(report)
    return cache[key]
