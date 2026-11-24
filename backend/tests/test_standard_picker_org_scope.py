"""A company administrator's browsing scope must not become a lab restriction."""
import pytest
from app.extensions import db
from app.models import StdLibraryItem, CapabilityImportBatch, CapabilityEntry
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('source_prefix', ['', "'"])
def test_org_wide_unset_department_lists_lab_qualifications(isolated_client, scenario_factory, source_prefix):
    f = scenario_factory
    company = f.department(name='示例检测科技有限公司')
    solar = f.department(name='热工设备检测部', parent=company)
    other = f.department(name='其他测试部门', parent=company)
    admin = f.user(company, role_key='admin')
    normal = f.user(other, permissions=['entrust.sample_register.view'])
    standard = StdLibraryItem(code='GB/T 19141-2026', name='测试标准', use_depts=solar.name,
                              auth_kind='CMA+CNAS+一单一库')
    batch = CapabilityImportBatch(source_name='test.xlsx', source_sha256='4'*64, status='active')
    db.session.add_all([standard, batch]); db.session.flush()
    for mark in ['CMA', 'CNAS']:
        entry = CapabilityEntry(batch_id=batch.id, standard_item_id=standard.id,
            standard_code=source_prefix + standard.code, standard_name=standard.name, item_name='测试参数', object_name='测试对象',
            capability_type='检测', site='示例站点B', active=True, mapping_status='confirmed',
            certificate_no='TEST-CERT', source_sha256='5'*64,
            source_file='test.xlsx', source_page=1, source_row=2,
            raw_cells={'standardWorkbook': {'accreditation': mark, 'oneLibraryState':'是', 'address':'测试完整地址'}})
        entry.departments = [solar]; db.session.add(entry)
    # Mirror production controlled-source ownership.
    batch.summary = {'schema':'lims.scope-workbook-import.v2', 'createdItemIds':[standard.id],
                     'standardPolicies':{str(standard.id):{'capabilityOwnerId':standard.id}}}
    db.session.commit()
    h = {'Authorization':'Bearer '+issue_token(admin)}
    def search(headers, **filters):
        return isolated_client.get('/api/quality/std-library/search', headers=headers,
                                   query_string={'keyword':'19141', **filters}).get_json()['data']['rows']
    rows = search(h)
    assert len(rows)==1 and rows[0]['cnas'] and rows[0]['cma'] and rows[0]['singleList']
    assert rows[0]['sites']==['示例站点B']
    assert search(h, dept=other.name)==[]
    assert len(search(h, dept=solar.name))==1
    normal_h={'Authorization':'Bearer '+issue_token(normal)}
    assert search(normal_h, dept=solar.name)==[]
    def pick(headers, **filters):
        return isolated_client.post('/api/reports/lib/capability-items',headers=headers,
            json={'standardItemId':standard.id, 'page':1, **filters}).get_json()['data']['rows']
    assert len(pick(h))==2
    assert len(pick(h, department=solar.name))==2
    assert pick(h, department=other.name)==[]
    assert pick(normal_h, department=solar.name)==[]
    # Authorizing the standard grants all its parameters, without touching their
    # imported department provenance (including an empty legacy association).
    standard.use_depts += ';' + other.name
    entries = CapabilityEntry.query.all()
    entries[0].departments = []
    db.session.commit()
    rows = search(normal_h)
    assert len(rows)==1 and rows[0]['cma'] and rows[0]['cnas'] and rows[0]['singleList']
    assert len(pick(normal_h))==2
    from datetime import date
    from app.applications.quality_resources.testing_locations import resolve_testing_location, workbook_current_variants
    from app.standard_mark_coverage import standard_mark_coverage
    raw = {'isOnsiteTesting':False}
    resolved = resolve_testing_location(raw,entries,other.name,date.today(),'检测',
                                        controlled_groups=workbook_current_variants())
    assert resolved['testLocation']=='测试完整地址'
    coverage = standard_mark_coverage([standard.code],other.name,date.today(),'检测',{**raw,**resolved})
    assert coverage[0]['marks']==['CMA','CNAS']
    # Type/site filters and inactive parameters cannot erase standard badges.
    assert search(normal_h, site='不存在')[0]['cma']
    entries[0].active = False
    db.session.commit()
    assert len(pick(normal_h))==2 and search(normal_h)[0]['cma']
    standard.use_depts = solar.name
    db.session.commit()
    assert pick(normal_h)==[] and search(normal_h)==[]
