"""CMA single-list policy must not remove an independently authorized CNAS mark."""
from types import SimpleNamespace
import pytest
from app.extensions import db
from app.models import StdLibraryItem
from app.standard_control import standard_scope_failures, validate_stamp_standards
from app.compliance import build_compliance_preflight
from app.report_scope import assess_scope

pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('marks,single,cnas,cma,blocked', [
    (['CNAS'], False, True, False, []),
    (['CNAS'], False, False, True, ['CNAS']),
    (['CMA'], False, True, True, ['CMA']),
    (['CMA','CNAS'], False, True, True, ['CMA']),
    (['CMA','CNAS'], True, True, True, []),
    (['CMA','CNAS'], True, False, True, ['CNAS']),
    (['CMA','CNAS'], True, True, False, ['CMA']),
    ([], False, True, True, []),
])
def test_marks_are_validated_independently(marks, single, cnas, cma, blocked):
    result = dict(valid=True, singleList=single, cnas=cnas, cma=cma)
    failures = standard_scope_failures(result, marks)
    assert sorted({mark for failure in failures for mark in failure['marks']}) == blocked

@pytest.fixture()
def standard(isolated_app):
    with isolated_app.app_context():
        row = StdLibraryItem(code='GB50333-2013', name='虚拟授权标准',
                             auth_kind='非一单一库+CNAS+CMA', use_depts='虚拟部门', impl_date='2014-01-01')
        db.session.add(row); db.session.commit()
        yield row

@pytest.mark.parametrize('stage', ['contract_review','report_review','report_approval'])
@pytest.mark.parametrize('seal,final', [('CNAS','CNAS'), ('CMA',''), ('CMA + CNAS','CNAS')])
def test_preflight_and_scope_preserve_cnas(standard, monkeypatch, stage, seal, final):
    from app import compliance
    monkeypatch.setattr(compliance, 'project_for_report', lambda report: object())
    # Equipment validity is an independent gate; isolate it while using real standard lookup.
    monkeypatch.setattr(compliance, 'compute_report_checks', lambda report: ([{'group':'仪器有效性校验','status':'通过'}], False, ''))
    report = SimpleNamespace(report_no='TEST-SCOPE', project='虚拟项目', department='虚拟部门', detail={
        'rawSample':{'seal':seal,'testBases':['GB50333-2013']},
        'checkInput':{'testDate':'2026-10-19','standard':'GB50333-2013'},
    })
    result = build_compliance_preflight(report, stage)
    assert result['finalSeal'] == final
    assert result['hardBlockers'] == []
    assert result['standardCoverage'][0]['marks'] == ['CNAS']
    assert [i['category'] for i in result['issues']] == (['single_list_scope'] if 'CMA' in seal else [])
    if 'CMA' in seal:
        assert result['issues'][0]['effect'] == '移除 CMA 标识'
    scope = assess_scope(report)
    assert scope['standardRows'][0]['marks'] == ['CNAS']
    assert scope['state'] == ('out_of_scope' if 'CMA' in seal else 'in_scope')

@pytest.mark.parametrize('change,reason', [
    ({'use_depts':'其他部门'}, '未授权给部门'),
    ({'void_date':'2025-01-01'}, '作废'),
    ({'impl_date':'2027-01-01'}, '实施日期'),
    ({'auth_kind':'CMA'}, 'CNAS 授权'),
    ({'out_of_scope':True}, '资质范围外'),
])
def test_cnas_still_requires_valid_department_authorization(standard, change, reason):
    from datetime import date
    for key,value in change.items(): setattr(standard,key,value)
    db.session.commit()
    errors=validate_stamp_standards(standard.code, '虚拟部门', require_cnas=True, at=date(2026,10,19))
    assert any(reason in error for error in errors)
