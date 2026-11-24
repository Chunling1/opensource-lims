"""Invalid sample forms must not consume durable business numbers."""
import pytest

from app.extensions import db
from app.models import BusinessNumberSequence, Report
from test_sample_pricing import business, detail

pytest_plugins = ('testkit.fixtures',)


def submit(business, value, state='登记完成', prefix='LAB-2026YP'):
    client, headers, parents = business
    return client.post('/api/reports/create', headers=headers, json={
        'reportNoPrefix': prefix, 'reportCategory': '普通',
        'entrustNo': parents[0].entrust_no, 'regState': state,
        'project': '虚拟检测', 'department': '虚拟部门', 'detail': value,
    }).get_json()


@pytest.mark.parametrize('invalid', ['price', 'required', 'date'])
def test_rejected_form_then_valid_save_gets_next_number(business, invalid):
    db.session.add(BusinessNumberSequence(scope='sample-report:2026YP', last_value=20))
    db.session.commit()
    value = detail()
    if invalid == 'price':
        value['rawSample']['stdPrice'] = '-1'
    elif invalid == 'required':
        value['rawSample']['subItems'] = []
    else:
        value['rawSample']['sendDate'] = 'not-a-date'
    rejected = submit(business, value)
    assert rejected['code'] != 0, rejected
    db.session.expire_all()
    assert BusinessNumberSequence.query.filter_by(scope='sample-report:2026YP').one().last_value == 20
    assert Report.query.filter(Report.sample_no.like('2026YP-%')).count() == 0
    saved = submit(business, detail())
    assert saved['code'] == 0, saved
    assert saved['data']['sampleNo'] == '2026YP-0021'
    assert saved['data']['reportNo'] == 'LAB-2026YP-0021'
    again = submit(business, detail(), prefix='LAB-2026YP')
    assert again['code'] == 0, again
    assert again['data']['sampleNo'] == '2026YP-0022'


def test_valid_draft_reserves_and_voided_number_is_not_reused(business):
    first = submit(business, detail('100', ()), '登记中')
    assert first['code'] == 0, first
    row = Report.query.filter_by(report_no=first['data']['reportNo']).one()
    row.voided = True
    db.session.commit()
    second = submit(business, detail(), '登记中')
    assert second['code'] == 0, second
    assert first['data']['sampleNo'] == '2026YP-0001'
    assert second['data']['sampleNo'] == '2026YP-0002'
