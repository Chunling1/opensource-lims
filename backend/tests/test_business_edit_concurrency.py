"""Form preconditions and the database race are separate invariants."""
from copy import deepcopy
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.extensions import db
from app.models import Report, Entrust, Agreement
from test_sample_pricing import business, saved, detail

pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('route', ['edit', 'change-save', 'change-resubmit'])
def test_stale_and_missing_forms_cannot_overwrite(business, route):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-CONCURRENT', '30', status='委托更改中' if route != 'edit' else '待合同评审')
    path = f'/api/reports/{row.report_no}/{route}'
    method = 'PUT' if route == 'edit' else 'POST'
    version = row.edit_version
    newer = deepcopy(row.detail); newer['preservedAuditField'] = 'another writer'; row.detail = newer
    db.session.commit()
    for v in (None, version, str(row.edit_version)):
        body = {'fullDetail': detail('40', ('40',))}
        if v is not None: body['editVersion'] = v
        response = client.open(path, method=method, headers=headers, json=body)
        assert response.status_code == 409, response.get_json()
        db.session.expire_all()
        assert row.detail == newer and row.edit_version == version + 1
    response = client.open(path, method=method, headers=headers,
        json={'editVersion': row.edit_version, 'fullDetail': detail('40', ('40',))})
    assert response.get_json()['code'] == 0, response.get_json()
    assert response.get_json()['data']['editVersion'] > version + 1

@pytest.mark.parametrize('model,values,field', [
    (Report, {'report_no': 'QA-R'}, 'client'),
    (Entrust, {'entrust_no': 'QA-E'}, 'client'),
    (Agreement, {'agreement_no': 'QA-A'}, 'client')])
def test_separate_connections_reject_lost_update(isolated_app, model, values, field):
    with isolated_app.app_context():
        row = model(**values); db.session.add(row); db.session.commit(); key = row.id
        with Session(db.engine) as first, Session(db.engine) as second:
            a = first.get(model, key); b = second.get(model, key)
            setattr(a, field, 'first'); first.commit()
            setattr(b, field, 'second')
            with pytest.raises(StaleDataError): second.commit()
            second.rollback()
        db.session.expire_all()
        assert db.session.get(model, key).client == 'first'


def test_testinfo_form_survives_composition_but_rejects_changed_inputs(isolated_app, scenario_factory, monkeypatch):
    from app.edit_concurrency import test_form_version as token
    from app.security import issue_token
    monkeypatch.setattr('app.preview_cache.schedule_after_save', lambda *a: None)
    identity = scenario_factory.identity_scenario(permission_codes=('testing.data_entry.view',),
                                                 granted_step_codes=('data_entry',))
    row = Report(report_no='QA-INPUT', department=identity.department.name,
                 project=identity.project.name, owner=identity.user.name,
                 status='检测录入中', sample_status='已领取', detail={})
    db.session.add(row); db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(identity.user)}
    client = isolated_app.test_client()
    path = '/api/reports/QA-INPUT/testinfo'
    baseline = token(row)
    row.detail = {'reportComposition': {'noSupplementBody': True}, 'reportPages': []}
    db.session.commit()
    assert token(row) == baseline
    result = client.put(path, headers=headers, json={'testEditVersion': baseline, 'result': 'first'}).get_json()
    assert result['code'] == 0, result
    assert result['data']['testEditVersion'] != baseline
    current = result['data']['testEditVersion']
    for body in ({'result': 'stale'}, {'testEditVersion': baseline, 'result': 'stale'}):
        assert client.put(path, headers=headers, json=body).status_code == 409
        db.session.refresh(row)
        assert row.detail['checkInput']['result'] == 'first'
    assert client.put(path, headers=headers, json={'testEditVersion': current, 'result': 'second'}).get_json()['code'] == 0
    assert row.detail['reportComposition'] == {'noSupplementBody': True}


def test_retired_erp_repush_route_and_action_are_gone(isolated_app, scenario_factory):
    # Batch-3 Q9 (2026-11-07): the entry never reached Erp; it is removed.
    from app.catalog import all_action_codes
    from app.security import issue_token
    user = scenario_factory.user(scenario_factory.department(), role_key='admin', data_scope_type='all')
    row = Entrust(entrust_no='QA-REPUSH', department=user.department.name, info={'keep': 'original'})
    db.session.add(row); db.session.commit()
    assert 'entrust.erp.repush' not in all_action_codes()
    assert not any('repush-erp' in rule.rule for rule in isolated_app.url_map.iter_rules())
    response = isolated_app.test_client().post(f'/api/entrust/{row.id}/repush-erp',
        headers={'Authorization': 'Bearer ' + issue_token(user)})
    assert response.status_code in (404, 405)
    db.session.refresh(row)
    assert row.info == {'keep': 'original'}


def test_additive_migration_preserves_rows_and_defaults(tmp_path):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1]/'migrations/versions/e167c01a2026_business_edit_versions.py'
    spec = importlib.util.spec_from_file_location('revision167', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine(f'sqlite:///{tmp_path / "migration.sqlite"}')
    with engine.begin() as connection:
        for table in ('reports', 'entrusts', 'agreements'):
            connection.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, client TEXT)'))
            connection.execute(text(f"INSERT INTO {table} VALUES (1, 'unchanged')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        for table in ('reports', 'entrusts', 'agreements'):
            assert connection.execute(text(f'SELECT client, edit_version FROM {table}')).one() == ('unchanged', 1)


def test_save_response_does_not_adopt_a_later_writers_version(business, monkeypatch):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-RESPONSE-RACE', '30', status='委托更改中')
    baseline = row.edit_version
    commit = db.session.commit
    def commit_then_other_writer():
        commit()
        with Session(db.engine) as other:
            current = other.get(Report, row.id)
            current.client = 'another edit after commit'
            other.commit()
    monkeypatch.setattr(db.session, 'commit', commit_then_other_writer)
    response = client.post(f'/api/reports/{row.report_no}/change-save', headers=headers,
        json={'editVersion': baseline, 'fullDetail': detail('40', ('40',))})
    body = response.get_json()
    assert body['code'] == 0, body
    db.session.expire_all()
    assert body['data']['editVersion'] < row.edit_version
    assert client.post(f'/api/reports/{row.report_no}/change-save', headers=headers,
        json={'editVersion': body['data']['editVersion'], 'fullDetail': detail('50', ('50',))}).status_code == 409
