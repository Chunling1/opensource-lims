"""Report QR compatibility and issuance state, using an isolated DB/file vault."""
import base64
import hashlib
import re
from datetime import datetime
from urllib.parse import urlsplit

import pytest

from app.extensions import db
from app.models import Report, ReportDocumentVersion, ReportEsignFlow
from app.blueprints.report_publication import (
    ReportPublication, ensure_prepared_query, issue, report_qr_url, token_for,
)
from app.functions.esign_service import store_signed_file

pytest_plugins = ('testkit.fixtures',)
ORIGIN = 'https://lims.example.com'
PDF = b'%PDF-1.4\n% isolated QR fixture\n%%EOF'


def make_report(number='TEST-QR-001'):
    report = Report(report_no=number, sample_no=number + '-S', project='虚拟项目',
                    client='虚拟客户', department='虚拟部门', owner='虚拟人员',
                    status='待打印', stamped=False, detail={})
    db.session.add(report)
    db.session.flush()
    row = issue(report)
    version = ReportDocumentVersion(
        report_no=number, output_kind='official', version_no=1, status='approved',
        profile_code='TEST-QR', composition=[], warnings=[],
        snapshot={'approvalDate': '2026-10-16', 'report': {
            'client': '冻结客户', 'project': '冻结项目',
            'detail': {'rawSample': {'sampleName': '冻结样品', 'spec': 'TEST-MODEL',
                                     'quantity': 2, 'projectList': '冻结检测项目'}}}},
        source_hash='isolated-qr-source', sha256=hashlib.sha256(PDF).hexdigest(),
        pdf_data=PDF, created_by='testkit')
    db.session.add(version)
    db.session.flush()
    report.current_document_version_id = report.approved_document_version_id = version.id
    db.session.commit()
    return report, row, version


def sign(report, version, attempt=1, *, sealed=False):
    flow = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
        report_document_version_id=version.id, attempt_no=attempt,
        source_sha256=version.sha256, status='signing',
        positioning_json='{"organizationSeal":{"included":true,"status":"completed"}}' if sealed else '{}')
    db.session.add(flow)
    db.session.flush()
    store_signed_file(flow, PDF)
    db.session.commit()
    return flow


def lookup(client, token):
    return client.post('/api/report-publication/lookup', json={'token': token}, base_url=ORIGIN)


def test_unknown_random_token_is_explicitly_invalid_without_report_data(isolated_app):
    with isolated_app.app_context():
        client = isolated_app.test_client()
        token = '0' * 32
        response = lookup(client, token)
        assert response.status_code == 404
        assert response.json['message'] == '无效二维码，无对应报告'
        assert not response.json.get('data')
        page = client.get('/s/v1/' + token, base_url=ORIGIN)
        assert '无效二维码，无对应报告。' in page.text
        assert 'if (response.status === 404) { fail(notFound); return; }' in page.text
        assert "暂时无法连接报告核验服务" in page.text


def new_token(report):
    return report_qr_url(report).rsplit('/', 1)[1]


def use_legacy_nonce(row):
    row.nonce = 'cd' * 32
    token = token_for(row.nonce)
    row.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.session.commit()
    return token


def test_short_url_is_stable_random_32_hex_without_secret(isolated_app):
    with isolated_app.app_context():
        isolated_app.config.update(REPORT_QUERY_SECRET='', JWT_SECRET='')
        report, row, _ = make_report()
        other, _, _ = make_report('TEST-QR-002')
        url = report_qr_url(report)
        assert re.fullmatch(re.escape(ORIGIN) + r'/s/v1/[0-9a-f]{32}', url)
        assert url == report_qr_url(report) and url != report_qr_url(other)
        assert report.report_no not in url
        token = new_token(report)
        assert token == row.nonce == token_for(row.nonce)
        assert hashlib.sha256(token_for(row.nonce).encode()).hexdigest() == row.token_hash
        client = isolated_app.test_client()
        result = lookup(client, token)
        assert result.status_code == 200
        assert result.json['data']['validity'] == '尚未正式签发'
        page = client.get(urlsplit(url).path, base_url=ORIGIN)
        assert page.status_code == 200 and 'shortMatch' in page.text
        assert page.headers['Referrer-Policy'] == 'no-referrer'
        assert page.headers['Cache-Control'] == 'no-store'
        assert 'nonce-' in page.headers['Content-Security-Policy']
        assert client.get('/api/report-publication/query', base_url=ORIGIN).status_code == 200


def test_old_path_and_fragment_keep_signed_report_snapshot(isolated_app):
    with isolated_app.app_context():
        report, row, version = make_report()
        legacy = use_legacy_nonce(row)
        hex_token = base64.urlsafe_b64decode(legacy + '=').hex()
        original_url = ORIGIN + '/s/v1/' + hex_token
        assert report_qr_url(report) == original_url
        sign(report, version, sealed=True)
        report.stamped = True
        db.session.commit()
        reused, created = ensure_prepared_query(report)
        assert reused.id == row.id and not created
        assert report_qr_url(report) == original_url
        client = isolated_app.test_client()
        path_result = lookup(client, hex_token)
        assert path_result.status_code == 200
        assert path_result.json == lookup(client, legacy).json
        assert path_result.json['data']['validity'] == '正式报告'
        assert path_result.json['data']['facts']['client'] == '冻结客户'
        assert client.get('/s/v1/' + hex_token, base_url=ORIGIN).status_code == 200


def test_new_url_uses_random_value_directly(isolated_app, monkeypatch):
    with isolated_app.app_context():
        from app.blueprints import report_publication
        requested_bytes = []
        def random_hex(size):
            requested_bytes.append(size)
            return '0123456789abcdef' * 2
        monkeypatch.setattr(report_publication.secrets, 'token_hex', random_hex)
        report, _, _ = make_report()
        assert requested_bytes == [16]
        assert new_token(report) == '0123456789abcdef' * 2


def test_formal_report_after_electronic_issuance_without_manual_publication(isolated_app):
    with isolated_app.app_context():
        report, row, version = make_report()
        token = new_token(report)
        client = isolated_app.test_client()
        before = lookup(client, token).json['data']
        assert before['validity'] == '尚未正式签发' and before['facts'] == {}
        flow = sign(report, version, sealed=True)
        signed = lookup(client, token).json['data']
        assert signed['validity'] == '正式报告'
        report.stamped, report.status = True, '待发放'
        report.client = '现在编辑的客户不应影响已签发快照'
        db.session.commit()
        formal = lookup(client, token).json['data']
        assert formal['validity'] == '正式报告'
        assert formal['facts'] == signed['facts']
        assert formal['facts']['client'] == '冻结客户'
        assert formal['facts']['issueDate'] == '2026年10月16日'
        assert not formal['downloadAllowed']
        assert row.published_at is None and row.version_id is None
        assert flow.signed_sha256 == hashlib.sha256(PDF).hexdigest()
        assert client.post('/api/report-publication/download', json={'token': token}, base_url=ORIGIN).status_code == 403
        report.stamped, report.status = False, '待打印'
        db.session.commit()
        assert lookup(client, token).json['data']['validity'] == '正式报告'


@pytest.mark.parametrize('mutation,expected', [
    ('void', '报告已作废'), ('withdraw', '暂停公开'), ('cancelled', '签署文件状态异常'),
    ('version', '已有更新版本'), ('missing_file', '签署文件状态异常'),
])
def test_invalidated_reports_never_show_formal(isolated_app, mutation, expected):
    with isolated_app.app_context():
        report, row, version = make_report()
        flow = sign(report, version)
        report.stamped = True
        token = new_token(report)
        if mutation == 'void': report.voided = True
        elif mutation == 'withdraw': row.withdrawn_reason = '暂停公开'
        elif mutation == 'cancelled': flow.status = 'cancelled'
        elif mutation == 'version': report.approved_document_version_id = None
        elif mutation == 'missing_file': flow.signed_file_id = None
        db.session.commit()
        data = lookup(isolated_app.test_client(), token).json['data']
        assert expected in data['validity'] and not data['downloadAllowed']
        if mutation in ('void', 'withdraw'): assert data['facts'] == {}


def test_original_qr_does_not_follow_later_signed_version(isolated_app):
    with isolated_app.app_context():
        report, row, original = make_report()
        sign(report, original)
        old_token = new_token(report)
        second = ReportDocumentVersion(report_no=report.report_no, output_kind='official',
            version_no=2, status='approved', profile_code='TEST-QR', composition=[], warnings=[],
            snapshot={'report': {'client': '更正客户'}}, source_hash='corrected-source',
            sha256=hashlib.sha256(PDF).hexdigest(), pdf_data=PDF, created_by='testkit')
        db.session.add(second)
        db.session.flush()
        report.approved_document_version_id = report.current_document_version_id = second.id
        sign(report, second)
        report.stamped = True
        db.session.commit()
        data = lookup(isolated_app.test_client(), old_token).json['data']
        assert '已有更新版本' in data['validity']
        assert data['facts']['client'] == '冻结客户'
        # Starting an editable correction must not reuse the old signed QR.
        report.approved_document_version_id = None
        replacement, created = ensure_prepared_query(report)
        assert created and replacement.id != row.id
        assert row.revoked_at is None


@pytest.mark.parametrize('legacy', [False, True])
def test_rotation_and_revocation_cover_both_url_encodings(isolated_app, legacy):
    with isolated_app.app_context():
        report, row, _ = make_report()
        if legacy:
            use_legacy_nonce(row)
        old_hex, old_legacy = new_token(report), token_for(row.nonce)
        row.revoked_at = datetime.utcnow()
        replacement = issue(report)
        db.session.commit()
        client = isolated_app.test_client()
        assert lookup(client, old_hex).status_code == lookup(client, old_legacy).status_code == 404
        assert lookup(client, new_token(report)).status_code == 200
        assert re.fullmatch(r'[0-9a-f]{32}', new_token(report))
        replacement.revoked_at = datetime.utcnow()
        db.session.commit()
        assert lookup(client, token_for(replacement.nonce)).status_code == 404
        with pytest.raises(ValueError, match='停用'):
            ensure_prepared_query(report)


def test_legacy_public_download_grant_does_not_expose_signed_bytes(isolated_app):
    with isolated_app.app_context():
        report, row, version = make_report()
        flow = sign(report, version, sealed=True)
        report.stamped = True
        row.version_id, row.flow_id = version.id, flow.id
        row.artifact_sha256, row.published_at = flow.signed_sha256, datetime.utcnow()
        row.allow_download = True
        db.session.commit()
        token = new_token(report)
        client = isolated_app.test_client()
        assert not lookup(client, token).json['data']['downloadAllowed']
        assert client.post('/api/report-publication/download', json={'token': token}, base_url=ORIGIN).status_code == 403
        report.status = '已发放'; report.archive_state = '归档完成'
        report.detail = {**report.detail, 'reportDelivery': {'released': True, 'versionId': version.id, 'sealedFlowId': flow.id}}
        db.session.commit()
        assert not lookup(client, token).json['data']['downloadAllowed']
        result = client.post('/api/report-publication/download', json={'token': token}, base_url=ORIGIN)
        assert result.status_code == 403
        assert row.allow_download is True  # historical setting retained, no public file access
        row.artifact_sha256 = '0' * 64
        db.session.commit()
        assert not lookup(client, token).json['data']['downloadAllowed']


def test_issuance_guard_rejects_unfinished_organization_seal(isolated_app):
    with isolated_app.app_context():
        report, row, version = make_report()
        flow = sign(report, version)
        report.stamped = True
        db.session.commit()
        isolated_app.config.update(ESIGN_REQUIRED_FOR_ISSUANCE=True, ESIGN_ORG_AUTOSIGN_ENABLED=True)
        data = lookup(isolated_app.test_client(), new_token(report)).json['data']
        assert '签发状态待核实' in data['validity']
        flow.positioning_json = '{"organizationSeal":{"included":true,"status":"completed"}}'
        db.session.commit()
        assert lookup(isolated_app.test_client(), new_token(report)).json['data']['validity'] == '正式报告'


@pytest.mark.parametrize('required', [False, True])
def test_completed_electronic_issuance_is_formal_before_printing(isolated_app, required):
    with isolated_app.app_context():
        isolated_app.config['ESIGN_REQUIRED_FOR_ISSUANCE'] = required
        report, row, version = make_report()
        flow = sign(report, version)
        token = new_token(report)
        client = isolated_app.test_client()
        # Personnel signatures alone never satisfy the new rule.
        assert lookup(client, token).json['data']['validity'] == '尚未正式签发'
        flow.positioning_json = '{"organizationSeal":{"included":true,"status":"completed"}}'
        db.session.commit()
        result = lookup(client, token).json['data']
        assert result['validity'] == '正式报告'
        assert result['facts']['client'] == '冻结客户'
        assert report.status == '待打印' and not report.stamped
        assert row.published_at is None and not result['downloadAllowed']
        assert client.post('/api/report-publication/download', json={'token': token}, base_url=ORIGIN).status_code == 403
        row.withdrawn_reason = '暂停公开'
        db.session.commit()
        assert lookup(client, token).json['data']['validity'] == '暂停公开'


def test_explicit_qr_rebind_uses_new_signed_snapshot_without_rewriting_files(isolated_app):
    with isolated_app.app_context():
        report, row, old = make_report()
        old_flow = sign(report, old)
        token = new_token(report)
        current = ReportDocumentVersion(report_no=report.report_no, output_kind='official',
            version_no=2, status='approved', profile_code='TEST-QR', composition=[], warnings=[],
            snapshot={'approvalDate': '2026-10-23', 'report': {'client': '本次确认客户'}},
            source_hash='new-source', sha256=hashlib.sha256(PDF).hexdigest(), pdf_data=PDF, created_by='testkit')
        db.session.add(current)
        db.session.flush()
        report.current_document_version_id = report.approved_document_version_id = current.id
        latest = sign(report, current, attempt=2)
        latest.positioning_json = '{"organizationSeal":{"included":true,"status":"completed"}}'
        db.session.commit()
        client = isolated_app.test_client()
        assert '已有更新版本' in lookup(client, token).json['data']['validity']
        row.version_id, row.flow_id, row.artifact_sha256 = current.id, latest.id, latest.signed_sha256
        db.session.commit()
        result = lookup(client, token).json['data']
        assert result['validity'] == '正式报告'
        assert result['facts']['client'] == '本次确认客户'
        assert result['facts']['issueDate'] == '2026年10月23日'
        assert new_token(report) == token and row.published_at is None
        assert not result['downloadAllowed'] and not report.stamped
        assert old.pdf_data == current.pdf_data == PDF
        assert old_flow.signed_sha256 == latest.signed_sha256 == hashlib.sha256(PDF).hexdigest()


def test_real_issuance_command_makes_prepared_qr_formal(isolated_app, scenario_factory, monkeypatch):
    from app.applications.report_lifecycle import commands
    from app.audit import add_operation_audit
    with isolated_app.app_context():
        scenario = scenario_factory.identity_scenario(
            permission_codes=('report.print.view',), granted_step_codes=('report_print',))
        scenario_factory.grant_action(scenario.user, 'report.print.pass')
        report, row, version = make_report()
        report.department, report.project, report.owner = scenario.department.name, scenario.project.name, scenario.user.name
        report.sample_reg_state = '登记完成'
        add_operation_audit('report.approval.pass', 'report', report.report_no,
                            category='workflow', actor=scenario.user)
        db.session.commit()
        sign(report, version, sealed=True)
        isolated_app.config['ESIGN_REQUIRED_FOR_ISSUANCE'] = True
        # Cover rendering is unrelated to the state transition and needs real templates.
        result = commands.execute_report_action(scenario.user, report.report_no, 'report.print.pass')
        assert result.code != 0  # seal callback already advanced the report
        assert report.status == "待发放"
        assert report.stamped
        assert row.published_at is None
        assert lookup(isolated_app.test_client(), new_token(report)).json['data']['validity'] == '正式报告'


def test_short_route_enforces_transport_format_and_rate_limit(isolated_app):
    client = isolated_app.test_client()
    path = '/s/v1/' + 'a' * 32
    assert client.get(path, base_url='http://localhost').status_code == 400
    assert client.get('/s/v1/not-a-token', base_url=ORIGIN).status_code == 404
    assert lookup(client, 'a' * 64).status_code == 404
    assert lookup(client, 'a' * 65).status_code == 404
    for invalid in ('a' * 31, 'a' * 33, 'A' * 32, 'g' * 32):
        assert client.get('/s/v1/' + invalid, base_url=ORIGIN).status_code == 404
        assert lookup(client, invalid).status_code == 404
    class Deny:
        def accept(self, *_args): return False
    isolated_app.extensions['report_query_limiter'] = Deny()
    response = client.get(path, base_url=ORIGIN)
    assert response.status_code == 429 and response.headers['Retry-After'] == '60'
