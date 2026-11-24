from copy import deepcopy
import pytest
from app.models import Report, ReportAttachment
from app.extensions import db
from test_sample_pricing import business, detail
from testkit.forms import loaded_form
pytest_plugins = ('testkit.fixtures',)
ROOT='NCSA-2026YP-0017'

def source(parents):
    value=detail();value['rawSample'].update(schemeCode='YP',schemeName='源方案',testPlan='源方案(YP)',trademarkImage='test-image')
    value['checkInput']={'standard':'TEST-STD','equipmentIds':[42]}
    r=Report(report_no=ROOT,sample_no='2026YP-0017',entrust_no=parents[0].entrust_no,department='虚拟部门',detail=value,status='待校核',sample_reg_state='登记完成')
    db.session.add(r);db.session.commit();return r

def create(client,headers,parents,value,state='登记中',**extra):
    return client.post('/api/reports/create',headers=headers,json={
      'reportCategory':'英文','baseReportNo':ROOT,'reportNo':ROOT+'(E)',
      'entrustNo':parents[0].entrust_no,'regState':state,'detail':value,'project':'虚拟检测',**extra}).get_json()

@pytest.mark.parametrize('state',['登记中','登记完成'])
def test_inherit_save_and_complete(business,state):
    c,h,p=business;r=source(p);before=deepcopy(r.detail)
    db.session.add(ReportAttachment(report_no=ROOT,name='原始.txt',source='原始记录',data=b'qa',content_type='text/plain'));db.session.commit()
    out=create(c,h,p,{'rawSample':{'sampleName':'English sample'},'summary':[{'title':'送样信息','fields':[['样品名称','English sample']]}]},state)
    assert out['code']==0,out
    derived=Report.query.filter_by(report_no=ROOT+'(E)').one()
    assert derived.detail['rawSample']['testDept']=='虚拟部门'
    assert derived.detail['rawSample']['trademarkImage']=='test-image'
    assert derived.detail['rawSample']['reportLanguage']=='EN'
    assert derived.detail['checkInput']==before['checkInput']
    assert derived.sample_no=='2026YP-0017'
    assert ReportAttachment.query.filter_by(report_no=derived.report_no,source='原始记录').count()==1
    assert r.detail==before
    if state=='登记中':
        result=c.post('/api/reports/'+derived.report_no+'/sample-reg',headers=h,json={'action':'complete'}).get_json()
        assert result['code']==0,result

@pytest.mark.parametrize('field,value',[('schemeCode','OTHER'),('schemeName','OTHER'),('testPlan','OTHER'),('testDept','OTHER'),('testRoom','OTHER')])
def test_create_rejects_scheme_department_changes(business,field,value):
    c,h,p=business;source(p)
    out=create(c,h,p,{'rawSample':{field:value}})
    assert out['code']!=0 and '不能更改' in out['message'],out
    assert Report.query.filter_by(report_no=ROOT+'(E)').first() is None

def test_draft_reopen_and_edit_lock(business):
    c,h,p=business;source(p);assert create(c,h,p,{})['code']==0
    no=ROOT+'(E)'
    d=c.get('/api/reports/'+no,headers=h,query_string={'view':'sample_register','projection':'sample_form_text'}).get_json()['data']
    assert d['reportCategory']=='英文' and d['mainReportNo']==ROOT
    for field in ['schemeCode','testDept']:
        full=deepcopy(d);full['summary']=[{'title':'送样信息','fields':[['样品名称','Translated']]}];full['rawSample'][field]='OTHER'
        out=c.put('/api/reports/'+no+'/edit',headers=h,json=loaded_form(c,'/api/reports/'+no+'/edit',{'fullDetail':full})).get_json()
        assert out['code']!=0 and ('不能更改' in out['message'] or '锁定' in out['message']),out

def test_copy_source_contains_snapshot_and_form_without_writes(business):
    c,h,p=business;r=source(p);before=deepcopy(r.detail)
    out=c.get('/api/samples/copy-sources/'+ROOT,headers=h).get_json()
    assert out['code']==0,out
    d=out['data'];assert d['department']=='虚拟部门' and d['entrustSnapshot']['entrustNo']==p[0].entrust_no
    assert d['rawSample']['trademarkImage']=='test-image' and r.detail==before

@pytest.mark.parametrize('patch',[{'department':'OTHER'},{'detail':{'rawSample':{'testDept':'OTHER'}}},{'detail':{'rawSample':{'schemeCode':'OTHER'}}}])
def test_administrative_editor_also_preserves_derived_scheme(business,patch):
    from app.admin_corrections.selection import validate
    c,h,p=business;r=source(p);r.main_report_no='LAB-2026YP-0001'
    with pytest.raises(ValueError,match='不能更改'):
        validate(r,{'detail':deepcopy(r.detail),'department':r.department},patch)

def test_legacy_clone_projection_normalizes_category_and_exposes_department(business):
    c,h,p=business;r=source(p)
    r.report_kind='english';r.main_report_no='LAB-2026YP-0001'
    r.status='待合同评审';r.sample_reg_state='登记中'
    r.detail={**r.detail,'reportCategory':'英文报告','rawSample':{**r.detail['rawSample'],'reportCategory':'普通','testDept':''}}
    db.session.commit()
    result=c.get('/api/reports/'+ROOT,headers=h,query_string={'view':'sample_register','projection':'sample_form_text'}).get_json()
    assert result['code']==0,result
    d=result['data']
    assert d['reportCategory']=='英文' and d['department']=='虚拟部门'


@pytest.mark.parametrize('state', ['登记中', '登记完成'])
def test_new_english_registration_does_not_inherit_review(business, state):
    from app.contract_review_output import review_flags, review_image
    c,h,p=business;r=source(p)
    r.detail={**r.detail,'complianceResolution':{'requestedSealOriginal':'CNAS','finalSeal':'','lastStage':'report_approval'},'contractReview':{'result':'通过','reviewer':'SOURCE',
        'signatureSource':'account-image-v1','signature':'data:image/png;base64,QA',
        'items':{'tech':True},'cma':True,'cnas':True}}
    db.session.commit();before=deepcopy(r.detail)
    out=create(c,h,p,{},state);assert out['code']==0,out
    derived=Report.query.filter_by(report_no=ROOT+'(E)').one()
    assert 'contractReview' not in derived.detail
    assert 'complianceResolution' not in derived.detail
    assert all(v is None for v in review_flags(derived).values())
    assert review_image(derived)==''
    assert derived.detail['rawSample']['testDept']=='虚拟部门'
    assert derived.detail['rawSample']['testRoom']=='虚拟部门'
    assert derived.detail['checkInput']==before['checkInput']
    assert r.detail==before


@pytest.mark.parametrize('kind', ['product', 'product-extended', 'engineering', 'engineering-extended'])
def test_legacy_unreviewed_english_document_omits_copied_review(business, monkeypatch, kind):
    from app import docparser_field_only as fields
    from app.contract_review_output import authoritative_review, review_flags, review_image
    from app.entrust_render import _business_values, _following_cells, _element_text
    from app.models import OperationAudit, User
    from test_entrust_output_release import SIGNATURE
    from zipfile import ZipFile
    from io import BytesIO
    from lxml import etree
    c,h,p=business;r=source(p)
    r.report_kind='english';r.main_report_no='LAB-2026YP-0001'
    r.sample_reg_state='登记中';r.status='待合同评审'
    r.detail['rawSample']['centerPrefix']='NCSA'
    r.detail['rawSample'].pop('trademarkImage',None)
    r.detail={**r.detail,'derivedFrom':r.main_report_no,'reportCategory':'英文',
        'contractReview':{'result':'通过','reviewer':'SOURCE','reviewerAccount':'source',
        'signatureSource':'account-image-v1','signature':SIGNATURE,
        'items':{'tech':True},'cma':True,'cnas':True}}
    db.session.commit();before=deepcopy(r.detail)
    monkeypatch.setattr(fields,'institution_profile_for',lambda _: {'centerName':'虚拟机构'})
    assert all(v is None for v in review_flags(r).values())
    assert review_image(r)==''
    assert _business_values(p[0],r)['reviewer']==''
    actor=User.query.first()
    assert not authoritative_review({'reportNo':ROOT,'detail':before},actor).get('contractReview')
    blob,_=fields.render_entrust(p[0],r,kind)
    with ZipFile(BytesIO(blob)) as package:
        root=etree.fromstring(package.read('word/document.xml'))
        text=''.join(_element_text(cell) for cell in _following_cells(root,'合同评审'))
        assert '☑' not in text and '☒' not in text and '□' in text
        assert 'SOURCE' not in text
        import base64
        assert base64.b64decode(SIGNATURE.split(',')[1]) not in [package.read(n) for n in package.namelist() if n.startswith('word/media/')]
    assert r.detail==before
    # A genuine review of this report is retained, including on later re-review.
    db.session.add(OperationAudit(object_type='report',object_id=ROOT,action='report.contract_review.pass',success=True,account='source',user_name='SOURCE'))
    db.session.commit()
    assert review_flags(r)['CMA'] is True and review_image(r)==SIGNATURE


def test_english_registration_cannot_skip_its_contract_review(business, monkeypatch):
    from types import SimpleNamespace
    from app import project_workflow
    from app.blueprints import reports
    c,h,p=business;source(p)
    monkeypatch.setattr(project_workflow,'project_for_report',lambda _:SimpleNamespace(workflow_config={'skippedSteps':['entrust_review','sample_inbound']}))
    monkeypatch.setattr(reports,'advance_skipped_project_steps',project_workflow.advance_skipped_project_steps)
    out=create(c,h,p,{},'登记完成');assert out['code']==0,out
    derived=Report.query.filter_by(report_no=ROOT+'(E)').one()
    assert derived.status=='待合同评审'
    assert derived.detail['requiresContractReReview'] is True
    assert not derived.detail.get('projectWorkflowSkips')
