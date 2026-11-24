"""Read-only issuance labels from the current version's latest local flow evidence."""
import json
from flask import current_app
from sqlalchemy.orm import selectinload

SIGNING = '报告签发中'
SEALING = '报告盖章中'
CONFIRMING = '报告已盖章，归档中，未发放'
ISSUANCE_STATUSES = {SIGNING, SEALING, CONFIRMING}


def current_flows(reports):
    from .models import ReportEsignFlow
    targets = {r.id: r.approved_document_version_id or r.current_document_version_id
               for r in reports if r.status == '待打印' and r.id
               and (r.approved_document_version_id or r.current_document_version_id)}
    result = {}
    if not targets:
        return result
    rows = ReportEsignFlow.query.filter(ReportEsignFlow.report_id.in_(targets),
        ReportEsignFlow.id >= int(current_app.config.get('ESIGN_PROVIDER_FLOW_MIN_ID', 0)))
    rows = rows.options(selectinload(ReportEsignFlow.signers)).order_by(
        ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).all()
    for flow in rows:
        if flow.report_document_version_id == targets[flow.report_id]:
            result.setdefault(flow.report_id, flow)
    return result


def flow_label(flow):
    if not flow or flow.status in {'cancelled', 'cancelling', 'rejected', 'expired', 'superseded'}:
        return SIGNING
    try:
        snapshot = json.loads(flow.positioning_json or '{}')
    except (TypeError, ValueError):
        snapshot = {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    seal = snapshot.get('organizationSeal') or {}
    seal = seal if isinstance(seal, dict) else {}
    positions = snapshot.get('positions') or {}
    included = seal['included'] is True if 'included' in seal else (
        isinstance(positions, dict) and 'cover' in positions and 'date' in positions)
    if flow.status in {'completed', 'verified'} and included and flow.signed_file_id and flow.signed_sha256:
        return CONFIRMING
    # Legacy organization-only attempts are created only over a completed personal PDF.
    if snapshot.get('flowKind') == 'organization_seal' and snapshot.get('sourceFlowId'):
        return SEALING
    if flow.signers and all(s.status == 'signed' for s in flow.signers):
        return SEALING
    return SIGNING


def issuance_status(report):
    return flow_label(current_flows([report]).get(report.id))
