"""Registration money gates against an isolated database; no business writes."""
from testkit.forms import loaded_form
from datetime import date

import pytest

from app.extensions import db
from app.models import Agreement, Entrust, Report, StdLibraryItem
from app.sample_pricing import completion_error, price_error
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


def detail(price='100.00', amounts=('40', '60')):
    return {'summary': [{'title': '结算信息', 'fields': [['标准价格', price]]}],
            'rawSample': {'stdPrice': price, 'subItems': [
                {'projectName': f'虚拟子项{i}', 'dept': '虚拟部门', 'businessCategory': '虚拟分类',
                 'amount': amount, 'receivedAmount': amount, 'paymentDescription': '按约定支付'} for i, amount in enumerate(amounts)],
                'sendDate': date.today().isoformat(), 'schemeCode': 'TEST', 'project': '虚拟检测',
                'testDept': '虚拟部门', 'testLocation': '虚拟完整地址', 'testBasis': 'TEST-STD',
                'standardJudge': 'TEST-STD', 'centerPrefix': 'LAB', 'reportCategory': '普通'}}


@pytest.mark.parametrize('price,amounts,error', [
    ('100', (), '至少一个子项目'), ('100', ('100', ''), '第2行子项金额'),
    ('100', ('40', '59.99'), '差额 0.01'), ('100', ('100.01',), '差额 -0.01'),
    ('0.30', ('0.1', '0.2'), None), ('0', ('0',), None),
    ('90', ('100', '-10'), None), ('100', ('1e2',), '有效金额'),
    ('100', ('100.001',), '有效金额'), ('-1', ('-1',), '不能为负数'),
    ('', ('100',), '标准价格'), ('NaN', ('100',), '标准价格'),
    ('1000000000000', ('1000000000000',), '有效金额'),
    ('999999999999.99', ('999999999999.98', '0.01'), None),
])
def test_exact_required_amounts(price, amounts, error):
    result = completion_error(detail(price, amounts))
    assert (error in result) if error else result is None


@pytest.mark.parametrize('field', ['projectName', 'dept', 'businessCategory'])
def test_each_subproject_must_be_identified(field):
    value = detail()
    value['rawSample']['subItems'][1][field] = ' '
    assert '第2行' in completion_error(value)


def test_receipts_do_not_replace_allocation_amounts():
    value = detail('100', ('40', '50'))
    value['rawSample']['subItems'][0]['receivedAmount'] = '100'
    assert '合计 90.00' in completion_error(value)
    assert completion_error({}) == '完成登记前请填写至少一个子项目'


@pytest.fixture()
def business(isolated_app, scenario_factory, monkeypatch):
    from app.blueprints import reports
    from app import sample_preview_warmup
    factory = scenario_factory
    department = factory.department(name='虚拟部门')
    user = factory.user(department, role_key='admin', permissions=[
        'entrust.sample_register.view', 'entrust.change.view'])
    agreement = Agreement(agreement_no='TEST-CONTRACT', amount='100', status='已登记')
    other_agreement = Agreement(agreement_no='TEST-OTHER', amount='1000', status='已登记')
    parents = [Entrust(entrust_no=f'TEST-WT-{i}', contract_no='TEST-CONTRACT' if i < 2 else 'TEST-OTHER',
                       department=department.name, owner=user.name, status='委托完成',
                       info={'entrustDate': date.today().isoformat()}) for i in range(3)]
    # Current registration resolves a controlled standard record, not code alone.
    standard = StdLibraryItem(code='TEST-STD', name='虚拟标准', use_depts=department.name)
    db.session.add_all([agreement, other_agreement, standard, *parents])
    db.session.commit()
    # Keep authentication, date normalization, pricing, persistence and audit real.
    # Unrelated capability catalogs and Word rendering use local stubs.
    monkeypatch.setattr(reports, 'validate_project_department', lambda *a, **k: None)
    monkeypatch.setattr(reports, 'standard_is_authorized', lambda *a, **k: True)
    monkeypatch.setattr(reports, '_capability_site_for_full_address', lambda *a: '虚拟场所')
    monkeypatch.setattr(reports, '_sample_configuration', lambda *a, **k: {'ready': True, 'errors': []})
    monkeypatch.setattr(reports, 'advance_skipped_project_steps', lambda *a: [])
    monkeypatch.setattr(sample_preview_warmup, 'schedule_after_save', lambda *a: None)
    return isolated_app.test_client(), {'Authorization': 'Bearer ' + issue_token(user)}, parents


def saved(parent, number, price, **values):
    row = Report(report_no=number, sample_no=number, entrust_no=parent.entrust_no,
                 department='虚拟部门', detail=detail(price, (price,)),
                 status=values.pop('status', '待合同评审'), sample_reg_state=values.pop('sample_reg_state', '登记中'),
                 **values)
    db.session.add(row)
    db.session.commit()
    return row


def create(client, headers, parent, number, value, state='登记完成'):
    return client.post('/api/reports/create', headers=headers, json={
        'reportNo': number, 'entrustNo': parent.entrust_no, 'regState': state,
        'project': '虚拟检测', 'department': '虚拟部门', 'detail': value}).get_json()


def test_create_requires_rows_but_draft_can_be_incomplete(business):
    client, headers, parents = business
    value = detail('100', ())
    rejected = create(client, headers, parents[0], 'TEST-NEW', value)
    assert rejected['code'] != 0 and '至少一个子项目' in rejected['message']
    assert Report.query.filter_by(report_no='TEST-NEW').first() is None
    draft = create(client, headers, parents[0], 'TEST-NEW', value, '登记中')
    assert draft['code'] == 0, draft
    from app.models import ReportAttachment
    assert ReportAttachment.query.filter_by(report_no='TEST-NEW', source='模板生成').count() == 0
    assert Report.query.filter_by(report_no='TEST-NEW').one().sample_reg_state == '登记中'
    rejected = client.post('/api/reports/TEST-NEW/sample-reg', headers=headers,
                           json={'action': 'complete'}).get_json()
    assert rejected['code'] != 0 and '至少一个子项目' in rejected['message']



@pytest.mark.parametrize('kind', ['标准合同', '框架', '虚拟框架', '不回传外部ERP合同'])
@pytest.mark.parametrize('contract_amount', ['', '0', '100', 'NaN', '10,00'])
def test_create_ignores_contract_total_and_other_samples(business, kind, contract_amount):
    client, headers, parents = business
    agreement = Agreement.query.filter_by(agreement_no='TEST-CONTRACT').one()
    agreement.erp_type = agreement.contract_type = kind
    agreement.amount = contract_amount
    db.session.commit()
    saved(parents[0], 'TEST-FIRST', '900000')
    result = create(client, headers, parents[1], 'TEST-SECOND', detail('10000', ('4000', '6000')))
    assert result['code'] == 0, result
    db.session.expire_all()
    row = Report.query.filter_by(report_no='TEST-SECOND').one()
    assert row.sample_reg_state == '登记完成'
    assert row.detail['rawSample']['stdPrice'] == '10000'
    assert agreement.amount == contract_amount


def test_edit_draft_preserves_sample_price_validation_without_contract_cap(business):
    client, headers, parents = business
    saved(parents[0], 'TEST-A', '900000')
    row = saved(parents[1], 'TEST-B', '30')
    result = client.put('/api/reports/TEST-B/edit', headers=headers,
                        json=loaded_form(client, '/api/reports/TEST-B/edit', {'fullDetail': detail('10000', ())})).get_json()
    assert result['code'] == 0, result
    result = client.put('/api/reports/TEST-B/edit', headers=headers,
                        json=loaded_form(client, '/api/reports/TEST-B/edit', {'fullDetail': detail('-1', ())})).get_json()
    assert result['code'] != 0 and '标准价格' in result['message'], result
    db.session.expire_all()
    assert db.session.get(Report, row.id).detail['rawSample']['stdPrice'] == '10000'


def test_judgment_entries_save_reopen_and_validate_at_sample_boundary(business):
    from app.document_field_projection import judgment_basis

    client, headers, parents = business
    value = detail()
    number = 'TEST-JUDGMENT'
    entry = 'GB/T 31433-2015 建筑幕墙、门窗通用技术条件'
    value['rawSample']['judgmentEntries'] = [entry, '按约定；附录 A']
    assert create(client, headers, parents[0], number, value, '登记中')['code'] == 0
    db.session.expire_all()
    row = Report.query.filter_by(report_no=number).one()
    assert row.detail['rawSample']['standardJudge'] == entry + '；按约定；附录 A'
    assert judgment_basis(row.detail, report=True) == 'GB/T 31433-2015 《建筑幕墙、门窗通用技术条件》；按约定；附录 A'

    endpoint = f'/api/reports/{number}/edit'
    value['rawSample']['judgmentEntries'] = [42]
    result = client.put(endpoint, headers=headers,
                        json=loaded_form(client, endpoint, {'fullDetail': value})).get_json()
    assert result['code'] != 0 and '判定标准条目格式无效' in result['message']
    db.session.refresh(row)
    assert row.detail['rawSample']['judgmentEntries'] == [entry, '按约定；附录 A']

    value['rawSample']['judgmentEntries'] = ['JJF 1001 《通用计量术语、定义》', entry]
    result = client.put(endpoint, headers=headers,
                        json=loaded_form(client, endpoint, {'fullDetail': value})).get_json()
    assert result['code'] == 0, result
    db.session.refresh(row)
    assert row.detail['rawSample']['judgmentEntries'] == value['rawSample']['judgmentEntries']
    assert judgment_basis(row.detail) == 'JJF 1001 《通用计量术语、定义》；GB/T 31433-2015 《建筑幕墙、门窗通用技术条件》'


def test_pre_release_sample_form_saves_legacy_judgment_without_reinterpreting_it(business):
    from app.document_field_projection import judgment_basis

    client, headers, parents = business
    number = 'TEST-LEGACY-JUDGMENT'
    value = detail()
    value['rawSample'].update(standardJudge='GB/T 31433-2015 建筑幕墙、门窗通用技术条件', judgeBases={'legacy': True})
    assert create(client, headers, parents[0], number, value, '登记中')['code'] == 0
    row = Report.query.filter_by(report_no=number).one()
    previous = judgment_basis(row.detail)
    endpoint = f'/api/reports/{number}/edit'
    already_open = loaded_form(client, endpoint, {'fullDetail': value})
    value['rawSample']['remark'] = '发布前已打开，继续保存'
    result = client.put(endpoint, headers=headers, json=already_open).get_json()
    assert result['code'] == 0, result
    db.session.refresh(row)
    raw = row.detail['rawSample']
    assert raw['judgeBases'] == {'legacy': True}
    assert 'judgmentEntries' not in raw
    assert raw['standardJudge'] == value['rawSample']['standardJudge']
    assert judgment_basis(row.detail) == previous


def test_complete_requires_local_balance_even_when_contract_amount_missing(business):
    client, headers, parents = business
    Agreement.query.filter_by(agreement_no='TEST-CONTRACT').one().amount = ''
    saved(parents[0], 'TEST-A', '900000')
    row = saved(parents[1], 'TEST-B', '10000')
    row.detail = detail('10000', ('9999',))
    db.session.commit()
    result = client.post('/api/reports/TEST-B/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert result['code'] != 0 and '合计 9999.00' in result['message'], result
    row.detail = detail('10000', ('4000', '6000'))
    db.session.commit()
    result = client.post('/api/reports/TEST-B/sample-reg', headers=headers, json={'action': 'complete'}).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    assert row.sample_reg_state == '登记完成'


@pytest.mark.parametrize('amounts', [('9999',), ('4000', '6000')])
def test_completed_sample_still_requires_change_or_admin_edit(business, amounts):
    client, headers, parents = business
    saved(parents[0], 'TEST-A', '900000')
    row = saved(parents[1], 'TEST-B', '30', sample_reg_state='登记完成')
    rejected = client.put('/api/reports/TEST-B/edit', headers=headers,
                          json=loaded_form(client, '/api/reports/TEST-B/edit', {'fullDetail': detail('10000', amounts)})).get_json()
    assert rejected['code'] != 0 and '样品单已锁定' in rejected['message'], rejected
    db.session.expire_all()
    assert row.detail['rawSample']['stdPrice'] == '30'
    assert row.sample_reg_state == '登记完成'


@pytest.mark.parametrize('full', [True, False])
def test_change_completion_cannot_bypass_subproject_gate(business, full):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-CHANGE', '10000', status='委托更改中', sample_reg_state='登记完成')
    row.detail = detail('10000', ('9999',))
    db.session.commit()
    body = {'fullDetail': detail('10000', ('9999',))} if full else {'note': '虚拟更改'}
    result = client.post('/api/reports/TEST-CHANGE/change-resubmit', headers=headers, json=loaded_form(client, '/api/reports/TEST-CHANGE/change-resubmit', body)).get_json()
    assert result['code'] != 0 and '差额 1.00' in result['message'], result
    db.session.expire_all()
    assert row.status == '委托更改中'


def test_change_draft_can_save_incomplete_above_contract_amount(business):
    client, headers, parents = business
    saved(parents[0], 'TEST-A', '900000')
    row = saved(parents[1], 'TEST-CHANGE', '30', status='委托更改中', sample_reg_state='登记完成')
    result = client.post('/api/reports/TEST-CHANGE/change-save', headers=headers,
                         json=loaded_form(client, '/api/reports/TEST-CHANGE/change-save', {'fullDetail': detail('10000', ())})).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    assert row.detail['rawSample']['stdPrice'] == '10000'
    assert row.status == '委托更改中'


@pytest.mark.parametrize('full', [True, False])
def test_change_completion_has_no_contract_cap_for_both_payload_shapes(business, full):
    client, headers, parents = business
    saved(parents[0], 'TEST-A', '900000')
    row = saved(parents[1], 'TEST-CHANGE', '10000', status='委托更改中', sample_reg_state='登记完成')
    body = {'fullDetail': detail('10000', ('10000',))} if full else {'note': '虚拟更改'}
    result = client.post('/api/reports/TEST-CHANGE/change-resubmit', headers=headers, json=loaded_form(client, '/api/reports/TEST-CHANGE/change-resubmit', body)).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    assert row.status == '待合同评审'


@pytest.mark.parametrize('price', ['', '10000'])
def test_draft_create_can_save_before_contract_amount_is_ready(business, price):
    client, headers, parents = business
    Agreement.query.filter_by(agreement_no='TEST-CONTRACT').one().amount = ''
    db.session.commit()
    result = create(client, headers, parents[0], 'TEST-DRAFT', detail(price, ()), '登记中')
    assert result['code'] == 0, result



@pytest.mark.parametrize('value,error', [('', None), ('—', None), ('10000', None),
                                       ('-1', '标准价格'), ('NaN', '标准价格'), ('1.001', '标准价格')])
def test_draft_price_validation_is_sample_local(value, error):
    result = price_error(detail(value, ()))
    assert (error in result) if error else result is None


@pytest.mark.parametrize('price,error', [('100', None), ('0', None), ('', '标准价格'), ('-1', '标准价格'), ('1e2', '标准价格')])
def test_internal_empty_subprojects_still_validate_price(price, error):
    result = completion_error(detail(price, ()), allow_empty=True)
    assert (error in result) if error else result is None


def test_internal_populated_rows_still_require_balance_and_identification():
    assert '差额' in completion_error(detail('100', ('99',)), allow_empty=True)
    value = detail('100', ('100',))
    value['rawSample']['subItems'][0]['dept'] = ''
    assert '核算部门' in completion_error(value, allow_empty=True)





@pytest.mark.parametrize('description', [None, '', ' \n\t', '　'])
def test_payment_description_required_even_without_draft_price(description):
    value = detail()
    value['rawSample']['subItems'][1]['paymentDescription'] = description
    assert completion_error(value) == '请填写子项目第2行付款说明'
    value['rawSample']['stdPrice'] = ''
    assert price_error(value) == '请填写子项目第2行付款说明'
    del value['rawSample']['subItems'][1]['paymentDescription']
    assert price_error(value) == '请填写子项目第2行付款说明'


@pytest.mark.parametrize('state', ['登记中', '登记完成'])
def test_create_rejects_blank_payment_description_without_writing(business, state):
    client, headers, parents = business
    value = detail()
    value['rawSample']['subItems'][1]['paymentDescription'] = ' '
    result = create(client, headers, parents[0], 'TEST-PAYMENT', value, state)
    assert result['code'] != 0 and '第2行付款说明' in result['message'], result
    assert Report.query.filter_by(report_no='TEST-PAYMENT').first() is None
    value['rawSample']['subItems'][1]['paymentDescription'] = '验收后支付'
    result = create(client, headers, parents[0], 'TEST-PAYMENT', value, state)
    assert result['code'] == 0, result
    assert Report.query.filter_by(report_no='TEST-PAYMENT').one().detail['rawSample']['subItems'][1]['paymentDescription'] == '验收后支付'


@pytest.mark.parametrize('route', ['edit', 'sample-reg', 'change-save', 'change-resubmit'])
def test_existing_sample_payment_description_gate_and_recovery(business, route):
    client, headers, parents = business
    status = '委托更改中' if route.startswith('change-') else '待合同评审'
    row = saved(parents[0], 'TEST-PAYMENT', '100', status=status)
    value = detail('100', ('100',))
    del value['rawSample']['subItems'][0]['paymentDescription']
    # Simulate a legacy record; a basic-body submission cannot evade validation.
    row.detail = value
    db.session.commit()
    body = {'action': 'complete'} if route == 'sample-reg' else {'fullDetail': value}
    call = client.put if route == 'edit' else client.post
    result = call('/api/reports/TEST-PAYMENT/' + route, headers=headers, json=loaded_form(client, '/api/reports/TEST-PAYMENT/' + route, body)).get_json()
    assert result['code'] != 0 and '第1行付款说明' in result['message'], result
    db.session.expire_all()
    assert row.status == status and row.sample_reg_state == '登记中'
    assert 'paymentDescription' not in row.detail['rawSample']['subItems'][0]
    repaired = detail('100', ('100',))
    if route == 'sample-reg':
        result = client.put('/api/reports/TEST-PAYMENT/edit', headers=headers, json=loaded_form(client, '/api/reports/TEST-PAYMENT/edit', {'fullDetail': repaired})).get_json()
        assert result['code'] == 0, result
    else:
        body = {'fullDetail': repaired}
    result = call('/api/reports/TEST-PAYMENT/' + route, headers=headers, json=loaded_form(client, '/api/reports/TEST-PAYMENT/' + route, body)).get_json()
    assert result['code'] == 0, result
    db.session.expire_all()
    assert row.detail['rawSample']['subItems'][0]['paymentDescription'] == '按约定支付'


def test_legacy_change_body_does_not_skip_payment_description(business):
    client, headers, parents = business
    row = saved(parents[0], 'TEST-PAYMENT', '100', status='委托更改中')
    value = detail('100', ('100',))
    value['rawSample']['subItems'][0]['paymentDescription'] = ''
    row.detail = value
    db.session.commit()
    result = client.post('/api/reports/TEST-PAYMENT/change-resubmit', headers=headers, json=loaded_form(client, '/api/reports/TEST-PAYMENT/change-resubmit', {'note': '更改备注'})).get_json()
    assert result['code'] != 0 and '第1行付款说明' in result['message'], result
