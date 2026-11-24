"""List reads must not hydrate documents, images or audit form snapshots."""
import json
import pytest
from sqlalchemy import event, inspect
from app.extensions import db
from app.models import Report, Entrust, Agreement, OperationAudit
from app.list_projection import list_reports, list_entrusts, list_agreements
from app.list_reads import reuse_list_reads
from app.audit import records_by_edit_time, latest_operation_audit
from app.business_rows import report_business_row
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


def headers(user):
    return {'Authorization': 'Bearer ' + issue_token(user)}


@pytest.fixture
def workspace(isolated_app, scenario_factory):
    f = scenario_factory
    dept_a = f.department(name='检测一部')
    dept_b = f.department(name='检测二部')
    perms = ['entrust.query.view', 'entrust.registration.view']
    user = f.user(dept_a, permissions=perms)
    peer = f.user(dept_a, permissions=perms)
    other = f.user(dept_b, permissions=perms)
    return isolated_app.test_client(), (user, peer, other), f


def test_mysql_projection_keeps_missing_slots_in_one_parse():
    from sqlalchemy import literal, select
    from sqlalchemy.dialects import mysql
    from app.list_projection import _projection_values
    sql = str(select(_projection_values(literal('{}'), ['$.missing', '$.present']))
              .compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
    assert sql.count('JSON_TABLE(') == 1
    assert "c0 JSON PATH '$.missing' NULL ON EMPTY" in sql
    assert "c1 JSON PATH '$.present' NULL ON EMPTY" in sql
    assert 'JSON_ARRAY(list_json.c0, list_json.c1)' in sql


def test_sparse_projection_preserves_json_types_and_single_path(isolated_app):
    from sqlalchemy import literal, select
    from app.list_projection import _projection_values
    with isolated_app.app_context():
        value = {'present':'text', 'nested':{'x':1}, 'items':[1,2], 'flag':False, 'nil':None}
        paths = ['$.missing', '$.present', '$.nested', '$.items', '$.flag', '$.nil']
        result = db.session.execute(select(_projection_values(literal(json.dumps(value)), paths))).scalar()
        assert json.loads(result) == [None, 'text', {'x':1}, [1,2], False, None]
        single = db.session.execute(select(_projection_values(literal(json.dumps(value)), ['$.items']))).scalar()
        assert json.loads(single) == [[1,2]]


def test_projection_preserves_list_fields_without_full_forms(isolated_app):
    with isolated_app.app_context():
        payload = 'DOCUMENT-BODY-' * 100000
        report = Report(report_no='LIST-1', project='温度', status='检测录入中', detail={
            'rawSample': {'sampleName': '样品', 'testDept': '检测部', 'sendDate': '2026-10-20',
                          'trademarkImage': payload},
            'summary': [{'title':'样品信息','fields':[['检测结果','合格']]}],
            'attachments': [{'content':payload}], 'rawRecord': payload,
            'checkInput': {}, 'dataEntryStarted': False})
        db.session.add(report); db.session.commit()
        expected = report_business_row(report)
        projected = list_reports(Report.query)[0]
        assert inspect(projected).transient
        assert report_business_row(projected) == expected
        assert payload not in json.dumps(projected.detail)
        assert 'trademarkImage' not in projected.detail['rawSample']
        assert 'attachments' not in projected.detail
        # It must not replace/truncate the identity-map instance used by writes.
        assert db.session.get(Report, report.id) is report
        assert report.detail['rawSample']['trademarkImage'] == payload
        assert not db.session.dirty


@pytest.mark.parametrize('check,started', [({}, False), ({'privateField':'saved'}, True), (None, False)])
def test_legacy_input_state_survives_projection(isolated_app, check, started):
    with isolated_app.app_context():
        db.session.add(Report(report_no='LEGACY', detail={'checkInput':check}))
        db.session.commit()
        from app.status_machine import detection_data_started
        assert detection_data_started(list_reports(Report.query)[0].detail) is started


def test_entrust_and_contract_list_exclude_unrelated_form_fields(isolated_app):
    with isolated_app.app_context():
        for model, key in [(Entrust, 'entrust_no'), (Agreement, 'agreement_no')]:
            db.session.add(model(**{key:'LIST'}, info={'handler':'经办人','registrar':'登记人',
                 'testDept':'检测部','contractPartyA':'甲方','attachmentBody':'secret document'}))
        db.session.commit()
        assert list_entrusts(Entrust.query)[0].info['handler'] == '经办人'
        assert list_agreements(Agreement.query)[0].info['testDept'] == '检测部'
        assert 'attachmentBody' not in list_entrusts(Entrust.query)[0].info
        assert 'attachmentBody' not in list_agreements(Agreement.query)[0].info


def test_completion_audit_reads_exclude_snapshots(isolated_app):
    with isolated_app.app_context():
        db.session.add(Report(report_no='AUDIT', detail={}))
        db.session.add(OperationAudit(object_type='report', object_id='AUDIT',
            action='sample.register.complete', success=True, account='actor',
            before_data={'large':'before'}, after_data={'large':'after'}))
        db.session.commit(); db.session.remove()
        statements = []
        def capture(_c, _cursor, sql, *_args): statements.append(sql)
        @reuse_list_reads
        def read():
            records_by_edit_time(list_reports(Report.query), 'report', lambda r:r.report_no)
            audit = latest_operation_audit('report', 'AUDIT', 'sample.register.complete')
            assert audit.account == 'actor'
            assert 'before_data' in inspect(audit).unloaded
            assert 'after_data' in inspect(audit).unloaded
        event.listen(db.engine, 'before_cursor_execute', capture)
        try: read()
        finally: event.remove(db.engine, 'before_cursor_execute', capture)
        assert not any('operation_audits.before_data' in s or 'operation_audits.after_data' in s for s in statements)


@pytest.mark.parametrize('model,route,number', [
    (Entrust, 'entrust', 'entrust_no')])
def test_summary_and_explicit_detail_preserve_data_and_authorization(workspace, model, route, number):
    client, (user, _, other), factory = workspace
    outsider = factory.user(user.department, permissions=[])
    body = 'FULL-FORM-ONLY' * 10000
    record = model(**{number: 'LOCAL-DETAIL'}, department=user.department.name,
                   owner=user.name, info={'handler':user.name, 'hiddenExtra':body})
    db.session.add(record); db.session.commit()
    auth = headers(user)
    full = client.post(f'/api/{route}/query', headers=auth, json={}).json
    summary = client.post(f'/api/{route}/query', headers=auth, json={'projection':'list'}).json
    assert summary['code'] == full['code'] == 0, summary
    full_row, list_row = full['data']['rows'][0], summary['data']['rows'][0]
    assert {k:v for k,v in full_row.items() if k != 'info'} == {k:v for k,v in list_row.items() if k != 'info'}
    assert body not in json.dumps(list_row)
    detail = client.get(f'/api/{route}/{record.id}', headers=auth).json
    assert detail['code'] == 0, detail
    assert detail['data']['info']['hiddenExtra'] == body
    assert client.get(f'/api/{route}/{record.id}', headers=headers(outsider)).json['code'] == 403
    if model is Entrust:
        assert client.get(f'/api/{route}/{record.id}', headers=headers(other)).json['code'] == 403
    db.session.expire_all()
    assert db.session.get(model, record.id).info['hiddenExtra'] == body


def test_report_list_queries_are_bounded_and_exclude_full_json(isolated_app, scenario_factory):
    from app.security import issue_token
    f = scenario_factory
    dept = f.department(); project, steps = f.project(dept)
    user = f.user(dept, role_key='admin', permissions=['report.query.view'], project_steps=steps)
    client = isolated_app.test_client()
    auth = {'Authorization':'Bearer ' + issue_token(user)}
    department, owner, project_name, project_code = dept.name, user.name, project.name, project.code
    def add_reports(start, stop):
        for i in range(start, stop):
            db.session.add(Report(report_no=f'PERF-{i}', department=department, owner=owner,
                project=project_name, status='检测录入中', sample_status='已领取', detail={
                    'rawSample':{'schemeCode':project_code, 'sampleName':'测试样品', 'trademarkImage':'IMAGE-BODY-'*10000},
                    'attachments':[{'content':'ATTACHMENT-BODY-'*10000}], 'checkInput':{}}))
        db.session.commit()
    def read():
        statements = []
        def observe(_c,_cursor,sql,*args): statements.append(sql)
        db.session.remove()
        event.listen(db.engine,'before_cursor_execute',observe)
        try: response = client.post('/api/reports/query',headers=auth,json={'view':'query'})
        finally: event.remove(db.engine,'before_cursor_execute',observe)
        assert response.json['code'] == 0, response.json
        assert b'IMAGE-BODY' not in response.data and b'ATTACHMENT-BODY' not in response.data
        assert not any('reports.detail AS reports_detail' in s for s in statements)
        return len(response.json['data']['rows']),len(statements)
    add_reports(0,10)
    small, queries_small = read()
    add_reports(10,60)
    large, queries_large = read()
    assert (small,large) == (10,60)
    assert queries_large <= queries_small + 2, (queries_small,queries_large)
