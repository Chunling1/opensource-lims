"""Same-code language variants keep the explicitly selected record identity."""
from testkit.forms import loaded_form
from copy import deepcopy
import pytest
from app.extensions import db
from app.models import StdLibraryItem, Standard
from app.functions.report_standard_text import load_report_standard_names
from test_admin_corrections import workspace, headers, url
pytest_plugins = ("testkit.fixtures",)
CODE = 'EN 442-1:2014'

@pytest.fixture()
def variants(workspace):
    client, actors, rows, _ = workspace
    cn = StdLibraryItem(code=CODE, name='散热器和对流器', use_depts=actors[0].department.name)
    en = StdLibraryItem(code=CODE, name='Specification for radiators', use_depts=actors[0].department.name)
    other = StdLibraryItem(code='EN 999-2024', name='Other', use_depts='其他部门')
    db.session.add_all([cn,en,other,Standard(code=CODE,name=cn.name)])
    db.session.commit()
    return cn,en,other

@pytest.mark.parametrize('index',[0,1])
def test_selected_record_name_saved_and_used_in_report(workspace,variants,index):
    client, actors, rows, _ = workspace
    chosen = variants[index]
    report = rows[2]
    detail = deepcopy(report.detail)
    detail['rawSample'].update(testBases=[CODE],standardItemIds=[chosen.id])
    report.detail = detail
    db.session.commit()
    revision=client.get(url('reports',report),headers=headers(actors[1])).get_json()['data']['revision']
    result=client.put(f'/api/reports/{report.report_no}/testinfo',headers=headers(actors[1]),json=loaded_form(client, f'/api/reports/{report.report_no}/testinfo', {
        'standards':[CODE], 'standardShowName':True,
        'adminCorrection':{'revision':revision,'confirmed':True,'reason':'核对标准语言'},
    })).get_json()
    assert result['code']==0,result
    db.session.refresh(report)
    assert report.detail['checkInput']['standardNames'][CODE]==chosen.name
    from app.report_documents import report_values
    assert chosen.name in report_values(report)['testBasis']
    assert report.detail['rawSample']['standardItemIds']==[chosen.id]

def test_record_lookup_does_not_expand_to_same_code_or_other_department(workspace,variants):
    client, actors, _, _ = workspace
    cn,en,other=variants
    data=client.get(f'/api/quality/std-library/search?ids={en.id}',headers=headers(actors[2])).get_json()
    assert data['code']==0,data
    assert [r['id'] for r in data['data']['rows']]==[en.id]
    data=client.get(f'/api/quality/std-library/search?ids={other.id}',headers=headers(actors[2])).get_json()
    assert data['data']['rows']==[]
    for invalid in ['0','bad','1,-2']:
        assert client.get('/api/quality/std-library/search?ids='+invalid,headers=headers(actors[0])).get_json()['code']!=0

def test_name_resolution_never_uses_another_code_or_chooses_between_two_selected_variants(workspace,variants):
    cn,en,other=variants
    assert load_report_standard_names([CODE],[en.id])[CODE]==en.name
    assert load_report_standard_names([CODE],[other.id])[CODE]==''
    assert load_report_standard_names([CODE],[cn.id,en.id])[CODE]==''

def test_both_language_records_render_independently_and_keep_title_styles(workspace, variants):
    from app.functions.report_standard_text import load_report_standard_records, format_report_standards
    from app.standard_control import selected_controlled_standards
    client, actors, rows, _ = workspace
    cn, en, other = variants
    records = load_report_standard_records([CODE], [en.id, cn.id, en.id])
    assert [r['id'] for r in records] == [en.id, cn.id]
    styles = {f'id:{en.id}': 'EN', f'id:{cn.id}': 'CN'}
    expected = f'{CODE} <{en.name}>；{CODE} 《{cn.name}》'
    assert format_report_standards([CODE], {}, True, styles=styles, records=records) == expected
    resolved = selected_controlled_standards([CODE], [en.id, cn.id], cn.use_depts)
    assert [item.id for item, _ in resolved] == [en.id, cn.id]
    assert all(verdict['valid'] for _, verdict in resolved)
    assert selected_controlled_standards([CODE], None, cn.use_depts)[0][0] is None
    assert selected_controlled_standards([CODE], [cn.id, 999999], cn.use_depts)[1][0] is None
    report=rows[2];detail=deepcopy(report.detail)
    detail['rawSample'].update(testBases=[CODE],standardItemIds=[en.id,cn.id])
    report.detail=detail;db.session.commit()
    revision=client.get(url('reports',report),headers=headers(actors[1])).get_json()['data']['revision']
    result=client.put(f'/api/reports/{report.report_no}/testinfo',headers=headers(actors[1]),json=loaded_form(client, f'/api/reports/{report.report_no}/testinfo', {
        'standards':[CODE],'standardShowName':True,'standardTitleStyles':styles,
        'adminCorrection':{'revision':revision,'confirmed':True,'reason':'核对中英文同时选择'},
    })).get_json()
    assert result['code']==0,result
    db.session.refresh(report)
    assert report.detail['rawSample']['standardItemIds']==[en.id,cn.id]
    assert report.detail['checkInput']['standardDisplay']==expected
    from app.report_documents import report_values
    assert report_values(report)['testBasis']==expected
    from app.document_field_projection import judgment_basis
    assert judgment_basis({'rawSample': {'standardJudge': CODE, 'standardItemIds':[en.id,cn.id],
        'judgmentDisplay': {'standardShowName':True, 'standardTitleStyles':styles}}}) == expected
    from app.entrust_render import _standard_display
    assert _standard_display(CODE,cn.use_depts,[en.id,cn.id])==f'{CODE} {en.name}；{CODE} {cn.name}'
