"""No real provider calls: reproduce QC0525 stale PDF and workflow races."""
from copy import deepcopy
from datetime import datetime
import hashlib
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models import Report, ReportDocumentVersion, ReportEsignFlow, OperationAudit, ReportRenderJob
from app import report_documents as documents, docparser_field_only as fields
from app.report_version_consistency import require_current_document
from app.applications.report_lifecycle import commands

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def chain(isolated_app, scenario_factory, monkeypatch):
    identity = scenario_factory.identity_scenario(
        permission_codes=('report.review.view', 'report.approval.view', 'testing.data_entry.view'),
        granted_step_codes=('report_review', 'report_approval', 'data_entry'))
    report = Report(report_no='LAB-QA-0525', status='待审核', department=identity.department.name,
        project=identity.project.name, owner=identity.user.name, detail={'rawSample': {
            'trademark': '', 'factoryNo': '', 'produceDate': ''}})
    db.session.add(report); db.session.flush()
    isolated_app.config['DOCUMENT_TEMPLATE_ENGINE'] = fields.ENGINE
    inputs = dict(template={'profile': {'kind': 'product', 'language': 'CN', 'variant': 'Standard'},
                            'files': [{'sha256': 'template-v1'}]},
                  attachments=[{'id': 1, 'sha256': 'body-v1'}], content={'remarks': ''})
    def snapshot(r, *args, **kwargs):
        return deepcopy(dict(inputs, report={'reportNo': r.report_no, 'detail': r.detail},
                             approvalDate='', outputKind='official'))
    monkeypatch.setattr(documents, 'source_snapshot', snapshot)
    raw = b'%PDF-1.4\nunchanged-content'
    old = snapshot(report)
    version = ReportDocumentVersion(report_no=report.report_no, version_no=1, output_kind='official',
        profile_code='STANDARD-COVER-HOME', snapshot=old, source_hash=documents.snapshot_hash(old),
        sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
    db.session.add(version); db.session.flush(); report.current_document_version_id=version.id
    db.session.commit()
    return report, version, identity.user, inputs, snapshot


@pytest.mark.parametrize('key', ['trademark', 'factoryNo', 'produceDate'])
def test_qc0525_latest_form_cannot_approve_old_pdf(chain, monkeypatch, key):
    report, version, user, inputs, snapshot = chain
    # The real profile flag which bypassed the old gate.
    monkeypatch.setattr(commands, 'select_profile', lambda r: SimpleNamespace(requires_version=False))
    report.detail = {'rawSample': {**report.detail['rawSample'], key: '/'}}
    db.session.commit()
    assert '不一致' in commands.document_version_blocker(report)
    assert version.snapshot['report']['detail']['rawSample'][key] == ''


@pytest.mark.parametrize('change', ['body', 'template', 'content', 'chief', 'composition'])
def test_all_pdf_inputs_invalidate_version(chain, change):
    report, version, user, inputs, snapshot = chain
    if change == 'body': inputs['attachments'][0]['sha256'] = 'body-v2'
    elif change == 'template': inputs['template']['files'][0]['sha256'] = 'template-v2'
    elif change == 'content': inputs['content']['remarks'] = 'new result'
    elif change == 'chief': report.detail = {**report.detail, 'signatures': {'主检': 'new-chief'}}
    else: report.detail = {**report.detail, 'reportComposition': {'includedOtherAttachmentIds': [2]}}
    with pytest.raises(ValueError, match='不一致'): require_current_document(report, version)


def test_expected_workflow_metadata_does_not_change_report(chain):
    report, version, user, inputs, snapshot = chain
    original = deepcopy(version.snapshot)
    report.detail = {**report.detail, 'signatures': {'审核': 'reviewer', '批准': 'approver'},
                     'projectWorkflowSkips': [{'step': 'approval'}]}
    version.snapshot = {**version.snapshot, 'approvalDate': '2026-11-13',
                        'issueDateVerification': {'sourceVersionId': version.id}}
    assert require_current_document(report, version) is version
    assert original['report']['detail'] == version.snapshot['report']['detail']


@pytest.mark.parametrize('bad', ['missing', 'partial', 'other-report', 'corrupt'])
def test_no_unproven_version_passes(chain, bad):
    report, version, user, inputs, snapshot = chain
    if bad == 'missing': report.current_document_version_id=None
    elif bad == 'partial': version.snapshot={'template': {}}
    elif bad == 'other-report': version.report_no='OTHER'
    else: version.sha256='0'*64
    with pytest.raises(ValueError): require_current_document(report)


@pytest.mark.parametrize('action,status', [('report.report_check.pass','待校核'),
                                         ('report.review.pass','待审核'),('report.approval.pass','待批准')])
def test_real_command_rejects_stale_before_workflow_audit(chain, scenario_factory, monkeypatch, action, status):
    report, version, user, inputs, snapshot=chain
    scenario_factory.grant_action(user, action)
    report.status=status; report.detail={**report.detail, 'rawSample': {'trademark': '/'}}
    db.session.commit()
    monkeypatch.setattr('app.report_date_policy.report_date_error', lambda *a: '')
    monkeypatch.setattr(commands,'validate_and_record_acknowledgement',lambda *a:None)
    result=commands.execute_report_action(user, report.report_no, action, {})
    assert result.code != 0 and '不一致' in result.message
    assert report.status == status and report.current_document_version_id == version.id
    assert OperationAudit.query.filter_by(action=action).count()==0
    assert ReportEsignFlow.query.count()==0


def test_date_finalization_cannot_disguise_old_content(chain, monkeypatch):
    from app.report_final_fields import ensure_approved_date_version
    report, version, user, inputs, snapshot=chain
    report.approved_document_version_id=version.id
    report.detail={'rawSample': {'trademark': '/'}}
    db.session.add(OperationAudit(object_type='report',object_id=report.report_no,category='workflow',
        action='report.approval.pass',success=True,created_at=datetime(2026,11,13,6)))
    db.session.commit()
    monkeypatch.setattr('app.report_issue_dates.finalize_approved_version',
                        lambda *a: pytest.fail('stale content reached date stamping'))
    with pytest.raises(ValueError,match='不一致'): ensure_approved_date_version(report,version,user)
    assert ReportDocumentVersion.query.count()==1


@pytest.mark.parametrize('uploaded', [False, True])
def test_dispatch_rechecks_content_before_any_provider_call(chain, monkeypatch, uploaded):
    from app.functions import esign_service as service
    report, version, user, inputs, snapshot=chain
    report.status='待打印';report.approved_document_version_id=version.id
    report.detail={'rawSample': {'trademark': '/'}}
    flow=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=1,status='ready',source_sha256=version.sha256,provider_file_id='uploaded' if uploaded else None)
    db.session.add(flow);db.session.commit()
    monkeypatch.setattr('app.esign_production.require_flow',lambda *a:None)
    monkeypatch.setattr(service,'_require_dispatch_access',lambda *a:None)
    monkeypatch.setattr(service,'EsignV3Client',lambda:pytest.fail('unexpected provider call'))
    with pytest.raises(service.EsignServiceError,match='不一致'):service.dispatch_flow(flow.id,user)
    assert flow.report_document_version_id==version.id and flow.status=='ready'
    assert version.pdf_data==b'%PDF-1.4\nunchanged-content'


@pytest.mark.parametrize('change',['status','content'])
def test_slow_render_cannot_replace_newer_or_approved_version(chain, isolated_app, monkeypatch, change):
    report, version, user, inputs, snapshot=chain
    report.status='检测录入中';db.session.commit()
    job=ReportRenderJob(id='race-job',report_no=report.report_no,output_kind='official',requested_by=user.account)
    db.session.add(job);db.session.commit()
    monkeypatch.setattr(documents,'document_preflight',lambda *a,**k:{'missing':[],'warnings':[],'content':{}})
    monkeypatch.setattr(documents,'build_document',lambda *a,**k:b'docx')
    def render(r):
        # Model a completed concurrent write while the office renderer ran.
        if change=='status': r.status='待打印';r.approved_document_version_id=version.id
        else: r.detail={'rawSample': {'trademark': '/'}}
        db.session.commit()
        return b'%PDF-old-render',[]
    monkeypatch.setattr(documents,'build_complete_report_pdf',render)
    documents._execute_render_job(isolated_app,job.id)
    db.session.expire_all()
    assert db.session.get(ReportRenderJob,job.id).status=='failed'
    assert report.current_document_version_id==version.id
    assert ReportDocumentVersion.query.count()==1


@pytest.fixture
def preview_chain(chain, monkeypatch):
    from app import review_version, report_preview_confirmation as confirmation, preview_cache
    report, version, user, inputs, snapshot = chain
    report.status = '检测录入中'
    db.session.commit()
    raw = version.pdf_data
    def cached(r):
        return raw, dict(sourceHash=documents.snapshot_hash(snapshot(r)), pdfHash=hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(preview_cache, 'cached_pdf', cached)
    monkeypatch.setattr(confirmation, 'source_snapshot', snapshot)
    monkeypatch.setattr(review_version, 'source_snapshot', snapshot)
    monkeypatch.setattr(review_version, 'document_preflight', lambda *a: dict(missing=[], warnings=[]))
    return report, version, user, inputs, snapshot, cached


def test_ready_without_view_confirmation_cannot_complete(preview_chain):
    from app.review_version import freeze_ready_preview
    report, version, user, *_ = preview_chain
    with pytest.raises(ValueError, match='尚未确认最新预览'):
        freeze_ready_preview(report, user)
    assert report.status == '检测录入中'


@pytest.mark.parametrize('change', ['data', 'body', 'composition', 'template'])
def test_modified_after_confirm_requires_new_preview_even_after_reopen(preview_chain, change):
    from app import report_preview_confirmation as confirmation
    from app.review_version import freeze_ready_preview
    report, version, user, inputs, snapshot, cached = preview_chain
    token = confirmation.receipt(report, user, cached(report)[1])
    confirmation.confirm(report, user, token)
    db.session.commit()
    if change == 'data': report.detail = {'rawSample': {'trademark': '/'}}
    elif change == 'body': inputs['attachments'][0]['sha256'] = 'new-upload'
    elif change == 'template': inputs['template']['files'][0]['sha256'] = 'new-template'
    else: inputs['content']['compositionOptions'] = {'preserveUploadedReport': True}
    db.session.commit(); db.session.expire_all()
    with pytest.raises(ValueError, match='报告已修改'):
        confirmation.confirm(report, user, token)
    with pytest.raises(ValueError, match='尚未确认最新预览'):
        freeze_ready_preview(report, user)
    fresh = confirmation.receipt(report, user, cached(report)[1])
    confirmation.confirm(report, user, fresh)
    current = freeze_ready_preview(report, user)
    assert current.id != version.id
    assert current.source_hash == documents.snapshot_hash(snapshot(report))
    assert current.sha256 == cached(report)[1]['pdfHash']


@pytest.mark.parametrize('bad', ['empty', 'forged', 'user', 'report', 'pdf'])
def test_preview_receipt_is_bound_to_user_report_and_bytes(preview_chain, bad):
    from app import report_preview_confirmation as confirmation
    report, version, user, inputs, snapshot, cached = preview_chain
    state = cached(report)[1]
    token = confirmation.receipt(report, user, state)
    if bad == 'empty': token = None
    if bad == 'forged': token = 'fake-signature'
    if bad == 'user': token = confirmation.receipt(report, SimpleNamespace(id=user.id+1), state)
    if bad == 'report': token = confirmation.receipt(SimpleNamespace(report_no='other'), user, state)
    if bad == 'pdf': token = confirmation.receipt(report, user, {**state, 'pdfHash': 'wrong'})
    with pytest.raises(ValueError): confirmation.confirm(report, user, token)
    assert OperationAudit.query.filter_by(action=confirmation.ACTION).count() == 0


def test_confirm_and_freeze_reuses_only_the_pdf_that_was_viewed(preview_chain):
    from app import report_preview_confirmation as confirmation
    from app.review_version import freeze_ready_preview
    report, version, user, inputs, snapshot, cached = preview_chain
    confirmation.confirm(report, user, confirmation.receipt(report, user, cached(report)[1]))
    db.session.commit(); db.session.expire_all()
    assert freeze_ready_preview(report, user).id == version.id
    # An older official PDF with the same inputs must not replace the viewed bytes.
    version.pdf_data = b'%PDF-different-render'; version.sha256 = hashlib.sha256(version.pdf_data).hexdigest()
    db.session.flush()
    current = freeze_ready_preview(report, user)
    assert current.id != version.id and current.sha256 == cached(report)[1]['pdfHash']


@pytest.mark.parametrize('confirmed', [False, True])
def test_direct_completion_command_checks_server_confirmation(preview_chain, monkeypatch, confirmed):
    from app import report_preview_confirmation as confirmation
    from app.applications.testing_records import commands as testing
    report, version, user, inputs, snapshot, cached = preview_chain
    report.sample_status='已领取'
    report.detail={**report.detail, 'checkInput': dict(validatedForCompletion=True, standard='QA',
        instrument='QA', testStartDate='2026-11-01', testDate='2026-11-02')}
    db.session.commit()
    monkeypatch.setattr(testing, '_test_date_error', lambda *a: '')
    monkeypatch.setattr(testing, 'compute_report_checks', lambda *a: ([],False,''))
    if confirmed:
        confirmation.confirm(report,user,confirmation.receipt(report,user,cached(report)[1]))
        db.session.commit()
    result=testing.complete_test_data(user, report.report_no)
    assert (result.code == 0) is confirmed
    assert report.status == ('待审核' if confirmed else '检测录入中')
    assert OperationAudit.query.filter_by(action='report.data_entry.complete').count() == int(confirmed)


def test_preview_http_receipt_confirmation_download_and_permissions(preview_chain, isolated_client, scenario_factory):
    from testkit.factories import login_headers
    from app import report_preview_confirmation as confirmation
    report, version, user, inputs, snapshot, cached=preview_chain
    report.sample_status='已领取'; report.sample_reg_state='登记完成'
    scenario_factory.grant_action(user,'report.pdf.preview')
    db.session.commit()
    headers=login_headers(isolated_client,user.account)
    base='/api/reports/'+report.report_no
    response=isolated_client.get(base+'/complete-preview?view=data_entry',headers=headers)
    assert response.status_code==200 and response.mimetype=='application/pdf', response.json
    token=response.headers['X-Report-Preview-Receipt']
    assert OperationAudit.query.filter_by(action=confirmation.ACTION).count()==0
    download=isolated_client.get(base+'/complete-preview?view=data_entry&download=1',headers=headers)
    assert 'X-Report-Preview-Receipt' not in download.headers
    result=isolated_client.post(base+'/complete-preview-confirm',headers=headers,json={'receipt':token})
    assert result.json['code']==0, result.json
    assert OperationAudit.query.filter_by(action=confirmation.ACTION).count()==1
    report.detail={'rawSample':{'trademark':'/'}};db.session.commit()
    result=isolated_client.post(base+'/complete-preview-confirm',headers=headers,json={'receipt':token})
    assert result.json['code']!=0 and '报告已修改' in result.json['message']
    assert OperationAudit.query.filter_by(action=confirmation.ACTION).count()==1


def test_approval_cannot_change_rendered_seal_after_document_gate(chain, monkeypatch, scenario_factory):
    report, version, user, inputs, snapshot=chain
    scenario_factory.grant_action(user,'report.approval.pass')
    report.status='待批准';db.session.commit()
    monkeypatch.setattr('app.report_date_policy.report_date_error',lambda *a:'')
    def change_seal(r,*args):
        r.detail={**r.detail,'rawSample':{**r.detail['rawSample'],'seal':'CMA'}}
    from app.report_version_consistency import lock_reviewed_document
    lock_reviewed_document(report,user);db.session.commit()
    monkeypatch.setattr(commands,'validate_and_record_acknowledgement',change_seal)
    result=commands.execute_report_action(user,report.report_no,'report.approval.pass',{})
    assert result.code!=0 and '不一致' in result.message
    assert report.status=='待批准' and 'seal' not in report.detail['rawSample']
    assert OperationAudit.query.filter_by(action='report.approval.pass').count()==0


def test_real_snapshot_preview_freeze_review_approval_date_chain(isolated_app,scenario_factory,monkeypatch):
    from test_pdf_issue_date import sample_pdf
    from app import preview_cache, report_preview_confirmation as confirmation, review_version
    from app.report_final_fields import approval_date
    identity=scenario_factory.identity_scenario(
        permission_codes=('testing.data_entry.view','report.review.view','report.approval.view'),
        granted_step_codes=('data_entry','report_review','report_approval'))
    user=identity.user
    for action in ('report.review.pass','report.approval.pass'): scenario_factory.grant_action(user,action)
    isolated_app.config['DOCUMENT_TEMPLATE_ENGINE']=fields.ENGINE
    r=Report(report_no='LAB-QA-CHAIN-001',sample_no='QA-CHAIN-001',entrust_no='WT-QA-CHAIN-001',status='检测录入中',
        department=identity.department.name,project=identity.project.name,owner=user.name,
        sample_reg_state='登记完成',sample_status='已领取',detail={'rawSample':{'reportType':'工程报告'}})
    db.session.add(r);db.session.commit()
    raw=sample_pdf()
    from app.blueprints.report_publication import ensure_prepared_query
    ensure_prepared_query(r);db.session.commit()
    # Real source/template snapshot and PDF date engine; only office rendering is replaced.
    snap=documents.source_snapshot(r)
    # Other tests import these modules while source_snapshot is patched; bind
    # the real function explicitly so this integration is order-independent.
    monkeypatch.setattr(review_version,'source_snapshot',documents.source_snapshot)
    monkeypatch.setattr(confirmation,'source_snapshot',documents.source_snapshot)
    def cached(report):
        return raw, dict(sourceHash=documents.snapshot_hash(documents.source_snapshot(report)),
                        pdfHash=hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(preview_cache,'cached_pdf',cached)
    monkeypatch.setattr(review_version,'document_preflight',lambda *a:dict(missing=[],warnings=[]))
    confirmation.confirm(r,user,confirmation.receipt(r,user,cached(r)[1]))
    v=review_version.freeze_ready_preview(r,user)
    r.status='待审核';db.session.commit()
    assert v.snapshot==snap and v.sha256==hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr('app.report_date_policy.report_date_error',lambda *a:'')
    monkeypatch.setattr(commands,'validate_and_record_acknowledgement',lambda *a:None)
    reviewed=commands.execute_report_action(user,r.report_no,'report.review.pass',{})
    assert reviewed.code==0,reviewed.message
    monkeypatch.setattr(documents,'source_snapshot',lambda *a,**k:pytest.fail('approval rescanned full source'))
    approved=commands.execute_report_action(user,r.report_no,'report.approval.pass',{})
    assert approved.code==0 and not approved.data['issueDateError'],approved.message
    final=db.session.get(ReportDocumentVersion,r.approved_document_version_id)
    assert final.id!=v.id and final.snapshot['issueDateVerification']['sourceVersionId']==v.id
    assert final.snapshot['approvalDate']==approval_date(r)
    from app.report_version_consistency import require_reviewed_document
    assert require_reviewed_document(r,final) is final
    assert v.sha256==hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('operation',['upload','delete','content'])
def test_authoring_writes_recheck_locked_report_stage(chain,isolated_client,scenario_factory,monkeypatch,operation):
    from testkit.factories import login_headers
    from app.models import ReportAttachment
    from io import BytesIO
    report,version,user,inputs,snapshot=chain
    scenario_factory.grant_action(user,'report.attachment.upload')
    report.status='检测录入中';report.sample_status='已领取'
    attachment=ReportAttachment(report_no=report.report_no,name='extra.pdf',source='其他附件',
        kind='PDF',content_type='application/pdf',data=b'%PDF-1.4 synthetic',status='已上传')
    db.session.add(attachment);db.session.commit()
    monkeypatch.setattr('app.preview_cache.schedule_after_save',lambda *a:None)
    monkeypatch.setattr('app.blueprints.report_documents.document_preflight',lambda *a:dict(missing=[],warnings=[]))
    headers=login_headers(isolated_client,user.account)
    base='/api/reports/'+report.report_no
    def request():
        if operation=='upload':return isolated_client.post(base+'/attachments',headers=headers,
            data={'category':'other','file':(BytesIO(b'%PDF-1.4 synthetic'),'new.pdf')},content_type='multipart/form-data')
        if operation=='delete':return isolated_client.delete('/api/attachments/'+str(attachment.id),headers=headers)
        return isolated_client.put(base+'/document-content',headers=headers,json={'remarks':'new result'})
    result=request()
    assert result.json['code']==0,result.json
    report.status='待审核';db.session.commit()
    if operation=='delete':attachment.deleted_at=None;db.session.commit()
    result=request()
    assert result.json['code']!=0 and '锁定' in result.json['message'],result.json


@pytest.mark.parametrize('change',['data','body','content','pointer','file','revoke'])
def test_review_lock_invalidates_after_mutation_without_template_scan(chain,monkeypatch,change):
    from app.report_version_consistency import lock_reviewed_document,require_reviewed_document
    from app.models import ReportAttachment,ReportDocumentContent
    report,version,user,inputs,snapshot=chain
    lock_reviewed_document(report,user);db.session.commit()
    monkeypatch.setattr(documents,'source_snapshot',lambda *a,**k:pytest.fail('downstream full scan'))
    assert require_reviewed_document(report) is version
    if change=='data':report.detail={'rawSample':{'trademark':'/'}}
    elif change=='body':db.session.add(ReportAttachment(report_no=report.report_no,name='new.pdf',data=b'new',source='完整报告正文'))
    elif change=='content':db.session.add(ReportDocumentContent(report_no=report.report_no,remarks='changed'))
    elif change=='pointer':report.current_document_version_id=None
    elif change=='file':version.pdf_data=b'corrupt'
    else:db.session.add(OperationAudit(object_type='report',object_id=report.report_no,
        action='report.review.undo',category='workflow',success=True))
    db.session.commit()
    with pytest.raises(ValueError):require_reviewed_document(report,version)


def test_template_upgrade_after_review_keeps_locked_file(chain,monkeypatch):
    from app.report_version_consistency import lock_reviewed_document,require_reviewed_document
    report,version,user,inputs,snapshot=chain
    lock_reviewed_document(report,user);db.session.commit()
    inputs['template']['files'][0]['sha256']='next-release'
    monkeypatch.setattr(documents,'source_snapshot',lambda *a,**k:pytest.fail('template rescanned'))
    report.detail={**report.detail,'signatures':{'审核':'reviewer','批准':'approver'}}
    db.session.commit()
    assert require_reviewed_document(report) is version


def test_copied_date_snapshot_without_finalizer_audit_cannot_replace_locked_file(chain):
    from app.report_version_consistency import lock_reviewed_document,require_reviewed_document
    report,version,user,inputs,snapshot=chain
    lock_reviewed_document(report,user);db.session.commit()
    replacement=ReportDocumentVersion(report_no=report.report_no,output_kind='official',version_no=2,profile_code=version.profile_code,
        snapshot={**version.snapshot,'issueDateVerification':{'sourceVersionId':version.id}},
        source_hash=version.source_hash,sha256=version.sha256,pdf_data=version.pdf_data)
    db.session.add(replacement);db.session.flush();report.current_document_version_id=replacement.id
    with pytest.raises(ValueError):require_reviewed_document(report,replacement)


def test_configured_review_skip_still_locks_document(chain,monkeypatch):
    from app import project_workflow
    from app.report_version_consistency import require_reviewed_document
    report,version,user,inputs,snapshot=chain
    monkeypatch.setattr(project_workflow,'project_for_report',lambda r:SimpleNamespace(workflow_config={'skippedSteps':['report_review']}))
    assert project_workflow.advance_skipped_project_steps(report)==['报告审核']
    db.session.commit()
    assert report.status=='待批准'
    monkeypatch.setattr(documents,'source_snapshot',lambda *a,**k:pytest.fail('approval rescanned source'))
    assert require_reviewed_document(report) is version


def test_review_compares_full_source_only_once(chain,scenario_factory,monkeypatch):
    report,version,user,inputs,snapshot=chain
    scenario_factory.grant_action(user,'report.review.pass')
    monkeypatch.setattr('app.report_date_policy.report_date_error',lambda *a:'')
    monkeypatch.setattr(commands,'validate_and_record_acknowledgement',lambda *a:None)
    calls=[]
    def counted(*args,**kwargs):
        calls.append(1);return snapshot(*args,**kwargs)
    monkeypatch.setattr(documents,'source_snapshot',counted)
    result=commands.execute_report_action(user,report.report_no,'report.review.pass',{})
    assert result.code==0,result.message
    assert len(calls)==1


@pytest.mark.parametrize('stage', ['待校核', '待审核'])
def test_renderer_release_does_not_invalidate_confirmed_pdf(chain, stage):
    from app.report_version_consistency import lock_reviewed_document, require_reviewed_document
    report, version, user, inputs, snapshot = chain
    report.status = stage
    inputs['template'].update(release='old-release', files=[
        {'filename': 'report.docx', 'sha256': 'template-v1'},
        {'filename': 'document_module.py', 'sha256': 'code-v1'},
        {'filename': 'document_module_vendor_20260911.json', 'sha256': 'manifest-v1'}],
        originalSource={'files': [{'filename': 'pdf_helper.py', 'sha256': 'vendor-v1'}]},
        fieldValues={'TestDate': '2026年10月11日至2026年10月12日'})
    version.snapshot = snapshot(report)
    db.session.commit()
    saved = deepcopy(version.snapshot)
    inputs['template']['release'] = 'new-release'
    inputs['template']['files'][1]['sha256'] = 'code-v2'
    inputs['template']['files'][2]['sha256'] = 'manifest-v2'
    inputs['template']['originalSource']['files'][0]['sha256'] = 'vendor-v2'
    inputs['template']['fieldValues']['TestDate'] = '2026年10月11日至12日'
    assert require_current_document(report) is version
    lock_reviewed_document(report, user)
    report.status = '待批准'
    db.session.commit()
    assert require_reviewed_document(report) is version
    assert version.snapshot == saved
    assert version.pdf_data == b'%PDF-1.4\nunchanged-content'
    inputs['template']['files'][0]['sha256'] = 'template-v2'
    with pytest.raises(ValueError, match='不一致'):
        require_current_document(report)


@pytest.mark.parametrize('change', ['date', 'form', 'body', 'field', 'pdf'])
def test_renderer_upgrade_never_masks_actual_change(chain, change):
    report, version, _, inputs, snapshot = chain
    inputs['template'].update(files=[{'filename': 'document_module.py', 'sha256': 'old'}],
        fieldValues={'TestDate': '2026年10月11日至2026年10月12日', 'Conclusion': 'original'})
    version.snapshot = snapshot(report)
    db.session.commit()
    inputs['template']['files'][0]['sha256'] = 'new'
    if change == 'date': inputs['template']['fieldValues']['TestDate'] = '2026年10月11日至13日'
    if change == 'form': report.detail = {'rawSample': {'trademark': 'changed'}}
    if change == 'body': inputs['attachments'][0]['sha256'] = 'changed'
    if change == 'field': inputs['template']['fieldValues']['Conclusion'] = 'changed'
    if change == 'pdf': version.pdf_data = b'corrupted'
    with pytest.raises(ValueError):
        require_current_document(report)


@pytest.mark.parametrize('stage', ['待校核', '待审核', '待批准', '待打印', '检测录入中', '检测更改中'])
def test_preflight_renderer_upgrade_matches_workflow_and_keeps_draft_stale(chain, isolated_client, stage):
    from app.report_version_consistency import lock_reviewed_document
    from testkit.factories import login_headers
    report, version, user, inputs, snapshot = chain
    user.role_key = 'admin'
    report.status = stage
    inputs['template']['files'] = [{'filename': 'report.docx', 'sha256': 'template-v1'},
                                  {'filename': 'document_module.py', 'sha256': 'code-v1'}]
    version.snapshot = snapshot(report)
    version.source_hash = documents.snapshot_hash(version.snapshot)
    if stage in {'待批准', '待打印'}:
        lock_reviewed_document(report, user)
    db.session.commit()
    inputs['template']['files'][1]['sha256'] = 'code-v2'
    headers = login_headers(isolated_client, user.account)
    response = isolated_client.get(f'/api/reports/{report.report_no}/document-preflight?view=query', headers=headers)
    assert response.status_code == 200
    result = response.get_json()
    assert result['code'] == 0, result
    assert result['data']['currentVersionStale'] is (stage in {'检测录入中', '检测更改中'})
    assert commands.document_version_blocker(report, reviewed=stage in {'待批准', '待打印'}) == ''
    report.detail = {**report.detail, 'rawSample': {'trademark': 'changed'}}
    db.session.commit()
    changed = isolated_client.get(f'/api/reports/{report.report_no}/document-preflight?view=query', headers=headers).get_json()
    assert changed['data']['currentVersionStale'] is True
    assert commands.document_version_blocker(report, reviewed=stage in {'待批准', '待打印'})


@pytest.mark.parametrize('change', ['template', 'body', 'date', 'field'])
def test_preflight_retains_actual_input_blockers(chain, change):
    report, version, _, inputs, snapshot = chain
    inputs['template'].update(files=[{'filename': 'report.docx', 'sha256': 'template-v1'}],
                              fieldValues={'TestDate': '2026年10月11日至12日', 'cmaOptionalPolicy': 'old'})
    version.snapshot = snapshot(report)
    version.source_hash = documents.snapshot_hash(version.snapshot)
    if change == 'template': inputs['template']['files'][0]['sha256'] = 'template-v2'
    if change == 'body': inputs['attachments'][0]['sha256'] = 'body-v2'
    if change == 'date': inputs['template']['fieldValues']['TestDate'] = '2026年10月11日至13日'
    if change == 'field': inputs['template']['fieldValues']['cmaOptionalPolicy'] = 'new'
    assert documents.document_preflight(report, render_template=False)['currentVersionStale'] is True
    assert commands.document_version_blocker(report)


def test_approval_checks_reviewed_version_once_after_compliance(chain, scenario_factory, monkeypatch):
    from app import report_version_consistency as consistency
    report, version, user, inputs, snapshot = chain
    scenario_factory.grant_action(user, 'report.approval.pass')
    report.status = '待批准'
    consistency.lock_reviewed_document(report, user)
    db.session.commit()
    monkeypatch.setattr('app.report_date_policy.report_date_error', lambda *a: '')
    calls = []
    original = consistency.require_reviewed_document
    def check(*args, **kwargs):
        calls.append('version')
        return original(*args, **kwargs)
    def compliance(r, *args):
        calls.append('compliance')
        r.detail = {**r.detail, 'rawSample': {'trademark': 'changed'}}
    monkeypatch.setattr(consistency, 'require_reviewed_document', check)
    monkeypatch.setattr(commands, 'validate_and_record_acknowledgement', compliance)
    result = commands.execute_report_action(user, report.report_no, 'report.approval.pass', {})
    assert result.code != 0
    assert calls == ['compliance', 'version']
    assert report.status == '待批准'
    assert OperationAudit.query.filter_by(action='report.approval.pass').count() == 0
