"""Optional picker location filtering must not become a workflow restriction."""
import pytest
from app.extensions import db
from app.models import CapabilityEntry, StdLibraryItem
from test_sample_pricing import business
from test_capability_report_type import calibration_record

pytest_plugins = ('testkit.fixtures',)


def catalog():
    first = calibration_record('检测')
    first.site = '示例站点B'
    first.raw_cells = {'standardWorkbook': {'address': '北京市示例站点B区测试路1号'}}
    rows = [first]
    for site, cells in [
        ('示例站点E', {'standardWorkbook': {'address': '示例站点E市测试路2号'}}),
        ('示例站点E', {'standardWorkbook': {'address': '示例站点E市测试路2号'}}),
        ('示例站点B', {'standardWorkbook': {'address': '旧地址'}, 'parameterMaintenance': {'address': '新维护地址'}}),
        ('仅场所', {}), ('', {}),
    ]:
        row = CapabilityEntry(batch_id=first.batch_id, standard_item_id=first.standard_item_id,
            certificate_no='VIRTUAL', source_file='virtual.pdf', source_page=1, source_row=2, source_sha256='c'*64,
            capability_type='校准', site=site, object_name='虚拟对象', item_name='温度', standard_code=first.standard_code,
            raw_cells=cells, active=False, mapping_status='pending')
        db.session.add(row); rows.append(row)
    other = StdLibraryItem(code=first.standard_code, name='同号英文标准', use_depts='其他部门')
    db.session.add(other); db.session.flush()
    db.session.add(CapabilityEntry(batch_id=first.batch_id, standard_item_id=other.id,
        capability_type='检测', certificate_no='VIRTUAL', source_file='virtual.pdf', source_page=1, source_row=3, source_sha256='d'*64,
        site='不应泄露地点', object_name='虚拟对象', standard_code=other.code, item_name='其他标准参数'))
    db.session.commit()
    return rows, other


def query(client, headers, item_id, **extra):
    return client.post('/api/reports/lib/capability-items', headers=headers, json={
        'standardItemIds': [item_id], 'department': '虚拟部门', 'includeLocations': True,
        'page': 1, 'size': 1, **extra})


def test_location_filter_before_pagination_and_options_across_all_pages(business):
    client, headers, _ = business
    rows, _ = catalog(); item = rows[0].standard_item_id
    all_result = query(client, headers, item).get_json()['data']
    assert all_result['total'] == 6
    assert set(all_result['locations']) == {'北京市示例站点B区测试路1号', '示例站点E市测试路2号', '新维护地址', '仅场所', '__unspecified__'}
    result = query(client, headers, item, locationFilter='示例站点E市测试路2号', page=2).get_json()['data']
    assert result['total'] == 2 and len(result['rows']) == 1
    assert result['rows'][0]['id'] == rows[2].id
    assert result['locations'] == all_result['locations']
    no_match = query(client, headers, item, locationFilter='示例站点E市测试路2号', keyword='不存在').get_json()['data']
    assert no_match['total'] == 0 and no_match['locations'] == all_result['locations']
    restored = query(client, headers, item, locationFilter='').get_json()['data']
    assert restored['total'] == 6


@pytest.mark.parametrize('location,index', [('新维护地址', 3), ('仅场所', 4), ('__unspecified__', 5)])
def test_location_sources_and_unmaintained_records(business, location, index):
    client, headers, _ = business
    rows, _ = catalog()
    result = query(client, headers, rows[0].standard_item_id, locationFilter=location).get_json()['data']
    assert result['total'] == 1 and result['rows'][0]['id'] == rows[index].id


def test_unknown_location_and_unauthorized_standard_return_no_records(business):
    client, headers, _ = business
    rows, other = catalog()
    assert query(client, headers, rows[0].standard_item_id, locationFilter='不存在').get_json()['data']['total'] == 0
    denied = query(client, headers, other.id).get_json()['data']
    assert denied['rows'] == [] and denied['locations'] == []


def test_selected_id_hydration_unfiltered_and_legacy_site_hint_ignored(business):
    client, headers, _ = business
    rows, _ = catalog()
    body = {'standardItemIds': [rows[0].standard_item_id], 'ids': [rows[0].id, rows[1].id], 'site': 'legacy-location'}
    result = client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()['data']
    assert {r['id'] for r in result['rows']} == {rows[0].id, rows[1].id}
    assert 'locations' not in result


@pytest.mark.parametrize('invalid', [None, [], 12, 'x'*501])
def test_invalid_location_filter_rejected(business, invalid):
    client, headers, _ = business
    assert query(client, headers, 1, locationFilter=invalid).status_code == 400


def test_accreditation_combines_with_location_before_count_and_pagination(business):
    client, headers, _ = business
    rows, other = catalog()
    for row in rows[1:3]:
        row.raw_cells = {'standardWorkbook': {'address': '示例站点E市测试路2号', 'accreditation': 'CMA'}}
    db.session.commit()
    item = rows[0].standard_item_id
    baseline = query(client, headers, item).get_json()['data']
    cma = query(client, headers, item, accreditationFilter='CMA', page=2).get_json()['data']
    assert cma['total'] == 2 and cma['rows'][0]['id'] == rows[2].id
    assert cma['rows'][0]['accreditation'] == 'CMA'
    assert cma['locations'] == baseline['locations']
    combined = query(client, headers, item, accreditationFilter='CMA', locationFilter='示例站点E市测试路2号', keyword='温度').get_json()['data']
    assert combined['total'] == 2
    empty = query(client, headers, item, accreditationFilter='CNAS', locationFilter='示例站点E市测试路2号').get_json()['data']
    assert empty['total'] == 0 and empty['locations'] == baseline['locations']
    legacy = query(client, headers, item, accreditationFilter='CNAS', size=100).get_json()['data']
    assert legacy['total'] == 4 and all(row['accreditation'] == 'CNAS' for row in legacy['rows'])
    assert query(client, headers, other.id, accreditationFilter='CMA').get_json()['data']['rows'] == []
    assert query(client, headers, item, accreditationFilter='').get_json()['data']['total'] == 6


@pytest.mark.parametrize('invalid', [None, [], 12, 'CMA,CNAS', 'invalid'])
def test_invalid_accreditation_filter_rejected(business, invalid):
    client, headers, _ = business
    assert query(client, headers, 1, accreditationFilter=invalid).status_code == 400
