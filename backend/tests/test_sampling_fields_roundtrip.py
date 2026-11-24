"""Sampling form payloads survive real isolated persistence and detail projection."""
from testkit.forms import loaded_form
from datetime import date
import pytest
from app.extensions import db
from app.models import Report
from test_sample_pricing import business, create, detail

pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('source', ['甲方现场委托 / QA-中文', '4445', ''])
def test_sampling_fields_create_edit_and_reload(business, source):
    client, headers, parents = business
    send = date.today().isoformat()
    value = detail()
    value['rawSample'].update(sendDate=send, sampleArrivalDate=send, taskSource=source)
    value['summary'].append({'title': '抽样信息', 'fields': [['任务来源', source], ['样品到达日期', send]]})
    result = create(client, headers, parents[0], 'SAMPLING-QA', value, '登记中')
    assert result['code'] == 0, result
    def reload():
        db.session.expire_all()
        row = Report.query.filter_by(report_no='SAMPLING-QA').one()
        assert row.detail['rawSample']['taskSource'] == source
        response = client.get('/api/reports/SAMPLING-QA?view=sample_register&projection=sample_form_text', headers=headers).get_json()
        assert response['code'] == 0, response
        raw = response['data']['rawSample']
        assert raw['taskSource'] == source
        assert raw['sampleArrivalDate'] == raw['sendDate'] == send
        sections = response['data']['summary']
        sampling = next(s for s in sections if s['title'] == '抽样信息')
        assert ['样品到达日期', send] in sampling['fields']
    reload()
    result = client.put('/api/reports/SAMPLING-QA/edit', headers=headers, json=loaded_form(client, '/api/reports/SAMPLING-QA/edit', {'fullDetail': value})).get_json()
    assert result['code'] == 0, result
    reload()
