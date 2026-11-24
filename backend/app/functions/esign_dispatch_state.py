"""Persisted create boundary shared by dispatch, withdrawal and local undo."""
import json
from datetime import datetime

# Compatibility for old tasks without a persisted create boundary. These are
# raised before create-by-file, or are an explicit provider rejection.
LEGACY_UNCREATED_ERRORS = frozenset({
    'keyword_position_layout_missing', 'keyword_position_layout_ambiguous',
    'positioning_config_invalid', 'report_signature_layout_invalid',
    'organization_seal_layout_invalid', 'calibration_layout_invalid',
    'dual_chief_layout_invalid', '1435002',
})


def snapshot(flow):
    try:
        value = json.loads(flow.positioning_json or '{}')
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def set_phase(flow, phase):
    value = snapshot(flow)
    value['dispatchState'] = {'phase': phase, 'updatedAt': datetime.utcnow().isoformat()}
    flow.positioning_json = json.dumps(value, ensure_ascii=False)


def definitely_uncreated(flow):
    if (flow.provider_flow_id or flow.dispatched_at or flow.signed_file_id
            or flow.status in {'signing', 'completed', 'signed', 'verified'}):
        return False
    state = snapshot(flow).get('dispatchState') or {}
    phase = state.get('phase') if isinstance(state, dict) else None
    if phase:
        return phase in {'preparing', 'rejected'}
    if flow.status == 'failed' and str(flow.error_code or '') in LEGACY_UNCREATED_ERRORS:
        return True
    return not flow.provider_file_id and flow.status in {'ready', 'binding_required', 'failed'}
