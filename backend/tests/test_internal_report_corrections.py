import hashlib
import json
import pytest
from app.extensions import db
from app.models import Report, ReportDocumentVersion, ReportEsignFlow, ReportCorrectionRequest, OperationAudit
from app.internal_report_corrections import history_for, is_historical_flow, blocks_new_request
from app.audit import add_operation_audit
from test_report_correction_approval import actors, submit, approve_both

pytest_plugins = ('testkit.fixtures',)
PDF = b'%PDF-1.4\n% immutable original\n%%EOF'


def previous_version(status='completed'):
    report = Report.query.filter_by(report_no='TEST-CORRECTION').one()
    version = ReportDocumentVersion(report_no=report.report_no, output_kind='official', version_no=1,
        status='approved', profile_code='TEST', snapshot={'approvalDate': '2026-10-24'},
        sha256=hashlib.sha256(PDF).hexdigest(), source_hash='original', pdf_data=PDF)
    db.session.add(version); db.session.flush()
    report.current_document_version_id = report.approved_document_version_id = version.id
    report.stamped = True
    flow = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
        report_document_version_id=version.id, source_sha256=version.sha256,
        provider_flow_id='isolated-old', status=status, positioning_json='{}')
    db.session.add(flow)
    add_operation_audit('report.approval.pass', 'report', report.report_no, category='workflow')
    db.session.commit()
    return report, version, flow


@pytest.mark.parametrize('mode,status', [('data_only', '检测更改中'), ('entrust_only', '委托更改中'), ('entrust_and_data', '委托更改中')])
def test_history_and_original_bytes_survive_same_number_edit(actors, isolated_client, mode, status):
    from app.esign_access import flow_state_error
    from app.report_final_fields import approval_date
    from app.blueprints.report_assurance import resolve_artifact
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'], returnMode=mode)['data']['id']
    result = approve_both(isolated_client, actors, rid)
    assert result['code'] == 0, result
    assert Report.query.count() == 1 and report.status == status
    assert report.approved_document_version_id is None and report.current_document_version_id is None
    assert not report.stamped and approval_date(report) == ''
    assert version.pdf_data == PDF and version.snapshot == {'approvalDate': '2026-10-24'}
    assert flow.status == 'completed' and flow.provider_flow_id == 'isolated-old'
    assert is_historical_flow(flow) and '历史版本' in flow_state_error(flow)
    with pytest.raises(ValueError, match='尚无当前'):
        resolve_artifact(report)
    endpoint = f'/api/reports/correction-requests/{rid}/history'
    old = isolated_client.get(endpoint, headers=actors['approver']).json['data']
    assert old['report']['status'] == '待打印'
    assert old['versions'][0]['id'] == version.id
    report.client = '更正后的客户'; db.session.commit()
    assert isolated_client.get(endpoint, headers=actors['approver']).json['data'] == old
    assert isolated_client.get(endpoint, headers=actors['outsider']).status_code == 404
    response = isolated_client.get(f'{endpoint}/version/{version.id}/pdf', headers=actors['approver'])
    assert response.status_code == 200 and response.data == PDF
    assert isolated_client.get(f'{endpoint}/version/99999/pdf', headers=actors['approver']).status_code == 400
    assert isolated_client.get('/api/esign/reports/TEST-CORRECTION', headers=actors['approver']).json['data'] is None


def test_active_provider_signing_must_be_cancelled_before_correction(actors, isolated_client):
    report, version, flow = previous_version('signing')
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    result = approve_both(isolated_client, actors, rid)
    assert result['code'] != 0 and '先撤销' in result['message']
    assert report.status == '待打印' and report.approved_document_version_id == version.id
    assert db.session.get(ReportCorrectionRequest, rid).status == 'pending_leader'
    assert history_for(rid) is None and not is_historical_flow(flow)


@pytest.mark.parametrize('status', ['cancelled', 'expired', 'rejected'])
def test_terminal_provider_history_does_not_block_correction(actors, isolated_client, status):
    report, version, flow = previous_version(status)
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    assert flow.status == status and is_historical_flow(flow)


def test_history_write_failure_rolls_back_everything(actors, isolated_client, monkeypatch):
    from app import internal_report_corrections as module
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    original = module.add_operation_audit
    def fail(action, *args, **kwargs):
        if action == 'report.correction.internal.approved':
            raise RuntimeError('isolated audit failure')
        return original(action, *args, **kwargs)
    monkeypatch.setattr(module, 'add_operation_audit', fail)
    assert approve_both(isolated_client, actors, rid)['code'] != 0
    assert report.status == '待打印' and report.approved_document_version_id == version.id
    assert flow.positioning_json == '{}' and history_for(rid) is None
    assert db.session.get(ReportCorrectionRequest, rid).status == 'pending_leader'


def test_reapproval_allows_another_internal_correction_and_old_qr_stays_old(actors, isolated_client):
    from app.blueprints.report_publication import issue, public_state, ensure_prepared_query
    report, old_version, flow = previous_version()
    qr = issue(report); qr.version_id = old_version.id; qr.flow_id = flow.id; db.session.commit()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    assert '更正' in public_state(qr)[1]
    new_qr, created = ensure_prepared_query(report)
    assert created and new_qr.id != qr.id and qr.version_id == old_version.id
    assert submit(isolated_client, actors['applicant'])['code'] != 0
    version = ReportDocumentVersion(report_no=report.report_no, output_kind='official', version_no=2,
        status='approved', profile_code='TEST', snapshot={}, sha256='new', source_hash='new', pdf_data=PDF)
    db.session.add(version); db.session.flush()
    report.status = '待打印'; report.approved_document_version_id = report.current_document_version_id = version.id
    db.session.commit()
    row = db.session.get(ReportCorrectionRequest, rid)
    assert not blocks_new_request(row, report)
    assert '原版本' in public_state(qr)[1]
    assert submit(isolated_client, actors['applicant'])['code'] == 0


def test_late_callback_cannot_reactivate_old_flow(actors, isolated_client, monkeypatch):
    from app.blueprints import esign
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    monkeypatch.setattr(esign, 'verify_callback_signature', lambda *args: True)
    monkeypatch.setitem(isolated_client.application.config, 'EXTERNAL_SIDE_EFFECTS_ENABLED', True)
    def no_provider(*args, **kwargs):
        raise AssertionError('Historical callback must not call provider')
    monkeypatch.setattr(esign.EsignV3Client, 'request', no_provider)
    response = isolated_client.post('/api/esign/callback', json={
        'action': 'SIGN_FLOW_FINISH', 'signFlowId': flow.provider_flow_id, 'signFlowStatus': 2})
    assert response.json['code'] == 0
    assert report.status == '检测更改中' and report.approved_document_version_id is None
    assert flow.status == 'completed' and is_historical_flow(flow)


def test_legacy_gz_consolidation_preserves_edits_and_archives_row(actors, isolated_client):
    from app.internal_report_corrections import consolidate_legacy_internal
    from app.models import User
    from app.applications.report_lifecycle import scoped_report_query
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'], 'external')['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    row = db.session.get(ReportCorrectionRequest, rid); row.correction_type = 'internal'
    old = Report.query.filter_by(report_no='TEST-CORRECTIONGZ').one()
    old.client = '已更改的委托单位'
    old.detail = {**old.detail, 'rawSample': {'reportNo': old.report_no, 'taskSource': '已修改'},
                  'reportComposition': {}}
    actor = User.query.filter_by(account='correction-admin').one()
    db.session.commit()
    result = consolidate_legacy_internal(rid, actor, main_id=report.id, derivative_id=old.id)
    db.session.commit()
    assert result.id == report.id and result.report_no == 'TEST-CORRECTION'
    assert result.client == '已更改的委托单位' and result.status == '检测更改中'
    assert result.detail['rawSample'] == {'reportNo': 'TEST-CORRECTION', 'taskSource': '已修改'}
    assert old.voided and old.report_kind == 'correction_history'
    assert Report.query.count() == 2  # retained, never deleted
    assert [r.id for r in scoped_report_query(Report.query, actor).all()] == [report.id]
    assert version.pdf_data == PDF and flow.status == 'completed'
    assert history_for(rid).before_data['report']['client'] != result.client
    with pytest.raises(ValueError):
        consolidate_legacy_internal(rid, actor, main_id=report.id, derivative_id=old.id)


def test_signed_history_returns_original_file_and_rejects_hash_change(actors, isolated_client):
    from app.functions.esign_service import store_signed_file
    report, version, flow = previous_version()
    store_signed_file(flow, PDF)
    db.session.commit()
    file_id, digest = flow.signed_file_id, flow.signed_sha256
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    endpoint = f'/api/reports/correction-requests/{rid}/history/signed/{flow.id}/pdf'
    response = isolated_client.get(endpoint, headers=actors['approver'])
    assert response.status_code == 410
    from app.internal_report_corrections import history_pdf
    assert history_pdf(history_for(rid), 'signed', flow.id) == PDF
    assert flow.signed_file_id == file_id and flow.signed_sha256 == digest
    assert isolated_client.get(endpoint, headers=actors['outsider']).status_code == 404
    audit = history_for(rid)
    snapshot = dict(audit.before_data)
    snapshot['flows'] = [{**snapshot['flows'][0], 'signedSha256': '0' * 64}]
    audit.before_data = snapshot; db.session.commit()
    assert isolated_client.get(endpoint, headers=actors['approver']).status_code == 410
    with pytest.raises(ValueError):
        history_pdf(audit, 'signed', flow.id)


def test_maintenance_dry_run_and_stale_state_gate(actors, isolated_client, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[1] / 'scripts/consolidate_internal_correction.py'
    spec = importlib.util.spec_from_file_location('consolidation_script', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'create_app', lambda: isolated_client.application)
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'], 'external')['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    row = db.session.get(ReportCorrectionRequest, rid); row.correction_type = 'internal'
    old = Report.query.filter_by(report_no='TEST-CORRECTIONGZ').one(); db.session.commit()
    args = SimpleNamespace(request_id=rid, main_id=report.id, derivative_id=old.id,
                           actor='correction-admin', apply=False, expected_sha256='')
    module.run(args)
    preview = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    db.session.expire_all()
    assert not old.voided and history_for(rid) is None
    args.apply = True; args.expected_sha256 = preview['beforeSha256']
    old.client = '预演后变化'; db.session.commit()
    with pytest.raises(ValueError, match='摘要'):
        module.run(args)
    args.apply = False; module.run(args)
    preview = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    args.apply = True; args.expected_sha256 = preview['beforeSha256']
    module.run(args)
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result['applied'] is True
    db.session.expire_all()
    assert old.voided and report.client == '预演后变化' and history_for(rid)


def test_history_stays_reachable_during_new_round(actors, isolated_client):
    report, version, flow = previous_version()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert approve_both(isolated_client, actors, rid)['code'] == 0
    def listed(headers):
        response = isolated_client.post('/api/reports/query', json={'view': 'change_request'}, headers=headers).json
        assert response['code'] == 0
        return [row['reportNo'] for row in response['data']['rows']]
    for status in ('委托更改中', '检测更改中', '待审核', '待批准', '待打印'):
        report.status = status
        db.session.commit()
        assert listed(actors['approver']) == ['TEST-CORRECTION']
        detail = isolated_client.get('/api/reports/TEST-CORRECTION?view=change_request', headers=actors['approver']).json
        assert detail['code'] == 0
        assert listed(actors['outsider']) == []
    report.voided = True
    db.session.commit()
    assert listed(actors['approver']) == []
    report.voided = False
    report.status = '检测更改中'
    report.detail = {}
    db.session.commit()
    assert listed(actors['approver']) == []
