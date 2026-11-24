from io import BytesIO
from pathlib import Path
import hashlib
from datetime import datetime

import fitz
import pytest
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app import document_module
from app.pdf_issue_date import formatted_date

PROFILES=[(kind,lang,ext) for kind in ['Product','Sampling'] for lang in ['CN','EN'] for ext in [False,True]]+[
    (kind,lang,False) for kind in ['Engineering','Inspection'] for lang in ['CN','EN']]+[('Calibration','CN',False)]


def sample_pdf(kind='Engineering',language='CN',extended=False,value='',duplicate=False,missing=False,gap=4):
    from app.vendor_docparser_20260911.pdf_helper import resolve_runtime_font
    pdfmetrics.registerFont(TTFont('DateTestSong',str(resolve_runtime_font('cn')),subfontIndex=0))
    pdfmetrics.registerFont(TTFont('DateTestTimes',str(resolve_runtime_font('en'))))
    out=BytesIO();c=canvas.Canvas(out,pagesize=(595,842))
    page=0 if kind=='Calibration' else (2 if extended else 1)
    label=('签 发 日 期' if kind=='Calibration' else
        'Issue Date:' if language=='EN' else '报告日期Date：' if kind in ['Product','Sampling'] else '签发日期Date：')
    for i in range(4):
        c.setFont('DateTestTimes',11);c.drawString(60,780,'REPORT-TEST-001 '+str(i))
        c.drawString(60,730,'Test Date: 2026-10-01 to 2026-10-02')
        c.drawString(60,690,'Original Issue Date: 20 Sep 2026')
        c.setLineWidth(.8);c.rect(35,40,525,710)
        if i==page and not missing:
            size=12 if kind=='Calibration' else 10.5
            c.setFont('DateTestSong' if language=='CN' else 'DateTestTimes',size)
            x=70;y=150;c.drawString(x,y,label)
            end=x+pdfmetrics.stringWidth(label,'DateTestSong' if language=='CN' else 'DateTestTimes',size)
            if value:c.drawString(end+(140 if kind=='Calibration' else gap),y,value)
            if duplicate:c.drawString(x,100,label)
        c.showPage()
    c.save();return out.getvalue()


@pytest.mark.parametrize('kind,language,extended',PROFILES)
@pytest.mark.parametrize('old',['','2026-10-01'])
def test_fill_replace_and_idempotent(kind,language,extended,old):
    source=sample_pdf(kind,language,extended,old)
    new,audit=document_module.finalize_issue_date(source,'2026-10-24',category=kind,language=language,extended=extended)
    proof=audit['issueDate'];assert proof['changed'] and proof['approvalDate']=='2026-10-24'
    with fitz.open(stream=source,filetype='pdf') as before,fitz.open(stream=new,filetype='pdf') as after:
        assert len(before)==len(after)==4
        index=proof['page']-1
        text=''.join(after[index].get_text().split())
        assert ''.join(formatted_date('2026-10-24',language).split()) in text
        assert 'OriginalIssueDate:20Sep2026' in text and 'TestDate:2026-10-01to2026-10-02' in text
        for i in range(4):
            a=before[i].get_pixmap();b=after[i].get_pixmap()
            if i!=index:assert a.samples==b.samples
            else:
                # Text-only redaction and insertion leave borders and all other rows intact.
                clip=fitz.Rect(0,0,595,650)
                assert before[i].get_pixmap(clip=clip).samples==after[i].get_pixmap(clip=clip).samples
    again,proof2=document_module.finalize_issue_date(new,'2026-10-24',category=kind,language=language,extended=extended)
    assert again==new and not proof2['issueDate']['changed']


@pytest.mark.parametrize('kwargs',[{'duplicate':True},{'missing':True},{'value':'CUSTOM NOTE'}])
def test_ambiguous_missing_or_unknown_refuses(kwargs):
    with pytest.raises(ValueError,match='报告日期核查失败'):
        document_module.finalize_issue_date(sample_pdf(**kwargs),'2026-10-24',category='Engineering',language='CN')


def test_no_implicit_today():
    with pytest.raises(ValueError,match='批准日期缺失'):
        document_module.finalize_issue_date(sample_pdf(),'',category='Engineering',language='CN')


@pytest.mark.parametrize('value', ['/', '2026-10-01'])
@pytest.mark.parametrize('language', ['CN', 'EN'])
def test_value_touching_label_is_removed_before_date_is_written(value, language):
    source = sample_pdf(language=language, value=value, gap=0)
    final, audit = document_module.finalize_issue_date(source, '2026-11-08', category='Engineering', language=language)
    with fitz.open(stream=final, filetype='pdf') as pdf:
        text = ''.join(pdf[1].get_text().split())
    if value == '/':
        assert '/' not in text
    else:
        # The unchanged test interval contains this date once.
        assert text.count(value) == 1
    assert ''.join(formatted_date('2026-11-08', language).split()) in text
    again, _ = document_module.finalize_issue_date(final, '2026-11-08', category='Engineering', language=language)
    assert final == again


pytest_plugins=('testkit.fixtures',)


@pytest.mark.parametrize('duplicate', [False, True])
def test_date_search_keeps_cross_page_uniqueness_and_skips_vector_body(duplicate, monkeypatch):
    from app import pdf_issue_date
    monkeypatch.syspath_prepend(str(document_module.VENDOR))
    from pdf_helper import PdfMaker
    with fitz.open(stream=sample_pdf(), filetype='pdf') as doc:
        doc.delete_page(2)
        if duplicate:
            with fitz.open(stream=sample_pdf(), filetype='pdf') as second:
                doc.insert_pdf(second, from_page=1, to_page=1, start_at=2)
        if not duplicate:
            page = doc.new_page(pno=2, width=595, height=842)
            page.insert_text((70, 100), 'VECTOR BODY')
            for y in range(200, 700):
                page.draw_line((50, y), (500, y))
        raw = doc.tobytes()
    searched = []
    original = pdf_issue_date.pdfplumber.page.Page.search
    def search(page, *args, **kwargs):
        searched.append(page.page_number)
        return original(page, *args, **kwargs)
    monkeypatch.setattr(pdf_issue_date.pdfplumber.page.Page, 'search', search)
    if duplicate:
        with pytest.raises(ValueError, match='找到2处'):
            pdf_issue_date.locate(raw, PdfMaker('Engineering', 'CN', False), 'CN')
        return
    result = pdf_issue_date.locate(raw, PdfMaker('Engineering', 'CN', False), 'CN')
    assert result['page'] == 1
    assert searched == [2]


@pytest.mark.parametrize('language', ['CN', 'EN'])
@pytest.mark.parametrize('old_day', ['2026-11-08', '2026-10-01'])
def test_existing_placeholder_plus_date_is_repaired(language, old_day):
    value = '/' + formatted_date(old_day, language)
    source = sample_pdf(language=language, value=value, gap=0)
    final, audit = document_module.finalize_issue_date(
        source, '2026-11-08', category='Engineering', language=language)
    with fitz.open(stream=final, filetype='pdf') as pdf:
        text = ''.join(pdf[1].get_text().split())
    assert '/' not in text
    assert ''.join(formatted_date('2026-11-08', language).split()) in text
    again, _ = document_module.finalize_issue_date(
        final, '2026-11-08', category='Engineering', language=language)
    assert final == again


@pytest.mark.parametrize('new_day',['2026-10-24','2026-10-25'])
def test_reapproval_new_event_and_date(isolated_app,scenario_factory,new_day):
    from app.extensions import db
    from app.models import Report,ReportDocumentVersion,ReportEsignFlow,OperationAudit
    from app.report_issue_dates import finalize_approved_version
    from app.report_final_fields import approval_date
    from app.functions.stored_files import read_file_bytes
    user=scenario_factory.identity_scenario().user
    with isolated_app.app_context():
        raw=sample_pdf()
        r=Report(report_no='DATE-REAPPROVE',status='待打印',detail={})
        v=ReportDocumentVersion(report_no=r.report_no,output_kind='official',version_no=1,profile_code='TEST',
            status='approved',composition=[],warnings=[],snapshot={'template':{'profile':{'kind':'engineering','language':'CN','variant':'Standard'}}},
            source_hash='original',sha256=hashlib.sha256(raw).hexdigest(),pdf_data=raw)
        db.session.add_all([r,v]);db.session.flush();r.current_document_version_id=r.approved_document_version_id=v.id
        def event(action,when):
            e=OperationAudit(object_type='report',object_id=r.report_no,category='workflow',action=action,success=True,
                             created_at=datetime.fromisoformat(when));db.session.add(e);db.session.commit();return e
        first=event('report.approval.pass','2026-10-24T01:00:00')
        approved=finalize_approved_version(r,v,user);db.session.commit()
        old_pdf=read_file_bytes(approved.pdf_file,approved.pdf_data)
        stopped=ReportEsignFlow(report_id=r.id,report_no=r.report_no,report_document_version_id=approved.id,
            attempt_no=1,status='cancelled',provider_flow_id='stopped-upstream',source_sha256=approved.sha256)
        db.session.add(stopped);db.session.commit()
        event('report.approval.undo','2026-10-24T02:00:00')
        assert approval_date(r)==''
        latest=event('report.approval.pass',new_day+'T03:00:00')
        new=finalize_approved_version(r,approved,user);db.session.commit()
        assert new.id!=approved.id and new.snapshot['approvalDate']==new_day
        assert new.snapshot['issueDateVerification']['approvalEventId']==latest.id!=first.id
        assert read_file_bytes(approved.pdf_file,approved.pdf_data)==old_pdf and v.pdf_data==raw
        assert stopped.report_document_version_id==approved.id and stopped.status=='cancelled'
        assert finalize_approved_version(r,new,user).id==new.id
        with fitz.open(stream=read_file_bytes(new.pdf_file,new.pdf_data),filetype='pdf') as pdf:
            assert formatted_date(new_day,'CN') in ''.join(pdf[1].get_text().split())


@pytest.mark.parametrize('esign_prepare_fails', [False, True])
@pytest.mark.parametrize('missing_version', [False, True])
@pytest.mark.parametrize('bad_date_field', [False, True])
def test_approval_endpoint_finalizes_without_esign(isolated_app, isolated_client, scenario_factory,
                                                  monkeypatch, missing_version, bad_date_field, esign_prepare_fails):
    from app import docparser_field_only as fields, report_documents as documents
    from app.extensions import db
    from app.models import Report, ReportDocumentVersion, OperationAudit, ReportEsignFlow
    from app.report_final_fields import approval_date
    from app.functions.stored_files import read_file_bytes
    from app.applications.report_lifecycle import commands
    from testkit.factories import login_headers
    identity = scenario_factory.identity_scenario(permission_codes=('report.approval.view',),
                                                   granted_step_codes=('report_approval',))
    user = identity.user
    scenario_factory.grant_action(user, 'report.approval.pass')
    scenario_factory.grant_action(user, 'report.approval.undo')
    isolated_app.config.update(DOCUMENT_TEMPLATE_ENGINE=fields.ENGINE, ESIGN_WORKFLOW_ENABLED=esign_prepare_fails)
    if esign_prepare_fails:
        from app.functions import esign_service
        def fail_preparation(*args):
            raise RuntimeError('isolated signature preparation failure')
        monkeypatch.setattr(esign_service, 'ensure_report_esign_flow', fail_preparation)
    raw = sample_pdf(missing=bad_date_field)
    r = Report(report_no='LAB-DATE-APPROVE', status='待批准', department=identity.department.name,
               project=identity.project.name, owner=user.name, sample_reg_state='登记完成',
               sample_status='已领取', detail={'rawSample': {'reportType': '工程报告'}})
    db.session.add(r); db.session.flush()
    profile = {'kind':'engineering','language':'CN','variant':'Standard'}
    snapshot = {'report': {'reportNo': r.report_no, 'detail': r.detail}, 'template': {'profile':profile}, 'content': {}, 'attachments': []}
    if not missing_version:
        v = ReportDocumentVersion(report_no=r.report_no, output_kind='official', version_no=1,
            profile_code='TEST', status='generated', composition=[], snapshot=snapshot,
            warnings=[], source_hash='original', sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
        db.session.add(v); db.session.flush(); r.current_document_version_id=v.id
    db.session.commit()
    # Isolate office conversion/qualification acknowledgements; exercise the real
    # approval transaction, materialization, PDF finalization and database writes.
    monkeypatch.setattr(commands,'validate_and_record_acknowledgement',lambda *a:None)
    monkeypatch.setattr(documents,'document_preflight',lambda *a,**k:{'missing':[],'warnings':[],'content':{}})
    monkeypatch.setattr(documents,'source_snapshot',lambda *a,**k:snapshot)
    monkeypatch.setattr(documents,'build_document',lambda *a,**k:b'office-conversion-double')
    monkeypatch.setattr(documents,'build_complete_report_pdf',lambda *a,**k:(raw,[]))
    if not missing_version:
        from app.report_version_consistency import lock_reviewed_document
        lock_reviewed_document(r,user);db.session.commit()
    response=isolated_client.post('/api/reports/'+r.report_no+'/action',
        headers=login_headers(isolated_client,user.account),json={'action':'report.approval.pass'})
    if missing_version:
        assert response.json['code'] != 0 and '尚无当前正式报告' in response.json['message']
        assert r.status == '待批准'
        assert OperationAudit.query.filter_by(action='report.approval.pass', object_id=r.report_no).count() == 0
        return
    assert response.json['code']==0, response.json
    db.session.expire_all()
    assert r.status=='待打印' and approval_date(r)
    assert OperationAudit.query.filter_by(action='report.approval.pass',object_id=r.report_no).count()==1
    assert ReportEsignFlow.query.count()==0
    if esign_prepare_fails and not bad_date_field:
        assert response.json['data']['esignPrepareError'] == 'isolated signature preparation failure'
        assert '批准已保留' in response.json['message']
        assert OperationAudit.query.filter_by(action='report.esign.prepare.failed', success=False).count() == 1
    if bad_date_field:
        assert '报告日期核查未通过' in response.json['message']
        assert OperationAudit.query.filter_by(action='report.issue_date.failed',object_id=r.report_no).count()==1
    else:
        final=db.session.get(ReportDocumentVersion,r.approved_document_version_id)
        assert final.snapshot['issueDateVerification']['approvalDate']==approval_date(r)
        with fitz.open(stream=read_file_bytes(final.pdf_file,final.pdf_data),filetype='pdf') as pdf:
            assert formatted_date(approval_date(r),'CN') in ''.join(pdf[1].get_text().split())
        if not missing_version:
            previous_id=final.id
            previous_event=final.snapshot['issueDateVerification']['approvalEventId']
            headers=login_headers(isolated_client,user.account)
            undone=isolated_client.post('/api/reports/'+r.report_no+'/action',headers=headers,
                json={'action':'report.approval.undo'})
            assert undone.json['code']==0, undone.json
            assert approval_date(r)==''
            redone=isolated_client.post('/api/reports/'+r.report_no+'/action',headers=headers,
                json={'action':'report.approval.pass'})
            assert redone.json['code']==0, redone.json
            db.session.expire_all()
            latest=db.session.get(ReportDocumentVersion,r.approved_document_version_id)
            assert latest.id!=previous_id
            assert latest.snapshot['issueDateVerification']['approvalEventId']!=previous_event
            assert latest.sha256==final.sha256  # Same-day reapproval never overlays duplicate text.


def test_old_ready_flow_finalizes_before_first_upload(isolated_app,scenario_factory,monkeypatch):
    from app import docparser_field_only as fields
    from app.extensions import db
    from app.models import Report,ReportDocumentVersion,ReportEsignFlow,OperationAudit
    from app.report_issue_dates import prepare_dispatch_date
    isolated_app.config['DOCUMENT_TEMPLATE_ENGINE']=fields.ENGINE
    user=scenario_factory.identity_scenario().user
    raw=sample_pdf()
    r=Report(report_no='DATE-READY',status='待打印',detail={})
    v=ReportDocumentVersion(report_no=r.report_no,output_kind='official',version_no=1,profile_code='TEST',
        status='approved',composition=[],warnings=[],source_hash='old',sha256=hashlib.sha256(raw).hexdigest(),
        pdf_data=raw,snapshot={'template':{'profile':{'kind':'engineering','language':'CN','variant':'Standard'}}})
    db.session.add_all([r,v]);db.session.flush();r.current_document_version_id=r.approved_document_version_id=v.id
    flow=ReportEsignFlow(report_id=r.id,report_no=r.report_no,report_document_version_id=v.id,
                        attempt_no=1,status='ready',source_sha256=v.sha256)
    db.session.add_all([flow,OperationAudit(object_type='report',object_id=r.report_no,category='workflow',
        action='report.approval.pass',success=True,created_at=datetime(2026,10,24,1))]);db.session.commit()
    snapshot = {**v.snapshot, 'report': {'reportNo': r.report_no, 'detail': {}}, 'content': {}, 'attachments': []}
    v.snapshot = snapshot
    monkeypatch.setattr('app.report_documents.source_snapshot', lambda *a, **k: snapshot)
    from app.report_version_consistency import lock_reviewed_document
    lock_reviewed_document(r,user);db.session.commit()
    prepare_dispatch_date(flow,user);db.session.commit()
    assert flow.report_document_version_id==r.approved_document_version_id!=v.id
    assert flow.source_sha256==flow.document_version.sha256!=v.sha256
    assert v.pdf_data==raw
    flow.provider_file_id='already-uploaded';db.session.commit()
    previous=flow.report_document_version_id
    prepare_dispatch_date(flow,user)
    assert flow.report_document_version_id==previous
