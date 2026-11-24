"""Manual parameters do not change workflow or the user's requested marks."""
from copy import deepcopy
import pytest
from app import compliance
from app.extensions import db
from app.models import ComplianceAcknowledgement, StdLibraryItem
from app.report_scope import assess_scope, report_seal
from app.sample_form_merge import merge_sample_form
from app.seal_requirements import requested_seal
from app.security import issue_token
from test_compliance_review_round import case, acknowledge, payload

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('detail,expected', [
    ({'rawSample': {'seal': ''}, 'contractReview': {'sealRequirement': 'CMA'}}, ''),
    ({'complianceResolution': {'requestedSealCurrent': '', 'requestedSealOriginal': 'CMA'}}, ''),
    ({'contractReview': {'sealRequirement': 'CMA + CNAS'}}, 'CMA + CNAS'),
    ({'sampleConfiguration': {'requiredCnas': True, 'requiredCma': False}}, 'CNAS'),
    ({'checkInput': {'seal': 'CNAS'}}, 'CNAS'),
])
def test_legacy_request_sources_and_explicit_empty(detail, expected):
    assert requested_seal(detail) == expected


def legacy_detail(report):
    detail = deepcopy(report.detail)
    detail['rawSample'].update(seal='', manualCapabilityItems=['尺寸偏差', '烟密闭性能'], manualCapabilityReason='')
    detail['summary'] = [{'title': '委托信息', 'fields': [['盖章要求', '']]}]
    detail['checkInput']['seal'] = ''
    detail['complianceResolution'] = {'requestedSealOriginal': 'CMA + CNAS', 'finalSeal': '', 'lastStage': 'contract_review'}
    return detail


@pytest.mark.parametrize('stage', ['contract_review', 'report_review', 'report_approval'])
def test_legacy_manual_strip_rechecks_without_manual_exception_or_opinion(case, stage):
    _, user, report = case
    report.detail = legacy_detail(report)
    report.out_of_scope = True
    report.out_of_scope_note = '库外项目，不在受认可范围内'
    db.session.commit()
    before = deepcopy(report.detail)
    preflight = compliance.build_compliance_preflight(report, stage)
    assert preflight['ready'] and not preflight['requiresOpinion']
    assert preflight['issues'] == []
    assert preflight['requestedSeal'] == preflight['finalSeal'] == 'CMA + CNAS'
    assert report.detail == before  # read-only recovery until explicit approval
    scope = assess_scope(report)
    assert scope['state'] == 'in_scope' and not scope['outOfScope']
    acknowledge(report, user, stage)
    assert not report.out_of_scope and report.out_of_scope_note == ''
    assert report_seal(report.detail) == 'CMA + CNAS'
    assert report.detail['rawSample']['manualCapabilityItems'] == ['尺寸偏差', '烟密闭性能']
    assert ComplianceAcknowledgement.query.one().opinion == ''


@pytest.mark.parametrize('projection', ['', 'sample_form', 'sample_form_text'])
def test_review_and_form_reads_expose_request_without_rewriting_final_or_history(case, projection):
    app, user, report = case
    report.detail = legacy_detail(report)
    db.session.commit()
    before = deepcopy(report.detail)
    url = f'/api/reports/{report.report_no}?view=contract_review&projection={projection}'
    result = app.test_client().get(url, headers={'Authorization': 'Bearer '+issue_token(user)}).get_json()
    assert result['code'] == 0, result
    assert result['data']['requestedSeal'] == 'CMA + CNAS'
    assert result['data']['rawSample']['seal'] == ''
    db.session.refresh(report)
    assert report.detail == before


def test_current_request_can_change_without_old_original_restoring_cma(case):
    _, user, report = case
    previous = legacy_detail(report)
    report.detail = merge_sample_form(previous, {'rawSample': {'seal': 'CNAS'}})
    assert requested_seal(report.detail) == 'CNAS'
    assert report.detail['complianceResolution']['requestedSealOriginal'] == 'CMA + CNAS'
    assert payload(report, 'contract_review')['finalSeal'] == 'CNAS'
    acknowledge(report, user, 'contract_review')
    assert report_seal(report.detail) == 'CNAS'
    # Legacy form unchanged system-final value must not erase the original request.
    assert requested_seal(merge_sample_form(previous, {'rawSample': {'seal': ''}})) == 'CMA + CNAS'
    previous['rawSample']['seal'] = 'CNAS'
    previous['complianceResolution']['finalSeal'] = 'CNAS'
    changed = merge_sample_form(previous, {'requestedSeal': 'CNAS', 'rawSample': {'seal': 'CNAS'}})
    assert requested_seal(changed) == 'CNAS'
    cleared = merge_sample_form(previous, {'requestedSeal': '', 'rawSample': {'seal': ''}})
    assert requested_seal(cleared) == ''



def test_legacy_re_review_still_requires_user_confirmation_of_requested_marks(case, monkeypatch):
    app, user, report = case
    from app import workflow_hooks as hooks
    from app.blueprints.reports import CR_ITEMS
    monkeypatch.setattr(hooks, 'blocker', lambda *a: None)
    report.detail = legacy_detail(report)
    db.session.commit()
    result = app.test_client().post(f'/api/reports/{report.report_no}/contract-review',
        headers={'Authorization': 'Bearer '+issue_token(user)}, json={
            **payload(report, 'contract_review'), 'action': 'pass',
            'items': {key: True for key, _ in CR_ITEMS}, 'cma': False, 'cnas': False,
        }).get_json()
    assert result['code'] != 0 and '必须逐项确认' in result['message']
    assert result['data']['requiredCma'] and result['data']['requiredCnas']
    assert ComplianceAcknowledgement.query.count() == 0


def test_manual_items_do_not_bypass_real_standard_or_equipment_failures(case, monkeypatch):
    _, _, report = case
    report.detail = legacy_detail(report)
    standard = StdLibraryItem.query.one()
    standard.auth_kind = 'CNAS'
    db.session.commit()
    result = compliance.build_compliance_preflight(report, 'contract_review')
    assert result['finalSeal'] == 'CNAS' and result['issues']
    assert assess_scope(report)['outOfScope']
    monkeypatch.setattr(compliance, 'compute_report_checks', lambda r: ([{'group': '仪器有效性校验', 'status': '不通过'}], True, ''))
    result = compliance.build_compliance_preflight(report, 'report_approval')
    assert result['finalSeal'] == ''
    assert 'instrument_validity' in {i['category'] for i in result['issues']}
