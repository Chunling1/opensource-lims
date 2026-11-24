"""EN standard colon editions must retain linked English parameter identity."""
import pytest
from app.extensions import db
from app.models import Report
from test_sample_pricing import business, create
from test_capability_report_type import calibration_record, sample

pytest_plugins = ('testkit.fixtures',)


def english_and_chinese(separator=':'):
    en = calibration_record('检测')
    en.batch.source_sha256 = 'c' * 64
    db.session.commit()
    cn = calibration_record('检测')
    en.standard_item.code = cn.standard_item.code = 'EN 442-2' + separator + '2014'
    en.standard_item.name = 'Radiators and convectors-Part 2:Test methods and rating'
    en.standard_item.is_english = True
    cn.standard_item.name = '散热器和对流器 第二部分：试验方法和评定'
    cn.standard_item.is_english = False
    en.standard_code = 'EN 442-2'
    en.standard_name = en.standard_item.name
    en.item_name = 'Thermal output'
    cn.standard_code = cn.standard_item.code
    cn.item_name = '散热量'
    db.session.commit()
    return en, cn


def query(client, headers, item, mode='id'):
    body = {'page': 1, 'size': 100, 'capabilityType': '检测'}
    if mode == 'id': body['standardItemId'] = item.id
    elif mode == 'code': body['standardCode'] = item.code; body['standardItemIds'] = [item.id]
    else:
        body.update(allStandards=True, standardItemIds=[item.id], standardCodes=[item.code])
    return client.post('/api/reports/lib/capability-items', headers=headers, json=body).get_json()


@pytest.mark.parametrize('separator', [':', '：'])
@pytest.mark.parametrize('mode', ['id', 'code', 'selected'])
def test_colon_edition_returns_only_selected_language_parameters(business, separator, mode):
    client, headers, _ = business
    en, cn = english_and_chinese(separator)
    result = query(client, headers, en.standard_item, mode)
    assert result['code'] == 0 and result['data']['total'] == 1, result
    row = result['data']['rows'][0]
    assert (row['id'], row['itemName'], row['standardCode']) == (en.id, 'Thermal output', en.standard_item.code)
    chinese = query(client, headers, cn.standard_item, mode)
    assert [r['id'] for r in chinese['data']['rows']] == [cn.id]
    search = client.get('/api/quality/std-library/search', headers=headers,
        query_string={'ids': en.standard_item_id, 'capabilityOnly': '1'}).get_json()['data']['rows']
    assert len(search) == 1 and search[0]['capabilityTypes'] == ['检测']
    assert en.standard_code == 'EN 442-2'


@pytest.mark.parametrize('source', ['EN 442-2:2012', 'EN 442-2-2012', 'EN 442', 'EN 442-1', 'EN 442-20'])
def test_source_code_metadata_does_not_override_explicit_standard_id(business, source):
    client, headers, _ = business
    en, _ = english_and_chinese()
    en.standard_code = source
    db.session.commit()
    rows = query(client, headers, en.standard_item)['data']['rows']
    assert [r['id'] for r in rows] == [en.id]
    assert rows[0]['sourceStandardCode'] == source


def test_colon_edition_draft_complete_keeps_one_standard_and_english_name(business):
    client, headers, parents = business
    en, cn = english_and_chinese()
    item = en.standard_item
    value = sample(en, '产品报告', '委托')
    value['rawSample'].update(testBases=[item.code], testBasis=item.code, standardJudge=item.code,
        standardItemIds=[item.id], reportLanguage='en')
    result = create(client, headers, parents[0], 'EN442-PART2-QA', value, '登记中')
    assert result['code'] == 0, result
    reopened = client.get('/api/reports/EN442-PART2-QA?view=sample_register&projection=sample_form_text',
        headers=headers).get_json()['data']['rawSample']
    assert reopened['capabilityEntryIds'] == [en.id] and reopened['standardItemIds'] == [item.id]
    completed = client.post('/api/reports/EN442-PART2-QA/sample-reg', headers=headers,
        json={'action': 'complete'}).get_json()
    assert completed['code'] == 0, completed
    db.session.expire_all()
    raw = Report.query.filter_by(report_no='EN442-PART2-QA').one().detail['rawSample']
    assert raw['testBases'] == [item.code] and raw['standardItemIds'] == [item.id]
    assert raw['capabilityEntryIds'] == [en.id] and en.standard_code == 'EN 442-2'
