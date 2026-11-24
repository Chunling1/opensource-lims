"""Typed correction applications with independent two-stage approvals."""
from io import BytesIO
import pytest
from app.extensions import db
from app.models import Report, ReportCorrectionRequest, ReportAttachment, ReportDocumentVersion, User, user_action_permissions
from app.report_correction_permissions import assign, authorization_payload
from testkit.factories import login_headers
from test_report_derivatives import _main_report

pytest_plugins = ("testkit.fixtures",)
BASE = '/api/reports/TEST-CORRECTION/correction-requests'
LEVEL1 = 'correctionApprovalLevel1'
LEVEL2 = 'correctionApprovalLevel2'

@pytest.fixture()
def actors(scenario_factory, isolated_client):
    dept = scenario_factory.department()
    applicant = scenario_factory.user(dept, account='applicant', permissions=('report.change_request.view',))
    approver = scenario_factory.user(dept, account='approver', permissions=('report.change_request.view',))
    institute = scenario_factory.department(name='虚拟示例国检院')
    leader = scenario_factory.user(institute, account='leader', permissions=('report.change_request.view',))
    scenario_factory.grant_data_department(leader, dept)
    admin = scenario_factory.user(dept, account='correction-admin', role_key='admin')
    stranger = scenario_factory.user(scenario_factory.department(), account='outsider', permissions=('report.change_request.view',))
    for user, grant in ((approver, LEVEL1), (leader, LEVEL2), (stranger, LEVEL1)):
        assign(user, grant, True)
    _main_report('TEST-CORRECTION', dept.name)
    db.session.commit()
    return {u.account: login_headers(isolated_client, u.account) for u in [applicant, approver, leader, admin, stranger]}

def submit(client, headers, kind='internal', **changes):
    data = {'reason': '虚拟日期更正', 'returnMode': 'data_only', 'correctionType': kind,
            'internalFile': (BytesIO(b'%PDF-1.4 internal approval'), 'internal.pdf')}
    if kind == 'external': data['receiptFile'] = (BytesIO(b'%PDF-1.4 customer receipt'), 'receipt.pdf')
    data.update(changes)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(BASE, data=data, headers=headers).get_json()

def decide(client, headers, rid, decision='approve', note='审核附件齐全', *, stage='pending_director'):
    return client.post(f'/api/reports/correction-requests/{rid}/decision', headers=headers,
                       json={'stage': stage, 'decision': decision, 'note': note}).get_json()


def approve_both(client, actors, rid):
    result = decide(client, actors['approver'], rid)
    assert result.get('data', {}).get('status') == 'pending_leader', result
    return decide(client, actors['leader'], rid, stage='pending_leader')

@pytest.mark.parametrize('a2', [False, True])
def test_correction_list_searches_and_filters_before_pagination(actors, isolated_client, a2):
    isolated_client.application.config['LIST_QUERY_A2'] = a2
    main = Report.query.filter_by(report_no='TEST-CORRECTION').one()
    result = submit(isolated_client, actors['applicant'], 'external')
    assert result['code'] == 0, result
    for index in range(14):
        _main_report(f'QA-2026V-{index:04d}', main.department)
    db.session.commit()

    def fetch(actor='approver', **params):
        result = isolated_client.post('/api/reports/query', headers=actors[actor], json={
            'view': 'change_request', 'presentation': 'report', 'serverPage': True,
            'sort': 'reportNo', 'direction': 'asc', 'pageSize': 12, **params,
        }).get_json()
        assert result['code'] == 0, result
        return result['data']

    first = fetch()
    assert first['total'] == 15 and len(first['rows']) == 12
    assert all(row['reportNo'] != main.report_no for row in first['rows'])
    assert any(row['reportNo'] == main.report_no for row in fetch(page=2)['rows'])
    assert [row['reportNo'] for row in fetch(keyword='correction', correctionStatus='pending_director')['rows']] == [main.report_no]
    assert fetch(keyword='correction', correctionStatus='none')['total'] == 0
    assert fetch(keyword='2026v-', correctionStatus='none')['total'] == 14
    assert fetch('outsider', keyword='correction')['total'] == 0
    rid = result['data']['id']
    assert decide(isolated_client, actors['approver'], rid)['data']['status'] == 'pending_leader'
    assert fetch(keyword='correction', correctionStatus='pending_leader')['total'] == 1
    assert decide(isolated_client, actors['leader'], rid, 'reject', stage='pending_leader')['code'] == 0
    assert fetch(keyword='correction', correctionStatus='none')['total'] == 1


@pytest.mark.parametrize('server_page', [False, True])
def test_report_query_hides_original_before_pagination_and_preserves_history(
        actors, isolated_client, server_page):
    isolated_client.application.config['LIST_QUERY_A2'] = False
    headers = actors['correction-admin']
    original = Report.query.filter_by(report_no='TEST-CORRECTION').one()
    original.status = '已发放'
    historical_pdf = b'%PDF-1.4 original'
    version = ReportDocumentVersion(report_no=original.report_no, output_kind='official', version_no=1,
        profile_code='TEST-PROFILE', snapshot={}, source_hash='original', sha256='f' * 64, pdf_data=historical_pdf)
    english = _main_report(f'{original.report_no}(E)', original.department)
    english.main_report_no, english.report_kind = original.report_no, 'english'
    db.session.add(version)
    db.session.commit()
    version_id = version.id

    def fetch(**params):
        result = isolated_client.post('/api/reports/query', headers=headers, json={
            'view': 'query', 'presentation': 'report', 'serverPage': server_page,
            'keyword': original.report_no, 'searchField': 'reportCode',
            'sort': 'reportNo', 'page': 1, 'pageSize': 1, **params,
        }).get_json()
        assert result['code'] == 0, result
        return result['data']

    request_id = submit(isolated_client, actors['applicant'], 'external')['data']['id']
    assert fetch()['total'] == 2
    assert approve_both(isolated_client, actors, request_id)['code'] == 0
    correction = Report.query.filter_by(main_report_no=original.report_no, report_kind='correction').one()
    assert fetch()['total'] == 2
    pages = [fetch(page=page)['rows'] for page in (1, 2)]
    assert {row['reportNo'] for rows in pages for row in rows} == {english.report_no, correction.report_no}
    assert original.report_no in {row['reportNo'] for row in fetch(presentation='entry', pageSize=10)['rows']}
    assert isolated_client.get(f'/api/reports/{original.report_no}?view=query', headers=headers).json['code'] == 0
    assert db.session.get(ReportDocumentVersion, version_id).pdf_data == historical_pdf
    assert original.status == '已发放' and not original.voided
    assert db.session.get(ReportCorrectionRequest, request_id).correction_report_no == correction.report_no
    plan_counts = isolated_client.post('/api/reports/plan-counts', headers=headers, json={'view': 'query'}).json
    assert sum(row['sampleCount'] for row in plan_counts['data']['rows']) == 2
    correction.voided = True
    db.session.commit()
    assert original.report_no in {row['reportNo'] for row in fetch(pageSize=10)['rows']}


@pytest.mark.parametrize('kind', ['internal', 'external'])
def test_two_approvals_use_type_specific_numbering(actors, isolated_client, kind):
    result = submit(isolated_client, actors['applicant'], kind)
    assert result['code'] == 0, result
    rid = result['data']['id']
    assert result['data']['status'] == 'pending_director'
    assert Report.query.count() == 1
    assert ReportAttachment.query.count() == (2 if kind == 'external' else 1)
    assert decide(isolated_client, actors['leader'], rid)['code'] == 403
    assert decide(isolated_client, actors['approver'], rid)['data']['status'] == 'pending_leader'
    assert Report.query.count() == 1
    assert decide(isolated_client, actors['leader'], rid)['code'] != 0
    result = decide(isolated_client, actors['leader'], rid, stage='pending_leader')
    assert result['code'] == 0, result
    assert result['data']['status'] == 'approved'
    assert result['data']['directorAccount'] == 'approver'
    assert result['data']['leaderAccount'] == 'leader'
    if kind == 'external':
        assert Report.query.filter_by(report_no='TEST-CORRECTION').one().status == '待打印'
        assert Report.query.filter_by(report_no='TEST-CORRECTIONGZ').one().status == '检测更改中'
    else:
        assert Report.query.filter_by(report_no='TEST-CORRECTION').one().status == '检测更改中'
        assert result['data']['hasHistory'] is True
        assert result['data']['correctionReportNo'] == 'TEST-CORRECTION'
    assert decide(isolated_client, actors['leader'], rid, stage='pending_leader')['code'] != 0
    assert Report.query.count() == (2 if kind == 'external' else 1)

@pytest.mark.parametrize('kind,changes,message', [
    ('internal', {'internalFile': None}, '内部签字'),
    ('external', {'internalFile': None}, '内部签字'),
    ('external', {'receiptFile': None}, '甲方回执'),
    ('internal', {'correctionType': ''}, '请选择'),
    ('internal', {'reason': ' '}, '原因'),
    ('internal', {'returnMode': 'other'}, '请选择'),
    ('internal', {'internalFile': (b'', 'empty.pdf')}, '不能为空'),
    ('external', {'receiptFile': (b'fake', 'receipt.exe')}, '仅支持'),
])
def test_invalid_application_persists_nothing(actors, isolated_client, kind, changes, message):
    changes = {k: (BytesIO(v[0]), v[1]) if isinstance(v, tuple) else v for k, v in changes.items()}
    result = submit(isolated_client, actors['applicant'], kind, **changes)
    assert result['code'] != 0 and message in result['message'], result
    assert ReportCorrectionRequest.query.count() == ReportAttachment.query.count() == 0

def test_receipt_oversize_does_not_persist_first_file(actors, isolated_client, isolated_app):
    isolated_app.config['MAX_FILE_BYTES'] = 32
    result = submit(isolated_client, actors['applicant'], 'external', receiptFile=(BytesIO(b'x'*33), 'r.pdf'))
    assert result['code'] != 0
    assert ReportAttachment.query.count() == 0

def test_permission_scope_revocation_and_duplicate_submission(actors, isolated_client):
    result = submit(isolated_client, actors['applicant'], 'external'); rid = result['data']['id']
    assert submit(isolated_client, actors['applicant'])['code'] != 0
    assert decide(isolated_client, actors['applicant'], rid)['code'] == 403
    assert decide(isolated_client, actors['outsider'], rid)['code'] != 0
    assert isolated_client.get('/api/reports/correction-requests', headers=actors['outsider']).json['data']['rows'] == []
    assert isolated_client.get('/api/reports/correction-requests', headers=actors['approver']).json['data']['rows'][0]['canApproveDirector']
    approver = User.query.filter_by(account='approver').one(); assign(approver, LEVEL1, False); db.session.commit()
    assert decide(isolated_client, actors['approver'], rid)['code'] == 403
    assert ReportCorrectionRequest.query.one().status == 'pending_director'

def test_page_permission_required_even_with_approval_grant(actors, isolated_client):
    approver = User.query.filter_by(account='approver').one(); approver.permissions = []; db.session.commit()
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert decide(isolated_client, actors['approver'], rid)['code'] == 403
    assert isolated_client.get('/api/reports/correction-requests', headers=actors['approver']).json['code'] == 403


def test_same_account_cannot_complete_both_levels_even_with_both_grants(actors, isolated_client):
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert decide(isolated_client, actors['approver'], rid)['data']['status'] == 'pending_leader'
    approver = User.query.filter_by(account='approver').one()
    assign(approver, LEVEL2, True)
    db.session.commit()
    assert decide(isolated_client, actors['approver'], rid, stage='pending_leader')['code'] == 403
    assert decide(isolated_client, actors['leader'], rid, stage='pending_leader')['data']['status'] == 'approved'

@pytest.mark.parametrize('actor,stage,note_field', [('approver','pending_director','directorNote'), ('leader','pending_leader','leaderNote')])
def test_reject_requires_reason_and_allows_resubmit(actors, isolated_client, actor, stage, note_field):
    submitted = submit(isolated_client, actors['applicant'])
    assert submitted['code'] == 0, submitted
    rid = submitted['data']['id']
    if stage == 'pending_leader':
        assert decide(isolated_client, actors['approver'], rid)['code'] == 0
    assert decide(isolated_client, actors[actor], rid, 'reject', '', stage=stage)['code'] != 0
    result = decide(isolated_client, actors[actor], rid, 'reject', '内部签字不完整', stage=stage)
    assert result['data']['status'] == 'rejected'
    assert result['data'][note_field] == '内部签字不完整'
    assert result['data']['applicationAttachment']['id'] == submitted['data']['applicationAttachment']['id']
    assert Report.query.count() == 1
    assert submit(isolated_client, actors['applicant'])['code'] == 0
    assert ReportCorrectionRequest.query.count() == 2

def test_organization_grants_are_independent_and_explicit_for_admins(actors, isolated_client):
    user = User.query.filter_by(account='correction-admin').one()
    url = f'/api/admin/departments/{user.department_id}/members/{user.id}/authorizations'
    assert authorization_payload(user) == {LEVEL1: False, LEVEL2: False}
    for changes, expected in [({LEVEL1: True}, {LEVEL1: True, LEVEL2: False}),
                              ({LEVEL2: True}, {LEVEL1: True, LEVEL2: True}),
                              ({LEVEL1: False}, {LEVEL1: False, LEVEL2: True})]:
        response = isolated_client.put(url, json=changes, headers=actors['correction-admin']).json
        assert response['code'] == 0, response
        assert {field: response['data'][field] for field in expected} == expected
        assert isolated_client.put(url, json={}, headers=actors['correction-admin']).json['code'] == 0
        assert authorization_payload(user) == expected
    assert isolated_client.put(url, json={LEVEL1: 'true'}, headers=actors['correction-admin']).json['code'] != 0
    assert isolated_client.put(url, json={LEVEL1: True}, headers=actors['applicant']).json['code'] == 403
    saved = isolated_client.put(f'/api/admin/users/{user.id}', json={'actionPermissions': []},
                                headers=actors['correction-admin']).json
    assert saved['code'] == 0, saved
    assert authorization_payload(user) == {LEVEL1: False, LEVEL2: True}

def test_attachment_download_uses_page_scope(actors, isolated_client):
    result = submit(isolated_client, actors['applicant'], 'external')['data']
    for att in (result['applicationAttachment'], result['receiptAttachment']):
        url = f'/api/attachments/{att["id"]}?view=change_request&download=1'
        response = isolated_client.get(url, headers=actors['approver'])
        assert response.status_code == 200 and response.data.startswith(b'%PDF-1.4'), response.data
        assert isolated_client.get(url, headers=actors['outsider']).json['code'] != 0

def test_failure_during_clone_rolls_back_decision(actors, isolated_client, monkeypatch):
    from app.blueprints import reports
    rid = submit(isolated_client, actors['applicant'], 'external')['data']['id']
    def fail(*a, **kw): raise RuntimeError('isolated storage failure')
    monkeypatch.setattr(reports, '_clone_derived_report', fail)
    assert approve_both(isolated_client, actors, rid)['code'] != 0
    assert db.session.get(ReportCorrectionRequest, rid).status == 'pending_leader'
    assert Report.query.count() == 1

def test_legacy_single_pending_returns_to_first_stage_without_inheriting_grants(actors, isolated_client):
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    row = db.session.get(ReportCorrectionRequest, rid)
    row.status = 'pending_approval'
    admin = User.query.filter_by(account='correction-admin').one()
    db.session.execute(user_action_permissions.insert().values(user_id=admin.id, action_code='report.correction.approve'))
    db.session.commit()
    assert decide(isolated_client, actors['correction-admin'], rid)['code'] == 403
    result = isolated_client.get('/api/reports/correction-requests', headers=actors['approver']).json
    assert result['data']['rows'][0]['status'] == 'pending_director'
    assert approve_both(isolated_client, actors, rid)['data']['status'] == 'approved'

def test_competing_approvals_create_one_derivative(actors, isolated_client, isolated_app, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.blueprints import reports
    rid = submit(isolated_client, actors['applicant'])['data']['id']
    assert decide(isolated_client, actors['approver'], rid)['code'] == 0
    original = reports._correction_projection
    barrier = Barrier(2)
    def synchronize(row, user):
        result = original(row, user)
        if row.status == 'pending_leader': barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(reports, '_correction_projection', synchronize)
    def run(account):
        with isolated_app.test_client() as client:
            return decide(client, actors[account], rid, stage='pending_leader')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ['leader', 'leader']))
    assert sum(result['code'] == 0 for result in results) == 1, results
    db.session.expire_all()
    assert Report.query.count() == 1
    assert Report.query.one().status == '检测更改中'
    from app.internal_report_corrections import HISTORY_ACTION
    from app.models import OperationAudit
    assert OperationAudit.query.filter_by(action=HISTORY_ACTION).count() == 1
    assert db.session.get(ReportCorrectionRequest, rid).status == 'approved'

def test_additive_migration_preserves_legacy_row(tmp_path):
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module_path = Path(__file__).resolve().parents[1] / 'migrations/versions/c9f204a61e78_report_correction_approval.py'
    spec = importlib.util.spec_from_file_location('correction_migration', module_path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = sa.create_engine(f'sqlite:///{tmp_path / "migration.sqlite"}')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE report_attachments (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE report_correction_requests (id INTEGER PRIMARY KEY, status VARCHAR(32), reason TEXT)')
        conn.exec_driver_sql("INSERT INTO report_correction_requests VALUES (7, 'pending_leader', 'legacy evidence')")
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        row = conn.exec_driver_sql('SELECT status, reason, correction_type, approver_at FROM report_correction_requests WHERE id=7').one()
        assert row == ('pending_leader', 'legacy evidence', None, None)
        assert any(fk['name'] == 'fk_correction_receipt' for fk in sa.inspect(conn).get_foreign_keys('report_correction_requests'))
    engine.dispose()

def test_pending_correction_changes_public_lookup_state(actors, isolated_client):
    from app.blueprints.report_publication import issue, public_state
    report = Report.query.filter_by(report_no='TEST-CORRECTION').one()
    publication = issue(report); db.session.commit()
    submit(isolated_client, actors['applicant'], 'external')
    assert public_state(publication)[1] == '报告更正中'

def test_referenced_evidence_cannot_be_removed(actors, isolated_client, monkeypatch):
    from app.blueprints import attachments
    evidence = submit(isolated_client, actors['applicant'])['data']['applicationAttachment']
    # Reach the existing editable-attachment handler without weakening the correction evidence guard.
    monkeypatch.setattr(attachments, 'report_data_entry_step_error', lambda *a: '')
    monkeypatch.setattr(attachments, 'report_content_editable', lambda *a: True)
    result = isolated_client.delete(f'/api/attachments/{evidence["id"]}', headers=actors['correction-admin']).json
    assert result['code'] != 0 and '审批历史记录' in result['message'], result
    assert db.session.get(ReportAttachment, evidence['id']).deleted_at is None
