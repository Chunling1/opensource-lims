"""Saved sample identity is independent of the current editor; isolated HTTP tests."""
from testkit.forms import loaded_form
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.extensions import db
from app.models import OperationAudit
from app.sample_entrust import stamp_sample_registrar, write_sample_registrar
from test_sample_pricing import business, saved
from test_admin_corrections import workspace, save, url
pytest_plugins = ('testkit.fixtures',)


def identity(value):
    assert value['sampleRegistrar'] == value['rawSample']['registrar'] == value['entrustSnapshot']['owner'] == value['entrustSnapshot']['info']['handler']
    assert value['sampleRegistrarDepartment'] == value['rawSample']['registrarDepartment'] == value['entrustSnapshot']['department'] == value['entrustSnapshot']['info']['handleDept']
    return value['sampleRegistrar'], value['sampleRegistrarDepartment']


@pytest.mark.parametrize('route', ['edit', 'change-save'])
@pytest.mark.parametrize('has_entrust', [True, False])
def test_ordinary_save_preserves_registrar_even_when_caller_forges_it(business, route, has_entrust):
    client, headers, parents = business
    row = saved(parents[0], 'REG-TEST', '30', status='委托更改中' if route == 'change-save' else '待合同评审')
    if not has_entrust:
        row.entrust_no = ''
    value = deepcopy(row.detail)
    value['entrustSnapshot'] = {'owner':'原登记人', 'department':'原登记部门', 'info':{}}
    row.detail = write_sample_registrar(value, '原登记人', 'original', '原登记部门')
    db.session.commit()
    forged = write_sample_registrar(row.detail, '当前管理员', 'admin', '公司')
    response = client.open(f'/api/reports/REG-TEST/{route}', method='PUT' if route == 'edit' else 'POST', headers=headers, json=loaded_form(client, f'/api/reports/REG-TEST/{route}', {'fullDetail':forged})).get_json()
    assert response['code'] == 0, response
    db.session.refresh(row)
    assert identity(row.detail) == ('原登记人', '原登记部门')
    assert row.detail['sampleRegistrarAccount'] == 'original'


@pytest.mark.parametrize('actor', [0,1])
def test_explicit_admin_revision_syncs_identity_and_audits_actual_editor(workspace, actor, scenario_factory):
    client, actors, records, _ = workspace
    row = records[2]
    department = scenario_factory.department(name='修订部门')
    person = scenario_factory.user(department, name='修订登记人', account='selected-registrar')
    value = deepcopy(row.detail)
    value['entrustSnapshot'] = {'owner':'原登记人','department':'原登记部门','info':{}}
    value['summary'] = [{'title':'委托信息','fields':[['样品登记人','原登记人'],['样品登记部门','原登记部门']]}]
    row.detail = write_sample_registrar(value, '原登记人', 'original', '原登记部门')
    db.session.commit()
    new = deepcopy(row.detail)
    new['entrustSnapshot'].update(owner='修订登记人', department='修订部门')
    new['entrustSnapshot']['info'].update(handler='修订登记人', handleDept='修订部门')
    new['entrustSnapshot']['info'].update(sampleRegistrarUserId=str(person.id), sampleRegistrarDepartmentId=str(department.id))
    response = save(client, actors[actor], url('reports', row), {'detail':new})
    assert response.status_code == 200, response.get_json()
    db.session.refresh(row)
    assert identity(row.detail) == ('修订登记人','修订部门')
    assert row.detail['sampleRegistrarAccount'] == 'selected-registrar'
    assert row.detail['sampleRegistrarUserId'] == str(person.id)
    assert ['样品登记人','修订登记人'] in row.detail['summary'][0]['fields']
    audit = OperationAudit.query.filter_by(action='admin.business.correct').one()
    assert audit.account == actors[actor].account
    # An unrelated later edit must retain the explicitly corrected identity.
    new = deepcopy(row.detail); new['rawSample']['testLocation'] = '新地址'
    assert save(client, actors[actor], url('reports', row), {'detail':new}).status_code == 200
    db.session.refresh(row)
    assert identity(row.detail) == ('修订登记人','修订部门')


def test_creation_seeds_authenticated_user_but_legacy_edits_do_not():
    user = SimpleNamespace(account='new', name='新登记人', department=SimpleNamespace(name='新部门'))
    value = {'rawSample':{},'entrustSnapshot':{'owner':'来源委托人','department':'来源部门','info':{}}}
    assert identity(stamp_sample_registrar(value,user)) == ('新登记人','新部门')
    assert identity(stamp_sample_registrar(value,user,previous=value)) == ('来源委托人','来源部门')


def test_completion_by_another_user_preserves_original_registration(business, monkeypatch):
    from app.blueprints import reports
    client, headers, parents = business
    row = saved(parents[0], 'REG-COMPLETE', '30')
    value = deepcopy(row.detail); value['entrustSnapshot'] = {'info':{}}
    row.detail = write_sample_registrar(value,'原登记人','original','原登记部门')
    db.session.commit()
    # Completion catalogue checks are unrelated; retain real permission, persistence and audit.
    monkeypatch.setattr(reports, '_validate_sample_registration_completion', lambda user,value,*a,**k:(value,None))
    response = client.post('/api/reports/REG-COMPLETE/sample-reg',headers=headers,json={'action':'complete'}).get_json()
    assert response['code'] == 0, response
    db.session.refresh(row)
    assert row.sample_reg_state == '登记完成'
    assert identity(row.detail) == ('原登记人','原登记部门')


def test_conflicting_admin_identity_cannot_partially_save(workspace):
    client, actors, records, _ = workspace
    row = records[2]; before = deepcopy(row.detail)
    value = deepcopy(before)
    value['sampleRegistrar'] = '登记人甲'
    value['entrustSnapshot'] = {'owner':'登记人乙','info':{}}
    response = save(client, actors[1], url('reports',row), {'detail':value})
    assert response.status_code == 400, response.get_json()
    db.session.refresh(row)
    assert row.detail == before
    assert OperationAudit.query.filter_by(action='admin.business.correct').count() == 0
