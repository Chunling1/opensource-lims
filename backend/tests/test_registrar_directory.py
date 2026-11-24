from testkit.forms import loaded_form
from copy import deepcopy
import pytest
from app.extensions import db
from app.models import User, OperationAudit
from test_admin_corrections import workspace, headers, save, url
pytest_plugins = ('testkit.fixtures',)


def test_all_people_paging_search_and_department_selection(workspace, scenario_factory):
    client, actors, _, _ = workspace
    department = scenario_factory.department(name='跨院测试部门')
    # Total exactly 195 including the three fixture identities; no expensive password work.
    for i in range(192):
        db.session.add(User(account=f'person-{i:03}', name=f'测试人员{i:03}', password_hash='test-only',
                           department_id=department.id, enabled=i != 191, role_key='user', role_name='Test', home_path='/'))
    db.session.commit()
    seen = set()
    for page in range(1, 11):
        response = client.get(f'/api/admin-corrections/registrar-options?page={page}', headers=headers(actors[1]))
        data = response.get_json()['data']
        assert data['total'] == 195
        assert len(data['rows']) <= 20
        seen.update(r['id'] for r in data['rows'])
        assert all('password_hash' not in r and 'permissions' not in r for r in data['rows'])
    assert len(seen) == 195
    result = client.get('/api/admin-corrections/registrar-options?keyword=person-191', headers=headers(actors[0])).get_json()['data']
    assert result['total'] == 1 and result['rows'][0]['enabled'] is False
    assert result['rows'][0]['departmentId'] == department.id
    data = client.get('/api/admin-corrections/registrar-options?kind=departments&keyword=跨院', headers=headers(actors[1])).get_json()['data']
    assert data['rows'][0]['id'] == department.id
    assert client.get('/api/admin-corrections/registrar-options', headers=headers(actors[2])).status_code == 403
    assert client.get('/api/admin-corrections/registrar-options?page=0', headers=headers(actors[0])).status_code == 400
    assert OperationAudit.query.count() == 0


def test_department_only_and_invalid_person_are_atomic(workspace, scenario_factory):
    client, actors, rows, _ = workspace
    from app.sample_entrust import write_sample_registrar
    report = rows[2]
    report.detail = write_sample_registrar({'rawSample':{},'entrustSnapshot':{'info':{}}},'原人','old','原部门')
    dept = scenario_factory.department(name='更正部门'); db.session.commit()
    changed = deepcopy(report.detail)
    changed['entrustSnapshot']['info'].update(handleDept=dept.name, sampleRegistrarDepartmentId=str(dept.id))
    response = save(client, actors[1], url('reports',report), {'detail':changed})
    assert response.status_code == 200, response.get_json()
    assert report.detail['sampleRegistrar'] == '原人' and report.detail['sampleRegistrarAccount'] == 'old'
    assert report.detail['sampleRegistrarDepartment'] == dept.name
    before = deepcopy(report.detail)
    changed = deepcopy(before); changed['entrustSnapshot']['info']['sampleRegistrarUserId'] = '999999'
    assert save(client, actors[1], url('reports',report), {'detail':changed}).status_code == 400
    db.session.refresh(report); assert report.detail == before


def test_explicit_person_and_independent_department_selection(workspace, scenario_factory):
    client, actors, rows, _ = workspace
    from app.sample_entrust import write_sample_registrar
    report = rows[2]
    report.detail = write_sample_registrar({'rawSample': {}, 'entrustSnapshot': {'info': {}}}, '旧人', 'old', '旧部门')
    person = actors[0]
    dept = scenario_factory.department(name='独立登记部门')
    db.session.commit()
    changed = deepcopy(report.detail)
    changed['entrustSnapshot']['info'].update(sampleRegistrarUserId=str(person.id), sampleRegistrarDepartmentId=str(dept.id), handler=person.name, handleDept=dept.name)
    response = save(client, actors[1], url('reports', report), {'detail': changed})
    assert response.status_code == 200, response.get_json()
    assert report.detail['sampleRegistrarAccount'] == person.account
    assert report.detail['sampleRegistrarDepartment'] == dept.name
    assert report.detail['rawSample']['registrarUserId'] == str(person.id)


@pytest.mark.parametrize('kind,index', [('entrusts',1),('reports',2)])
def test_admin_unrelated_correction_keeps_business_owner(workspace,kind,index):
    client, actors, rows, _ = workspace
    row=rows[index]; row.owner='原经手人'
    if kind=='reports':
        row.detail=dict(row.detail, signatures={'主检':'原签名'}, checkInput={'entryStaff':{'id':99,'account':'original','name':'原录入人'}})
    else:
        row.info=dict(row.info, registrar='原登记人',handler='原经手人')
    db.session.commit()
    assert save(client, actors[1], url(kind,row), {'project_name':'更正项目名'}).status_code == 200
    db.session.refresh(row)
    assert row.owner=='原经手人'
    if kind!='reports': assert row.info['registrar']=='原登记人'
    assert OperationAudit.query.filter_by(action='admin.business.correct').one().account==actors[1].account


def test_testing_correction_preserves_entry_staff_people_owner_and_signature(workspace):
    client, actors, rows, _ = workspace
    report=rows[2]; report.owner='原主检'
    people={'primaryTester1':{'id':99,'code':'original','name':'原主检'}}
    staff={'id':99,'account':'original','name':'原录入人'}
    report.detail=dict(report.detail, checkInput={'entryStaff':staff,'people':people}, signatures={'主检':'原签名'}, summary=[{'title':'实验信息','fields':[]}])
    db.session.commit()
    record=client.get(url('reports',report),headers=headers(actors[1])).get_json()['data']
    response=client.put(f'/api/reports/{report.report_no}/testinfo',headers=headers(actors[1]),json=loaded_form(client, f'/api/reports/{report.report_no}/testinfo', {
        'result':'修订结果','adminCorrection':{'revision':record['revision'],'confirmed':True,'reason':'核对结果'}}))
    assert response.get_json()['code']==0, response.get_json()
    db.session.refresh(report)
    assert report.owner=='原主检'
    assert report.detail['checkInput']['entryStaff']==staff
    assert report.detail['checkInput']['people']==people
    assert report.detail['signatures']['主检']=='原签名'
    assert ['数据录入人员','original / 原录入人'] in report.detail['summary'][0]['fields']
