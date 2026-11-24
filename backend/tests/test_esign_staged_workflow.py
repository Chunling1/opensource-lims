"""Real local DB/PDF/state machine; only the external provider is simulated."""
import copy
import hashlib
import json
import os
from pathlib import Path

import fitz
import pytest
from app.extensions import db
from app.models import EsignIdentityBinding, OperationAudit, Project, ProjectStep, EquipmentItem, StdLibraryItem
from app.functions import esign_service as service, esign_unified as unified, esign_stages as stages, esign_cancellation as cancellation
from app.esign_seal_confirmation import assign
from app.report_version_consistency import lock_reviewed_document, require_current_document
from app.applications.report_lifecycle import commands
from test_preserved_approval_and_seal_confirmation import prepared
from test_esign_pdf_signature_positioning import report_pdf
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)


def synthetic_pdf():
    with fitz.open() as pdf:
        pdf.new_page(width=595, height=842).insert_text((170, 700), 'Example Testing Lab Co., Ltd.')
        page = pdf.new_page(width=595, height=842)
        page.insert_text((400, 660), '检验检测专用章', fontname='china-s', fontsize=10)
        page.insert_text((400, 685), '签发日期：', fontname='china-s', fontsize=11)
        for x, zh, en in [(56, '批准', 'Approval'), (230, '审核', 'Verification'), (405, '主检', 'Chief Tester')]:
            page.insert_text((x, 740), zh, fontname='china-s', fontsize=10)
            page.insert_text((x, 754), en, fontsize=10)
        return pdf.tobytes()


class Provider:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []
        self.stop = True
        self.timeout_append = False
        self.detail = {'signFlowStatus': 1, 'signers': []}

    def upload_pdf(self, name, raw):
        assert raw == self.raw
        self.calls.append(('upload', name, hashlib.sha256(raw).hexdigest()))
        return 'LOCAL-FILE'

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == 'GET':
            return copy.deepcopy(self.detail)
        if path.endswith('/create-by-file') or path.endswith('/signers/sign-fields'):
            for signer in copy.deepcopy(payload['signers']):
                for field in signer['signFields']:
                    field['signFieldStatus'] = 0
                self.detail['signers'].append(signer)
            if self.timeout_append:
                raise service.EsignServiceError('provider_unavailable', 'simulated timeout')
            return {'signFlowId': 'LOCAL-FLOW'}
        if path.endswith('/revoke'):
            if self.stop:
                self.detail['signFlowStatus'] = 3
            return {}
        if path.endswith('/finish'):
            self.detail['signFlowStatus'] = 2
            return {}
        pytest.fail('Unexpected provider call ' + path)

    def sign(self, role):
        for signer in self.detail['signers']:
            for field in signer['signFields']:
                if field['customBizNum'].endswith('-' + role.upper()):
                    field['signFieldStatus'] = 4

    def seal(self):
        for signer in self.detail['signers']:
            if signer['signerType'] == 1:
                for field in signer['signFields']:
                    field['signFieldStatus'] = 4

    def download_signed_pdf(self, flow_id):
        assert self.detail['signFlowStatus'] == 2
        return self.raw


@pytest.fixture
def sample(prepared, isolated_app, scenario_factory, monkeypatch):
    report, version, chief, _ = prepared
    # The shared prepared fixture starts at approval. This scenario starts at first entry.
    OperationAudit.query.filter_by(object_type='report', object_id=report.report_no,
        action='report.approval.pass').delete()
    raw = Path(os.environ['ESIGN_TEST_PDF']).read_bytes() if os.environ.get('ESIGN_TEST_PDF') else synthetic_pdf()
    version.pdf_data = raw
    version.sha256 = hashlib.sha256(raw).hexdigest()
    report.status = '检测录入中'
    report.sample_status = '已领取'
    report.approved_document_version_id = None
    chief.role_key = 'admin'
    report.sample_pickup = {'pickupTime': '2026-01-01'}
    report.detail = {'rawSample': {'reportType': '工程报告', 'seal': '无'},
        'checkInput': {'standard': '测试标准', 'instrument': '测试仪器', 'testStartDate': '2026-01-02',
            'testDate': '2026-01-03', 'validatedForCompletion': True, 'people': {'primaryTester1': chief.account}}}
    equipment = EquipmentItem(archive_no='LOCAL-EQ', name='测试仪器', dept=chief.department.name,
        period='长期', status='在用')
    standard = StdLibraryItem(code='QA 123-2026', name='本地测试标准', use_depts=chief.department.name)
    db.session.add_all([equipment, standard])
    db.session.flush()
    report.detail = {**report.detail, 'rawSample': {**report.detail['rawSample'],
        'testBases': [standard.code], 'standardItemIds': [standard.id]},
        'checkInput': {**report.detail['checkInput'], 'standard': standard.code, 'standards': [standard.code],
            'equipmentIds': [equipment.id]}}
    from app.standard_resolution import align_testing_identity
    align_testing_identity(report, chief)
    reviewer = scenario_factory.user(chief.department, role_key='admin')
    approver = scenario_factory.user(chief.department, role_key='admin')
    for i, user in enumerate([chief, reviewer, approver]):
        db.session.add(EsignIdentityBinding(user_id=user.id, legal_name=user.name,
            psn_account=f'1380000000{i}', psn_id=f'LOCAL-ONLY-{i}', status='verified'))
    assign(chief, True)
    # No template rendering/conversion in this provider test; snapshot comparison is real.
    def snapshot(r, *args, **kwargs):
        return copy.deepcopy({'report': {'reportNo': r.report_no, 'detail': r.detail},
            'template': {'profile': {'kind': 'engineering', 'language': 'CN', 'variant': 'Standard'},
                'files': [{'sha256': 'local-template'}]}, 'attachments': [], 'content': {}, 'approvalDate': ''})
    monkeypatch.setattr('app.report_documents.source_snapshot', snapshot)
    version.snapshot = snapshot(report)
    db.session.commit()
    for key, value in {'ESIGN_STAGE_WORKFLOW_ENABLED': True, 'ESIGN_ENABLED': True,
            'ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED': True, 'ESIGN_ORG_AUTOSIGN_ENABLED': True,
            'ESIGN_ORG_ID': 'LOCAL-ORG', 'ESIGN_ORG_NAME': 'Local test', 'ESIGN_ORG_SEAL_ID': 'LOCAL-SEAL',
            'DOCUMENT_TEMPLATE_ENGINE': 'docparser-original-202609'}.items():
        monkeypatch.setitem(isolated_app.config, key, value)
    provider = Provider(raw)
    monkeypatch.setattr(service, 'EsignV3Client', lambda: provider)
    monkeypatch.setattr(unified, '_client', lambda: provider)
    monkeypatch.setattr(cancellation, 'EsignV3Client', lambda: provider)
    return report, version, chief, reviewer, approver, provider


@pytest.fixture
def selected_sample(sample):
    report, _, chief, *_ = sample
    assert stages.choose_at_completion(report, chief, stages.MODE) == stages.MODE
    db.session.commit()
    return sample


@pytest.fixture
def active(selected_sample):
    sample = selected_sample
    report, version, chief, *rest = sample
    flow = stages.begin(report, version, chief)
    db.session.commit()
    service.dispatch_flow(flow.id, chief)
    assert flow.status == 'signing', flow.error_message
    return (*sample, flow)


def advance(data, role):
    report, version, chief, reviewer, approver, provider, flow = data
    if role != 'chief':
        stages.confirm_stage(report, reviewer if role == 'reviewer' else approver, role)
        db.session.commit()
        stages.append_confirmed(flow.id)
    provider.sign(role)
    if role == 'approver':
        provider.sign('approval-date')
    unified.refresh(flow.id)


def test_complete_round_no_rewrite_and_explicit_seal(active):
    report, version, chief, reviewer, approver, provider, flow = active
    original = version.pdf_data
    assert len(flow.signers) == 1
    advance(active, 'chief')
    assert report.status == '待审核'
    lock_reviewed_document(report, reviewer)
    db.session.commit()
    advance(active, 'reviewer')
    assert report.status == '待批准'
    advance(active, 'approver')
    assert report.status == '待打印' and stages.all_stages_signed(flow)
    assert service.ensure_report_esign_flow(report.report_no, chief).id == flow.id
    assert service._positioning_snapshot(flow)['organizationSeal']['status'] == 'awaiting_confirmation'
    assert not flow.signed_file_id
    unified.confirm(flow.id, chief, flow.source_sha256, report.report_no)
    unified.confirm(flow.id, chief, flow.source_sha256, report.report_no)
    provider.seal()
    unified.refresh(flow.id)
    assert flow.status == 'completed' and flow.signed_file_id
    assert report.stamped and report.status == '待发放'
    assert version.pdf_data == original and hashlib.sha256(original).hexdigest() == flow.source_sha256
    assert len([c for c in provider.calls if c[1].endswith('/create-by-file')]) == 1
    assert OperationAudit.query.filter_by(action='report.review.pass').count() == 1


def test_approval_waits_for_both_signature_and_date(active):
    *_, provider, flow = active
    advance(active, 'chief')
    advance(active, 'reviewer')
    stages.confirm_stage(active[0], active[4], 'approver')
    db.session.commit()
    stages.append_confirmed(flow.id)
    provider.sign('approver')
    unified.refresh(flow.id)
    assert active[0].status == '待批准'
    payload = [p for m, u, p in provider.calls if m == 'POST'][-1]
    date = payload['signers'][0]['signFields'][1]['dateSignFieldConfig']
    assert date['fontSize'] == 11 and date['dateFormat'] == 'yyyy年MM月dd日'
    provider.sign('approval-date')
    unified.refresh(flow.id)
    assert active[0].status == '待打印'


@pytest.mark.parametrize('last', ['none', 'chief', 'reviewer', 'approver'])
def test_return_revokes_then_requires_every_signature(active, last):
    report, version, chief, reviewer, approver, provider, flow = active
    for role in ('chief', 'reviewer', 'approver'):
        if last == 'none':
            break
        advance(active, role)
        if role == last:
            break
    stages.cancel_round(flow.id, chief, '本地退回验证')
    assert flow.status == 'cancelled' and report.status == '检测录入中'
    assert not report.approved_document_version_id and not stages.content_blocker(report)
    new = stages.begin(report, version, chief)
    db.session.commit()
    assert new.id != flow.id and len(new.signers) == 1 and new.signers[0].status == 'pending'
    stale = copy.deepcopy(provider.detail)
    stale['signFlowStatus'] = 1
    with pytest.raises(service.EsignServiceError):
        unified._sync(flow, provider, stale)
    assert report.status == '检测录入中'


def test_unconfirmed_revoke_locks_until_retry(active):
    report, version, chief, *_, provider, flow = active
    provider.stop = False
    with pytest.raises(service.EsignServiceError, match='尚未确认'):
        stages.cancel_round(flow.id, chief, '本地撤销')
    assert flow.status == 'cancelling' and stages.content_blocker(report)
    provider.stop = True
    stages.cancel_round(flow.id, chief, '本地撤销')
    assert flow.status == 'cancelled' and not stages.content_blocker(report)


def test_switch_off_preserves_active_round(active, isolated_app):
    isolated_app.config['ESIGN_STAGE_WORKFLOW_ENABLED'] = False
    advance(active, 'chief')
    advance(active, 'reviewer')
    advance(active, 'approver')
    assert active[0].status == '待打印'
    assert stages.workflow_choice(active[0]) == stages.MODE


def test_disabled_entry_preserves_selected_mode(selected_sample, isolated_app):
    report, version, chief, *_ = selected_sample
    isolated_app.config['ESIGN_STAGE_WORKFLOW_ENABLED'] = False
    with pytest.raises(service.EsignServiceError, match='已确定'):
        stages.choose_at_completion(report, chief, 'legacy')
    assert stages.is_staged(stages.begin(report, version, chief))


@pytest.mark.parametrize('kind', ['check', 'double', 'skip', 'check-history'])
def test_first_batch_rejects_unsupported_paths(sample, kind):
    report, version, chief, *_ = sample
    if kind == 'check':
        report.detail = {**report.detail, 'returnPlan': {'afterDataChange': 'data_check'}}
    if kind == 'double':
        report.detail = {**report.detail, 'checkInput': {**report.detail['checkInput'], 'people': {'primaryTester2': chief.account}}}
    if kind == 'skip':
        Project.query.filter_by(name=report.project).one().workflow_config = {'skippedSteps': ['report_review']}
    if kind == 'check-history':
        from app.audit import add_operation_audit
        add_operation_audit('report.report_check.pass', 'report', report.report_no, actor=chief)
    db.session.commit()
    with pytest.raises(service.EsignServiceError):
        stages.choose_at_completion(report, chief, stages.MODE)
    assert stages.choose_at_completion(report, chief, None) == 'legacy'


def test_live_round_cannot_change_mode(active):
    report, _, chief, *_, flow = active
    with pytest.raises(service.EsignServiceError, match='已确定'):
        stages.choose_at_completion(report, chief, 'legacy')
    assert stages.is_staged(flow)


def test_append_timeout_reconciles_without_duplicate(active):
    advance(active, 'chief')
    report, _, _, reviewer, _, provider, flow = active
    stages.confirm_stage(report, reviewer, 'reviewer')
    db.session.commit()
    provider.timeout_append = True
    with pytest.raises(service.EsignServiceError):
        stages.append_confirmed(flow.id)
    provider.timeout_append = False
    stages.append_confirmed(flow.id)
    assert len([c for c in provider.calls if c[1].endswith('/signers/sign-fields')]) == 1


def test_unknown_append_with_no_fields_needs_evidence_and_never_reposts(active, monkeypatch):
    advance(active, 'chief')
    report, _, _, reviewer, _, provider, flow = active
    stages.confirm_stage(report, reviewer, 'reviewer')
    db.session.commit()
    request = provider.request
    def interrupted(method, path, payload=None):
        if method == 'POST':
            raise service.EsignServiceError('provider_unavailable', 'connection lost')
        return request(method, path, payload)
    monkeypatch.setattr(provider, 'request', interrupted)
    with pytest.raises(service.EsignServiceError, match='connection lost'):
        stages.append_confirmed(flow.id)
    monkeypatch.setattr(provider, 'request', request)
    with pytest.raises(service.EsignServiceError, match='待核实'):
        stages.append_confirmed(flow.id)
    ts = stages.state(flow)['decisions']['reviewer']['appendRequestedAt']
    with pytest.raises(service.EsignServiceError, match='不匹配'):
        stages.release_unreceived(flow.id, 'reviewer', 'old-request', 'local-ticket')
    stages.release_unreceived(flow.id, 'reviewer', ts, 'local-ticket')
    assert OperationAudit.query.filter_by(action='report.esign.stage.release_unreceived').count() == 1
    assert not any(c[1].endswith('/signers/sign-fields') for c in provider.calls)
    stages.append_confirmed(flow.id)
    with pytest.raises(service.EsignServiceError, match='未解锁'):
        stages.release_unreceived(flow.id, 'reviewer', stages.state(flow)['decisions']['reviewer']['appendRequestedAt'], 'local-ticket')
    assert sum(c[1].endswith('/signers/sign-fields') for c in provider.calls) == 1


def test_confirmed_unsent_can_retry(active, monkeypatch):
    advance(active, 'chief')
    report, _, _, reviewer, _, provider, flow = active
    stages.confirm_stage(report, reviewer, 'reviewer')
    db.session.commit()
    request = provider.request
    def refused(method, path, payload=None):
        if method == 'POST':
            raise service.EsignServiceError('provider_unavailable', 'no connection', {'notSent': True})
        return request(method, path, payload)
    with monkeypatch.context() as patch:
        patch.setattr(provider, 'request', refused)
        with pytest.raises(service.EsignServiceError, match='no connection'):
            stages.append_confirmed(flow.id)
    stages.append_confirmed(flow.id)
    assert sum(c[1].endswith('/signers/sign-fields') for c in provider.calls) == 1


@pytest.mark.parametrize(('failure', 'retryable'), [('refused', True), (422, True), (504, False), ('timeout', False)])
def test_append_transport_outcome(isolated_app, monkeypatch, failure, retryable):
    import urllib.error
    with isolated_app.app_context():
        for key, value in {'ESIGN_PRODUCTION_READY': True, 'ESIGN_BASE_URL': 'https://local.invalid',
                           'ESIGN_APP_ID': 'local', 'ESIGN_APP_SECRET': 'local'}.items():
            monkeypatch.setitem(isolated_app.config, key, value)
        def unavailable(req, timeout):
            if isinstance(failure, int):
                raise urllib.error.HTTPError(req.full_url, failure, 'fixture', {}, None)
            raise urllib.error.URLError(ConnectionRefusedError() if failure == 'refused' else TimeoutError())
        monkeypatch.setattr('urllib.request.urlopen', unavailable)
        with pytest.raises(service.EsignServiceError) as err:
            service.EsignV3Client().request('POST', '/v3/sign-flow/local/signers/sign-fields', {})
        assert bool(err.value.details.get('notSent')) == retryable


def test_lightweight_pending_after_switch_off(active, isolated_client, isolated_app):
    report, _, chief, reviewer, _, _, flow = active
    isolated_app.config['ESIGN_STAGE_WORKFLOW_ENABLED'] = False
    assert stages.prompt_available()
    path = '/api/esign/tasks/stage-pending'
    headers = login_headers(isolated_client, chief.account)
    assert isolated_client.get(path, headers=headers).json['data']['rows'] == [
        dict(id=flow.id, reportNo=report.report_no, myRole='主检', providerFlowId=flow.provider_flow_id, errorMessage=None)]
    assert isolated_client.get(path, headers=login_headers(isolated_client, reviewer.account)).json['data']['rows'] == []
    advance(active, 'chief')
    assert isolated_client.get(path, headers=headers).json['data']['rows'] == []


def test_changed_content_rejected_before_upload(selected_sample):
    report, version, chief, *_, provider = selected_sample
    flow = stages.begin(report, version, chief)
    db.session.commit()
    report.detail = {**report.detail, 'rawSample': {'reportType': '工程报告', 'client': 'changed'}}
    db.session.commit()
    with pytest.raises((service.EsignServiceError, ValueError)):
        service.dispatch_flow(flow.id, chief)
    assert not provider.calls


def test_real_review_approval_commands_and_duplicate_click(active, scenario_factory):
    report, version, chief, reviewer, approver, provider, flow = active
    advance(active, 'chief')
    for actor, role, action, expected in [(reviewer, 'reviewer', 'report.review.pass', '待批准'),
                                         (approver, 'approver', 'report.approval.pass', '待打印')]:
        scenario_factory.grant_action(actor, action)
        db.session.commit()
        from app.compliance import build_compliance_preflight
        preflight = build_compliance_preflight(report, 'report_review' if role == 'reviewer' else 'report_approval')
        body = {'preflightVersion': preflight['preflightVersion'], 'finalSeal': preflight['finalSeal'],
            'acknowledgedIssueIds': [i['id'] for i in preflight['issues'] if i['acknowledgeable']],
            'complianceOpinion': '本地流程验证'}
        result = commands.execute_report_action(actor, report.report_no, action, body)
        assert result.code == 0, result.message
        assert result.data['esignPending']
        before = len(provider.calls)
        repeat = commands.execute_report_action(actor, report.report_no, action, body)
        assert repeat.code == 0, repeat.message
        assert not any(m == 'POST' for m, _, _ in provider.calls[before:])
        provider.sign(role)
        if role == 'approver':
            provider.sign('approval-date')
        unified.refresh(flow.id)
        assert report.status == expected


@pytest.mark.parametrize('action,last', [('report.review.return', 'chief'), ('report.approval.return', 'reviewer'),
                                        ('report.review.undo', 'reviewer'), ('report.approval.undo', 'approver')])
def test_real_return_command_keeps_authorization_and_restarts(active, scenario_factory, action, last):
    report, version, chief, reviewer, approver, provider, flow = active
    for role in ('chief', 'reviewer', 'approver'):
        advance(active, role)
        if role == last:
            break
    scenario_factory.grant_action(chief, action)
    db.session.commit()
    result = commands.execute_report_action(chief, report.report_no, action, {'note': '本地退回', 'returnMode': 'data_only'})
    assert result.code == 0, result.message
    assert flow.status == 'cancelled'
    assert report.status == ('检测更改中' if action.endswith('.return') else '检测录入中')
    assert report.approved_document_version_id is None
    assert not stages.content_blocker(report)


def test_return_entrust_also_requires_new_chief(active, scenario_factory):
    report, _, chief, *_, flow = active
    advance(active, 'chief')
    scenario_factory.grant_action(chief, 'report.review.return')
    db.session.commit()
    result = commands.execute_report_action(chief, report.report_no, 'report.review.return',
        {'note': '修改委托', 'returnMode': 'entrust_only'})
    assert result.code == 0, result.message
    assert report.status == '委托更改中'
    assert report.detail['returnPlan']['afterContractReview'] == 'data_change'
    assert report.detail['returnPlan']['afterDataChange'] == 'review'


def test_unauthorized_return_does_not_contact_provider(active, scenario_factory):
    report, _, chief, *_, provider, flow = active
    advance(active, 'chief')
    actor = scenario_factory.user(chief.department)
    db.session.commit()
    count = len(provider.calls)
    result = commands.execute_report_action(actor, report.report_no, 'report.review.return', {'note': 'no rights'})
    assert result.code == 403 and len(provider.calls) == count and flow.status == 'signing'


def test_pending_source_cannot_be_edited_or_regenerated(active):
    report, version, *_ = active
    from app.applications.report_lifecycle.queries import report_content_editable
    from app.applications.testing_records.commands import _editable_state_error
    from app import preview_cache
    assert not report_content_editable(report) and _editable_state_error(report)
    assert preview_cache._locked(report)
    assert preview_cache.cached_pdf(report)[0] == version.pdf_data


def test_provider_spontaneous_stop_requires_explicit_reset(active):
    report, _, chief, *_, provider, flow = active
    provider.detail['signFlowStatus'] = 3
    unified.refresh(flow.id)
    assert stages.content_blocker(report)
    assert stages.workflow_choice(report) == stages.MODE
    stages.cancel_round(flow.id, chief, '确认撤回')
    assert not stages.content_blocker(report)


def test_cancel_after_seal_request_preserves_lock(active):
    report, _, chief, *_, provider, flow = active
    for role in ('chief', 'reviewer', 'approver'):
        advance(active, role)
    unified.confirm(flow.id, chief, flow.source_sha256, report.report_no)
    with pytest.raises(service.EsignServiceError, match='组织盖章'):
        stages.cancel_round(flow.id, chief, '不能撤回盖章请求')
    assert stages.content_blocker(report) and report.status == '待打印'


@pytest.mark.parametrize('mode,enabled', [(stages.MODE, True), ('legacy', True), (None, False)])
def test_completion_route_selects_and_freezes_mode(sample, monkeypatch, scenario_factory, isolated_client, isolated_app, mode, enabled):
    from app import review_version, preview_cache, report_documents
    from app.audit import add_operation_audit
    report, version, chief, *_, provider = sample
    chief.role_key = 'operator'
    perm = scenario_factory.permission('testing.data_entry.view')
    chief.department.permissions.append(perm)
    chief.permissions.append(perm)
    chief.project_steps.append(ProjectStep.query.filter_by(
        project_id=Project.query.filter_by(name=report.project).one().id, step_code='data_entry').one())
    isolated_app.config['ESIGN_STAGE_WORKFLOW_ENABLED'] = enabled
    # External conversion result is prepopulated, using actual confirmation and freeze code.
    monkeypatch.setattr(review_version, 'source_snapshot', report_documents.source_snapshot)
    monkeypatch.setattr(review_version, 'document_preflight', lambda *a: {'missing': [], 'warnings': []})
    monkeypatch.setattr(preview_cache, 'source_snapshot', report_documents.source_snapshot)
    snapshot = report_documents.source_snapshot(report)
    version.source_hash = report_documents.snapshot_hash(snapshot)
    key = preview_cache.source_key(report)
    path = preview_cache._entry(report.report_no, key)
    (path / 'preview.pdf').write_bytes(version.pdf_data)
    preview_cache._write(path, 'ready', pdfHash=version.sha256)
    add_operation_audit('report.preview.confirm', 'report', report.report_no, category='report', actor=chief,
        after={'sourceHash': version.source_hash, 'pdfHash': version.sha256})
    db.session.commit()
    headers = login_headers(isolated_client, chief.account)
    path = f'/api/reports/{report.report_no}/testinfo-complete'
    status_path = f'/api/reports/{report.report_no}/testinfo-completion-state?view=data_entry'
    assert isolated_client.get(status_path).status_code == 401
    assert isolated_client.get(status_path.replace('data_entry', 'data_change'), headers=headers).status_code == 403
    state = isolated_client.get(status_path, headers=headers)
    assert state.headers['Cache-Control'] == 'no-store'
    assert state.json['data'] == {'status': '检测录入中', 'stillEditable': True, 'esignPending': False}
    assert not provider.calls
    if enabled:
        response = isolated_client.post(path, json={}, headers=headers).json
        assert response['code'] == 0, response
        assert response['data'] == {'esignWorkflowRequired': True}
        assert not stages.workflow_choice(report) and not provider.calls
        assert report.status == '检测录入中'
    response = isolated_client.post(path, json={'signingWorkflow': mode}, headers=headers).json
    assert response['code'] == 0, response
    assert stages.workflow_choice(report) == mode
    provider_calls = list(provider.calls)
    audit_count = OperationAudit.query.count()
    state = isolated_client.get(status_path, headers=headers)
    assert state.json['data'] == {
        'status': report.status, 'stillEditable': False, 'esignPending': mode == stages.MODE,
    }
    assert provider.calls == provider_calls
    assert OperationAudit.query.count() == audit_count
    if mode == stages.MODE:
        assert response['data']['esignPending'] and not response['data']['esignPrepareError']
        assert report.status == '检测录入中'
        assert stages.current_flow(report).status == 'signing'
        assert provider.raw == version.pdf_data
        conflict = isolated_client.post(path, json={'signingWorkflow': 'legacy'}, headers=headers).json
        assert conflict['code'] != 0 and '已确定' in conflict['message']
        return
    assert report.status == '待审核'
    assert not stages.current_flow(report) and not provider.calls
    # A legacy completion, including one performed with the switch off, remains legacy.
    isolated_app.config['ESIGN_STAGE_WORKFLOW_ENABLED'] = True
    assert stages.choose_at_completion(report, chief, None) == 'legacy'
    with pytest.raises(service.EsignServiceError, match='已确定'):
        stages.choose_at_completion(report, chief, stages.MODE)


def test_completion_state_respects_department_and_change_stage(sample, scenario_factory, isolated_client):
    report, _, chief, *_, provider = sample
    chief.role_key = 'operator'
    permission = scenario_factory.permission('testing.data_change.view')
    step = ProjectStep.query.filter_by(
        project_id=Project.query.filter_by(name=report.project).one().id, step_code='data_entry').one()
    chief.permissions.append(permission)
    chief.department.permissions.append(permission)
    chief.project_steps.append(step)
    outsider = scenario_factory.user(scenario_factory.department(), permissions=[permission])
    report.status = '检测更改中'
    db.session.commit()
    path = f'/api/reports/{report.report_no}/testinfo-completion-state?view=data_change'
    assert isolated_client.get(path, headers=login_headers(isolated_client, outsider.account)).status_code == 404
    headers = login_headers(isolated_client, chief.account)
    assert isolated_client.get(path, headers=headers).json['data'] == {
        'status': '检测更改中', 'stillEditable': True, 'esignPending': False,
    }
    report.status = '待校核'
    db.session.commit()
    assert isolated_client.get(path, headers=headers).json['data'] == {
        'status': '待校核', 'stillEditable': False, 'esignPending': False,
    }
    assert not provider.calls


@pytest.mark.parametrize('status', ['待审核', '待批准', '待打印'])
def test_inflight_old_reports_cannot_select_new_mode(sample, status):
    from app.audit import add_operation_audit
    report, _, chief, *_ = sample
    report.status = status
    add_operation_audit('report.data_entry.complete', 'report', report.report_no, actor=chief)
    db.session.commit()
    assert stages.choose_at_completion(report, chief, None) == 'legacy'
    with pytest.raises(service.EsignServiceError, match='已确定'):
        stages.choose_at_completion(report, chief, stages.MODE)


def test_old_cancel_retry_never_resets_new_round(active):
    report, version, chief, *_, old = active
    stages.cancel_round(old.id, chief, '第一轮撤回')
    with pytest.raises(service.EsignServiceError, match='已确定'):
        stages.choose_at_completion(report, chief, 'legacy')
    new = stages.begin(report, version, chief)
    db.session.commit()
    result = stages.cancel_round(old.id, chief, '旧请求重试')
    assert result.id == old.id and stages.current_flow(report).id == new.id
    assert new.status == 'ready' and stages.content_blocker(report)


def test_prepare_pending_preview_reads_frozen_pdf(active):
    from app.preview_cache import prepare
    report, version, *_ = active
    result = prepare(report)
    assert result['status'] == 'ready' and result['versionId'] == version.id


def test_changed_upstream_date_evidence_cannot_seal(active):
    report, _, chief, *_, provider, flow = active
    for role in ('chief', 'reviewer', 'approver'):
        advance(active, role)
    for signer in provider.detail['signers']:
        signer['signFields'] = [f for f in signer['signFields'] if not f['customBizNum'].endswith('-APPROVAL-DATE')]
    with pytest.raises(service.EsignServiceError, match='签字完成'):
        unified.confirm(flow.id, chief, flow.source_sha256, report.report_no)
    assert not flow.signed_file_id and report.status == '待打印'
