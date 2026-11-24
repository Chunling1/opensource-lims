from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile
from lxml import etree
import pytest
from flask import g
from app.extensions import db
from app.models import Report, OperationAudit
from app.document_module import render_issuance_record
from app.report_issuance_records import issuance_row
from app.blueprints import reports
pytest_plugins = ('testkit.fixtures',)
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def test_mapping_uses_cover_and_copy_count_not_test_items(monkeypatch):
    from app import report_issuance_records as module
    monkeypatch.setattr(module,'report_cover_names',lambda r:dict(SampleName='封面名称',Client='委托单位'))
    r=SimpleNamespace(report_no='QA-1',project='检测项目不可用',owner='负责人',detail={
        'rawSample':{'deliverStd':'3份','sampleAmount':'99'},'checkInput':{'people':{
            'primaryTester1':{'name':'主检甲'},'primaryTester2':{'name':'主检乙'}}}})
    assert issuance_row(r)==dict(no='QA-1',nam='封面名称',cli='委托单位',au='主检甲、主检乙',qty='3')
    r.detail['checkInput']['people']['primaryTester2']={}
    r.detail['assignedPeople']={'primaryTester2':{'name':'旧人员'}}
    assert issuance_row(r)['au']=='主检甲'

@pytest.mark.parametrize('kind',['product','engineering'])
@pytest.mark.parametrize('count',[1,3,15])
def test_real_template_rows_and_blank_manual_columns(kind,count):
    rows=[dict(no=f'QA-{i:03}',au='主检甲、主检乙',nam='名称<&>\t换行\n文字',cli='单位<&>',qty='3') for i in range(count)]
    blob,_=render_issuance_record(kind,rows)
    with ZipFile(BytesIO(blob)) as z:root=etree.fromstring(z.read('word/document.xml'))
    text=''.join(root.xpath('//w:t/text()',namespaces=NS));assert '{{' not in text and '{%' not in text
    data=[]
    for tr in root.xpath('//w:tr',namespaces=NS):
        cells=[''.join(c.xpath('.//w:t/text()',namespaces=NS)) for c in tr.xpath('./w:tc',namespaces=NS)]
        if any(x.startswith('QA-') for x in cells):data.append(cells)
    assert len(data)==count
    for i,cells in enumerate(data):
        assert cells[0]=='' and cells[1]==f'QA-{i:03}' and cells[-3:]==['','','']
        assert '名称<&> 换行 文字' in cells and '单位<&>' in cells and '3' in cells
        assert ('主检甲、主检乙' in cells)==(kind=='engineering')

@pytest.fixture
def identity(scenario_factory):
    return scenario_factory.identity_scenario(permission_codes=('report.release.view',),granted_step_codes=('report_release',))

def call(app,user,body):
    with app.test_request_context('/api/reports/issuance-record/export',method='POST',json=body):
        g.current_user=user
        return app.make_response(reports.export_issuance_record.__wrapped__())

def test_endpoint_checks_all_rows_before_render(isolated_app,identity,monkeypatch):
    rendered=[];visited=[]
    from app import document_module,report_issuance_records
    monkeypatch.setattr(document_module,'render_issuance_record',lambda *a:rendered.append(a))
    def authorize(user,no,view):
        visited.append((no,view));return (None,None,'outside scope') if no=='OTHER' else (SimpleNamespace(report_no=no),None,None)
    monkeypatch.setattr(reports,'get_authorized_report_for_view',authorize)
    monkeypatch.setattr(report_issuance_records,'issuance_row',lambda r:dict(no=r.report_no))
    response=call(isolated_app,identity.user,dict(kind='product',reportNos=['QA','OTHER']))
    assert response.status_code==403 and not rendered and visited==[('QA','release'),('OTHER','release')]

def test_endpoint_preserves_selection_order_deduplicates_and_no_workflow_write(isolated_app,identity,monkeypatch):
    from app import document_module,report_issuance_records
    received=[]
    monkeypatch.setattr(reports,'get_authorized_report_for_view',lambda user,no,view:(SimpleNamespace(report_no=no),None,None))
    monkeypatch.setattr(report_issuance_records,'issuance_row',lambda r:dict(no=r.report_no))
    monkeypatch.setattr(document_module,'render_issuance_record',lambda kind,rows:(received.append((kind,rows)) or b'PK-test',{}))
    before=OperationAudit.query.count()
    response=call(isolated_app,identity.user,dict(kind='engineering',reportNos=['B','A','B']))
    assert response.status_code==200 and response.headers['Cache-Control']=='private, no-store'
    assert received==[('engineering',[{'no':'B'},{'no':'A'}])] and OperationAudit.query.count()==before

@pytest.mark.parametrize('body',[{}, ['invalid'], {'kind':'other','reportNos':['A']},{'kind':'product','reportNos':[]},{'kind':'product','reportNos':['A']*201},{'kind':'product','reportNos':[{}]}])
def test_bad_selection(isolated_app,identity,body):
    assert call(isolated_app,identity.user,body).status_code==400

def test_feature_denied(isolated_app,scenario_factory):
    identity=scenario_factory.identity_scenario(permission_codes=('report.query.view',))
    assert call(isolated_app,identity.user,dict(kind='product',reportNos=['A'])).status_code==403

def test_real_endpoint_exports_scoped_report_and_rejects_other_department(isolated_app,identity,scenario_factory):
    from copy import deepcopy
    inside=Report(report_no='QA-2026-0001',sample_no='QA-SAMPLE-0001',entrust_no='QA-WT-0001',
        status='待发放',archive_state='归档完成',department=identity.department.name,project=identity.project.name,
        owner=identity.user.name,project_name='封面产品',client='合成委托单位',
        detail={'rawSample':{'deliverStd':'2份','sampleName':'封面产品'},
                'checkInput':{'people':{'primaryTester1':{'name':'测试主检'}}}})
    outside=Report(report_no='QA-OUTSIDE',status='待发放',department='另一测试部门',detail={})
    scenario_factory.grant_data_department(identity.user,identity.department)
    db.session.add_all([inside,outside]);db.session.commit()
    before=(inside.status,deepcopy(inside.detail),OperationAudit.query.count())
    response=call(isolated_app,identity.user,dict(kind='engineering',reportNos=[inside.report_no]))
    assert response.status_code==200,response.get_data(as_text=True) if response.status_code!=200 else ''
    response.direct_passthrough=False
    with ZipFile(BytesIO(response.get_data())) as z:
        content=''.join(etree.fromstring(z.read('word/document.xml')).xpath('//w:t/text()',namespaces=NS))
    assert all(s in content for s in ('QA-2026-0001','封面产品','合成委托单位','测试主检'))
    assert (inside.status,inside.detail,OperationAudit.query.count())==before
    assert call(isolated_app,identity.user,dict(kind='product',reportNos=[inside.report_no,outside.report_no])).status_code==403

def test_cover_name_precedence_is_shared_without_publication_or_render():
    from app.docparser_field_only import report_cover_names
    r=SimpleNamespace(project_name='列表项目名称',client='报告委托单位',detail={
        'rawSample':{'sampleName':'样品名称'},'entrustSnapshot':{'client':'快照单位','info':{'projectName':'快照工程'}},
        'summary':[{'title':'送样信息','fields':[['样品名称','封面名称']]}]})
    assert report_cover_names(r)=={'SampleName':'封面名称','Client':'快照单位'}
    r.detail['summary']=[];assert report_cover_names(r)['SampleName']=='样品名称'
    r.detail['rawSample']={};assert report_cover_names(r)['SampleName']=='快照工程'
    r.detail={};assert report_cover_names(r)=={'SampleName':'列表项目名称','Client':'报告委托单位'}
