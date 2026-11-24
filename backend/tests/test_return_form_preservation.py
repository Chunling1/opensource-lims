"""Real HTTP full-form submissions must retain fields the wizard does not own."""
from testkit.forms import loaded_form
from copy import deepcopy
import pytest
from app.extensions import db
from app.models import ReportAttachment, OperationAudit
from app.security import issue_token
from app.applications.report_lifecycle import apply_return_plan
from test_compliance_review_round import case

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def form_case(case, monkeypatch, scenario_factory):
    app, user, report = case
    from app.blueprints import reports
    from app import sample_preview_warmup
    for name in ('sample_party_error', 'sample_price_error', 'sample_pricing_error', '_apply_report_prefix_change'):
        monkeypatch.setattr(reports, name, lambda *a, **kw: None)
    monkeypatch.setattr(sample_preview_warmup, 'schedule_after_save', lambda *a: None)
    scenario_factory.grant_action(user, 'sample.register.complete')
    permission = scenario_factory.permission('entrust.sample_register.view')
    user.permissions.append(permission)
    user.department.permissions.append(permission)
    report.detail = {
        **report.detail,
        'workflowDates': {'sampleInboundAt': '2026-10-22', 'samplePickupAt': '2026-10-22'},
        'checkInput': {'standard': report.detail['checkInput']['standard'], 'instrument': 'QA', 'seal': 'CMA + CNAS', 'testStartDate': '2026-10-22', 'testDate': '2026-10-23', 'result': '原始结果'},
        'attachments': [{'id': 123, 'name': '原始记录.pdf'}], 'reportPages': [{'content': '原报告'}],
        'reportComposition': {'keepComplete': True},
        'summary': [{'title': '原始记录', 'fields': [['记录编号', 'QA-RECORD']]},
                    {'title': '实验信息', 'fields': [['检测日期', '2026-10-23'], ['检测设备', 'QA']]}],
    }
    report.sample_pickup = {'signed': True, 'outTime': '2026-10-22', 'pickupTime': '2026-10-22'}
    report.status, report.sample_status = '检测录入中', '已领取'
    db.session.add(ReportAttachment(report_no=report.report_no, name='原始记录.pdf', data=b'%PDF-QA'))
    db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(user)}
    # PipelineWizard.buildDetail sends form summary plus empty runtime placeholders.
    full = {'rawSample': deepcopy(report.detail['rawSample']),
            'summary': [{'title': '送样信息', 'fields': [['送样日期', '2026-10-22']]},
                        {'title': '实验信息', 'fields': [['检测项目', report.project], ['检测日期', '待检测人员录入'], ['检测设备', '待检测人员录入']]},
                        {'title': '原始记录', 'fields': [['记录编号', '待录入']]}],
            'checks': [], 'attachments': [], 'checkInput': {}, 'workflowDates': {}}
    return app.test_client(), headers, user, report, full


@pytest.mark.parametrize('entry', ['change-save', 'change-resubmit', 'edit'])
def test_full_form_keeps_testing_dates_attachments_and_records(form_case, entry):
    client, headers, user, report, full = form_case
    old = deepcopy(report.detail)
    if entry == 'edit':
        report.sample_reg_state = '登记中'
    else:
        apply_return_plan(report, user, 'testing.data_entry.return', '委托信息更正')
    db.session.commit()
    method = client.put if entry == 'edit' else client.post
    result = method(f'/api/reports/{report.report_no}/{entry}', headers=headers, json=loaded_form(client, f'/api/reports/{report.report_no}/{entry}', {'fullDetail': full})).get_json()
    assert result['code'] == 0, result
    db.session.refresh(report)
    for key in ('checkInput', 'workflowDates', 'attachments', 'reportPages', 'reportComposition'):
        assert report.detail[key] == old[key], key
    summaries = {s['title']: dict(s['fields']) for s in report.detail['summary']}
    assert summaries['原始记录']['记录编号'] == 'QA-RECORD'
    assert summaries['实验信息']['检测日期'] == '2026-10-23'
    assert ReportAttachment.query.filter_by(report_no=report.report_no).one().data == b'%PDF-QA'
    if entry == 'change-resubmit':
        assert report.status == '待合同评审'


@pytest.mark.parametrize('entry', ['change-save', 'change-resubmit', 'edit'])
def test_changed_send_date_is_checked_against_saved_inbound(form_case, entry):
    client, headers, user, report, full = form_case
    report.status = '委托更改中'; report.sample_reg_state = '登记中'
    db.session.commit()
    full['rawSample']['sendDate'] = '2026-10-24'
    full['summary'][0]['fields'] = [['送样日期', '2026-10-24']]
    before = deepcopy(report.detail)
    method = client.put if entry == 'edit' else client.post
    result = method(f'/api/reports/{report.report_no}/{entry}', headers=headers, json=loaded_form(client, f'/api/reports/{report.report_no}/{entry}', {'fullDetail': full})).get_json()
    assert result['code'] != 0 and '不得早于' in result['message'], result
    db.session.refresh(report)
    assert report.detail == before


def test_issued_correction_requires_contract_review_and_cannot_be_skipped(form_case, monkeypatch):
    client, headers, user, report, full = form_case
    from app import project_workflow
    apply_return_plan(report, user, 'report.approval.return', '更正', 'entrust_only')
    report.detail = {**report.detail, 'changeRound': True}
    db.session.commit()
    response = client.post(f'/api/reports/{report.report_no}/change-resubmit', headers=headers, json=loaded_form(client, f'/api/reports/{report.report_no}/change-resubmit', {'fullDetail': full})).get_json()
    assert response['code'] == 0, response
    db.session.expire(report)
    assert report.detail['requiresContractReReview'] is True
    monkeypatch.setattr(project_workflow, 'skipped_steps_for_project', lambda p: {'entrust_review', 'sample_inbound', 'sample_outbound'})
    project_workflow.advance_skipped_project_steps(report)
    assert report.status == '待合同评审'
    assert report.detail['returnPlan']['afterContractReview'] == 'review'


def test_testing_change_keeps_data_and_requests_review(form_case):
    client, headers, user, report, full = form_case
    report.status = '委托更改中'; db.session.commit()
    full['rawSample']['sampleName'] = '不同样品名称'
    result = client.post(f'/api/reports/{report.report_no}/change-save', headers=headers, json=loaded_form(client, f'/api/reports/{report.report_no}/change-save', {'fullDetail': full})).get_json()
    assert result['code'] == 0, result
    assert report.detail['testDataReviewRequired']['fields'] == ['sampleName']
    assert report.detail['checkInput']['result'] == '原始结果'


def test_post_testing_return_api_removed(isolated_app):
    assert not any(rule.rule == '/api/mobile/samples/<report_no>/return' for rule in isolated_app.url_map.iter_rules())
    assert isolated_app.test_client().post('/api/mobile/samples/QA/return', json={}).status_code == 404


def test_all_mobile_api_routes_are_removed(isolated_app):
    # Batch-3 Q10 (2026-11-07): no mobile client exists; the whole /api/mobile surface is gone.
    assert not [rule.rule for rule in isolated_app.url_map.iter_rules() if rule.rule.startswith('/api/mobile/')]
    client = isolated_app.test_client()
    for method, path in (('post', '/api/mobile/samples/query'), ('post', '/api/mobile/samples/QA/nameplate-ocr'),
                         ('post', '/api/mobile/samples/QA/inbound'), ('post', '/api/mobile/samples/QA/pickup'),
                         ('get', '/api/mobile/samples/logs'), ('post', '/api/mobile/reports/query')):
        assert getattr(client, method)(path, json={}).status_code == 404


@pytest.mark.parametrize('source,mode,target', [
    ('testing.data_entry.return', '', '检测录入中'),
    ('report.review.return', 'entrust_only', '待审核'),
    ('report.approval.return', 'entrust_and_data', '检测更改中'),
])
def test_full_form_three_contract_rejections_preserve_original_target(form_case, scenario_factory, monkeypatch, source, mode, target):
    client, headers, user, report, full = form_case
    from app.blueprints import reports
    from app import workflow_hooks as hooks
    from test_compliance_review_round import payload
    scenario_factory.grant_action(user, 'report.contract_review.return')
    monkeypatch.setattr(hooks, 'blocker', lambda *a: None)
    monkeypatch.setattr(hooks, 'capture', lambda *a: None)
    monkeypatch.setattr(reports, '_sample_configuration', lambda *a, **kw: {'ready': True})
    old = deepcopy(report.detail)
    apply_return_plan(report, user, source, '首次退回', mode)
    db.session.commit()
    for index in range(4):
        for action in ('change-save', 'change-resubmit'):
            result = client.post(f'/api/reports/{report.report_no}/{action}', headers=headers, json=loaded_form(client, f'/api/reports/{report.report_no}/{action}', {'fullDetail': full})).get_json()
            assert result['code'] == 0, result
        if index < 3:
            result = client.post(f'/api/reports/{report.report_no}/contract-review', headers=headers,
                                 json={'action': 'return', 'opinion': '复评再次退回'}).get_json()
            assert result['code'] == 0, result
    result = client.post(f'/api/reports/{report.report_no}/contract-review', headers=headers, json={
        **payload(report, 'contract_review'), 'action': 'pass', 'cma': True, 'cnas': True,
        'items': {key: True for key, _ in reports.CR_ITEMS},
    }).get_json()
    assert result['code'] == 0, result
    db.session.refresh(report)
    assert report.status == target
    assert report.detail['returnPlan']['originalSourceAction'] == source
    for key in ('workflowDates', 'checkInput', 'attachments', 'reportPages'):
        assert report.detail[key] == old[key]


def test_changed_send_date_checks_every_saved_test_interval(form_case):
    client, headers, user, report, full = form_case
    report.status = '委托更改中'
    detail = deepcopy(report.detail)
    detail['workflowDates'] = {}
    detail['checkInput'].update(testStartDate='2026-10-25', testDate='2026-10-25',
                               testIntervals=[{'start': '2026-10-22', 'end': '2026-10-22'}])
    report.detail = detail
    report.sample_pickup = {}
    db.session.commit()
    full['rawSample']['sendDate'] = '2026-10-23'
    full['summary'][0]['fields'] = [['送样日期', '2026-10-23']]
    result = client.post(f'/api/reports/{report.report_no}/change-save', headers=headers,
                         json=loaded_form(client, f'/api/reports/{report.report_no}/change-save', {'fullDetail': full})).get_json()
    assert result['code'] != 0 and '第 1 个试验区间' in result['message'], result
    db.session.refresh(report)
    assert report.detail == detail
