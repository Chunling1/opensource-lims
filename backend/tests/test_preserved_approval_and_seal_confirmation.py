"""Temporary DB/files and provider doubles; never contacts eSign or production."""
import copy
import hashlib
import json
from datetime import datetime, timedelta

import fitz
import pytest
from app.extensions import db
from app.models import Report, ReportDocumentVersion, ReportEsignFlow, ReportEsignSigner, OperationAudit
from app.audit import add_operation_audit
from app.functions import esign_service as service
from app.esign_seal_confirmation import assign, has_permission
from app.functions.stored_files import persist_bytes
from app.report_final_fields import approval_date, ensure_approved_date_version
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)


def test_cancelled_flow_rebuild_preserves_history_and_requires_new_signatures(prepared, monkeypatch):
    from app.models import EsignIdentityBinding
    report, version, user, raw = prepared
    old = signed_source(prepared)
    old.status = 'cancelled'
    binding = EsignIdentityBinding(user_id=user.id, legal_name=user.name,
        psn_account='13800000000', psn_id='isolated-person', status='verified')
    db.session.add(binding)
    db.session.commit()
    old_file_id, old_provider = old.signed_file_id, old.provider_flow_id
    monkeypatch.setattr(service, 'resolve_report_signers', lambda *args: ({role:user for role in ('chief','reviewer','approver')}, []))
    monkeypatch.setattr(service, 'report_signer_roles', lambda *args: service.ROLE_DEFINITIONS)
    new = service.ensure_report_esign_flow(report.report_no, user)
    db.session.expire_all()
    assert new.id != old.id and new.attempt_no == old.attempt_no + 1
    assert new.status == 'ready' and not new.provider_flow_id and not new.signed_file_id
    assert len(new.signers) == 3 and all(s.status == 'pending' and s.signed_at is None for s in new.signers)
    assert new.report_document_version_id == version.id and new.source_sha256 == version.sha256
    assert version.pdf_data == raw
    assert old.status == 'cancelled' and old.signed_file_id == old_file_id and old.provider_flow_id == old_provider
    assert all(s.status == 'signed' for s in old.signers)
    assert service.ensure_report_esign_flow(report.report_no, user).id == new.id


@pytest.fixture
def prepared(isolated_app, scenario_factory, monkeypatch):
    monkeypatch.setitem(isolated_app.config, 'ESIGN_PRODUCTION_READY', True)
    monkeypatch.setitem(isolated_app.config, 'ESIGN_PROVIDER_FLOW_MIN_ID', 0)
    monkeypatch.setitem(isolated_app.config, 'ESIGN_REQUIRED_FOR_ISSUANCE', True)
    scenario = scenario_factory.identity_scenario()
    user = scenario.user
    report = Report(report_no='TEST-SEAL-001', sample_no='TEST-SEAL-S', department=scenario.department.name,
        project=scenario.project.name, owner=user.name, status='待打印',
        detail={'reportComposition': {'preserveUploadedReport': True}})
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 60), 'CUSTOM COVER DO NOT REPLACE')
        pdf.new_page().insert_text((50, 60), 'TEST-SEAL-001 body')
        raw = pdf.tobytes()
    version = ReportDocumentVersion(report_no=report.report_no, output_kind='official', version_no=1,
        status='approved', profile_code='TEST', composition=[], snapshot={'approvalDate': ''},
        warnings=[], source_hash='test-source', sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
    db.session.add_all([report, version]); db.session.flush()
    report.current_document_version_id = report.approved_document_version_id = version.id
    add_operation_audit('report.approval.pass','report',report.report_no,category='workflow',actor=user)
    db.session.commit()
    return report, version, user, raw


@pytest.mark.parametrize('old_date', ['', '2000-01-01'])
@pytest.mark.parametrize('stored', [False, True])
def test_preserved_date_new_version_keeps_entire_pdf_and_old_snapshot(prepared, monkeypatch, old_date, stored):
    report, old, user, raw = prepared
    old.snapshot = {'approvalDate': old_date, 'report': {'detail': {'custom': 'unchanged'}}}
    if stored:
        old.pdf_file = persist_bytes(raw, category='report_document', original_name='original.pdf',
            content_type='application/pdf', created_by='test')
        old.pdf_data = None
    db.session.commit()
    before = copy.deepcopy(old.snapshot)
    monkeypatch.setattr('app.report_documents.materialize_approved_report_pdf', lambda *a: pytest.fail('must not render'))
    result = service._approved_version(report, user)
    db.session.commit()
    assert result.id != old.id and result.version_no == 2
    assert old.snapshot == before and result.sha256 == old.sha256
    assert result.pdf_file_id == old.pdf_file_id and result.pdf_data == old.pdf_data
    assert result.snapshot['approvalDate'] == approval_date(report)
    assert result.snapshot['approvalDateBinding']['pdfContentUnchanged'] is True
    assert service._approved_version(report, user).id == result.id
    assert ReportDocumentVersion.query.count() == 2
    assert OperationAudit.query.filter_by(action='report.esign.preserved_approval.bind').count() == 1


@pytest.mark.parametrize('status,provider', [('signing','upstream'), ('failed','uploaded'), ('completed','upstream')])
def test_dispatched_versions_are_never_replaced(prepared, status, provider):
    report, old, user, raw = prepared
    db.session.add(ReportEsignFlow(report_id=report.id,report_no=report.report_no,
        report_document_version_id=old.id,attempt_no=1,status=status,provider_file_id=provider,source_sha256=old.sha256))
    db.session.commit()
    assert service._approved_version(report,user).id == old.id
    assert ReportDocumentVersion.query.count() == 1 and old.snapshot['approvalDate'] == ''


def test_corrupt_preserved_pdf_refused_without_pointer_change(prepared):
    report, old, user, raw = prepared
    old.sha256='0'*64; db.session.commit()
    with pytest.raises(service.EsignServiceError, match='哈希'):
        service._approved_version(report,user)
    assert report.approved_document_version_id == old.id and ReportDocumentVersion.query.count() == 1


def test_nonpreserved_still_uses_original_renderer(prepared, monkeypatch):
    report, old, user, raw = prepared
    report.detail={}; db.session.commit()
    called=[]
    def render(report,actor):
        called.append(report.id); old.snapshot={'approvalDate': approval_date(report)}; return old
    monkeypatch.setattr('app.report_documents.materialize_approved_report_pdf',render)
    assert ensure_approved_date_version(report,old,user) is old and called == [report.id]


def signed_source(prepared):
    report, version, user, raw = prepared
    version.snapshot={'approvalDate': approval_date(report)}
    flow=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=1,status='signing',source_sha256=version.sha256,provider_flow_id='fake-person-flow',
        positioning_json=json.dumps({'flowKind':'person_signing','organizationSeal':{'included':False}}))
    db.session.add(flow); db.session.flush()
    for i,role in enumerate(('chief','reviewer','approver')):
        flow.signers.append(ReportEsignSigner(user_id=user.id,role_code=role,role_name=role,legal_name_snapshot=user.name,sign_order=i+1,status='signed'))
    service.store_signed_file(flow,raw,user); db.session.commit()
    return flow


def test_person_complete_waits_for_confirmation_and_download_is_blocked(prepared, isolated_client):
    report, version, user, raw = prepared
    flow=signed_source(prepared)
    user.role_key='admin'; db.session.commit()
    assert service._organization_seal_state(flow)['status']=='awaiting_confirmation'
    assert not service.flow_has_organization_seal(flow)
    assert service.issuance_blocker(report)
    response=isolated_client.get(f'/api/esign/flows/{flow.id}/signed-pdf',headers=login_headers(isolated_client,user.account))
    assert response.status_code == 410
    headers=login_headers(isolated_client,user.account)
    artifact=f'/api/report-assurance/reports/{report.report_no}/artifact?view=print&file=1'
    assert isolated_client.get(artifact+'&download=1',headers=headers).data==raw
    assert isolated_client.get(artifact+'&signed=1&download=1',headers=headers).status_code==409
    assert isolated_client.get(artifact,headers=headers).status_code==200
    historical=f'/api/report-assurance/reports/{report.report_no}/signing-history/{flow.id}/file?view=print'
    assert isolated_client.get(historical+'&download=1',headers=headers).status_code==410


def test_confirmation_requires_explicit_grant_even_admin_and_binds_source(prepared):
    report, version, user, raw=prepared
    source=signed_source(prepared)
    user.role_key='admin'; db.session.commit()
    args=dict(source_flow_id=source.id,source_sha256=source.signed_sha256)
    with pytest.raises(service.EsignServiceError,match='权限'):
        service.ensure_organization_seal_flow(report.report_no,user,**args)
    assign(user,True); db.session.commit()
    assert has_permission(user)
    result=service.ensure_organization_seal_flow(report.report_no,user,**args)
    assert result.id != source.id and not result.signers
    confirmation=service._organization_seal_state(result)['confirmation']
    assert confirmation['userId']==user.id and confirmation['sourceSha256']==source.signed_sha256
    assert service.ensure_organization_seal_flow(report.report_no,user,**args).id==result.id
    assert OperationAudit.query.filter_by(action='report.esign.organization_seal.confirm').count()==1
    assign(user,False); db.session.commit()
    with pytest.raises(service.EsignServiceError,match='权限'):
        service.dispatch_flow(result.id,user)


@pytest.mark.parametrize('invalid', ['hash','version','incomplete','missing_role','void','scope'])
def test_stale_or_unapproved_source_cannot_be_confirmed(prepared, scenario_factory, invalid):
    report, version, user, raw=prepared
    source=signed_source(prepared); assign(user,True)
    digest=source.signed_sha256
    if invalid=='hash': digest='f'*64
    elif invalid=='version': report.approved_document_version_id=None
    elif invalid=='incomplete': source.signers[0].status='pending'
    elif invalid=='missing_role': db.session.delete(source.signers.pop())
    elif invalid=='void': report.voided=True
    elif invalid=='scope':
        user=scenario_factory.user(scenario_factory.department(),account='other-sealer');assign(user,True)
    db.session.commit()
    with pytest.raises(service.EsignServiceError):
        service.ensure_organization_seal_flow(report.report_no,user,source_flow_id=source.id,source_sha256=digest)
    assert ReportEsignFlow.query.count()==1


def test_service_cli_cannot_dispatch_unconfirmed_organization_flow(prepared):
    report,version,user,raw=prepared
    flow=signed_source(prepared)
    flow.positioning_json=json.dumps({'flowKind':'organization_seal','organizationSeal':{'included':True}})
    flow.status='ready';flow.provider_flow_id=None;db.session.commit()
    with pytest.raises(service.EsignServiceError): service.dispatch_flow(flow.id,None)


def test_person_dispatch_payload_never_contains_seal_even_config_enabled(prepared, monkeypatch, isolated_app):
    from app.models import EsignIdentityBinding
    report,version,user,raw=prepared
    user.role_key='admin'
    version.snapshot={'approvalDate':approval_date(report)}
    binding=EsignIdentityBinding(user_id=user.id,legal_name=user.name,psn_account='13800000001',status='pending')
    db.session.add(binding)
    flow=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=1,status='ready',source_sha256=version.sha256)
    db.session.add(flow);db.session.flush()
    for i,role in enumerate(('chief','reviewer','approver')):
        flow.signers.append(ReportEsignSigner(user_id=user.id,binding=binding,role_code=role,role_name=role,legal_name_snapshot=user.name,sign_order=i+1,status='pending'))
    db.session.commit()
    monkeypatch.setitem(isolated_app.config,'ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED',True)
    monkeypatch.setitem(isolated_app.config,'ESIGN_ENABLED',True)
    monkeypatch.setitem(isolated_app.config,'ESIGN_ORG_AUTOSIGN_ENABLED',True)
    monkeypatch.setitem(isolated_app.config,'DEPLOYMENT_ROLE','standard')
    captured=[]
    class Client:
        def upload_pdf(self,*args): return 'fake-file'
        def request(self,*args): captured.append(args[2]);return {'signFlowId':'fake-provider'}
    monkeypatch.setattr(service,'EsignV3Client',Client)
    monkeypatch.setattr(service,'_resolve_sign_positions',lambda *a: ({r:{'positionPage':'2','positionX':10,'positionY':10} for r in ('chief','reviewer','approver')},{}))
    monkeypatch.setattr(service,'_organization_signer',lambda *a,**k: pytest.fail('person flow must not request a seal'))
    result=service.dispatch_flow(flow.id,user)
    assert len(captured)==1 and len(captured[0]['signers'])==3
    assert all(s['signerType']==0 for s in captured[0]['signers'])
    assert captured[0]['signFlowConfig']['autoFinish'] is False
    assert result.to_dict()['signingMode'] == 'single_flow_confirmation_v1'
    assert service._organization_seal_state(result)['included'] is False


def test_confirm_dispatch_complete_seal_and_download(prepared, monkeypatch, isolated_app, isolated_client):
    report,version,user,raw=prepared
    source=signed_source(prepared)
    user.role_key='admin';assign(user,True);db.session.commit()
    monkeypatch.setitem(isolated_app.config,'ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED',True)
    monkeypatch.setitem(isolated_app.config,'ESIGN_ENABLED',True)
    monkeypatch.setitem(isolated_app.config,'DEPLOYMENT_ROLE','standard')
    captured=[]
    class Client:
        def upload_pdf(self,name,data):
            assert data==raw
            return 'fake-seal-file'
        def request(self,*args): captured.append(args[2]);return {'signFlowId':'fake-seal-provider'}
    monkeypatch.setattr(service,'EsignV3Client',Client)
    pos={key:{'positionPage':'1','positionX':30,'positionY':30} for key in ('cover','titleCover','date')}
    monkeypatch.setattr(service,'_resolve_sign_positions',lambda client,flow,file: (pos,{**service._positioning_snapshot(flow),'layoutKind':'calibration'}))
    monkeypatch.setattr(service,'_organization_signer',lambda *a,**k: {'signerType':1,'signFields':[{'fileId':'fake-seal-file'}]})
    headers=login_headers(isolated_client,user.account)
    endpoint=f'/api/esign/reports/{report.report_no}/organization-seal'
    assert isolated_client.post(endpoint,json={},headers=headers).status_code==400
    body={'confirmed':True,'sourceFlowId':source.id,'sourceSha256':source.signed_sha256}
    response=isolated_client.post(endpoint,json=body,headers=headers)
    assert response.json['code']==0,response.json
    sealed=db.session.get(ReportEsignFlow,response.json['data']['id'])
    assert sealed.status=='signing' and service._organization_seal_state(sealed)['confirmation']['userId']==user.id
    assert len(captured)==1 and [s['signerType'] for s in captured[0]['signers']]==[1]
    assert isolated_client.post(endpoint,json=body,headers=headers).json['code']==0
    assert len(captured)==1
    service.store_signed_file(sealed,raw,user);db.session.commit()
    assert service.issuance_blocker(report) is None
    result=isolated_client.get(f'/api/report-assurance/reports/{report.report_no}/artifact?view=query&signed=1&file=1&download=1',headers=headers)
    assert result.status_code==200 and result.data==raw
    assign(user,False);db.session.commit()
    assert isolated_client.post(f'/api/esign/flows/{sealed.id}/dispatch',json={},headers=headers).status_code==403


def test_org_page_grant_revoke_and_unrelated_save(prepared, isolated_client):
    report,version,user,raw=prepared
    user.role_key='admin';db.session.commit()
    headers=login_headers(isolated_client,user.account)
    url=f'/api/admin/departments/{user.department_id}/members/{user.id}/authorizations'
    for enabled in (True,False):
        response=isolated_client.put(url,json={'sealConfirmation':enabled},headers=headers)
        assert response.json['code']==0,response.json
        assert has_permission(user) is enabled
        assert isolated_client.get(url,headers=headers).json['data']['sealConfirmation'] is enabled
        assert isolated_client.put(url,json={},headers=headers).json['code']==0
        assert has_permission(user) is enabled


def test_superseded_seal_confirmation_is_rejected(prepared):
    report,version,user,raw=prepared
    source=signed_source(prepared);user.role_key='admin';assign(user,True);db.session.commit()
    args=dict(source_flow_id=source.id,source_sha256=source.signed_sha256)
    seal=service.ensure_organization_seal_flow(report.report_no,user,**args)
    newer=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=seal.attempt_no+1,status='ready',source_sha256=version.sha256)
    db.session.add(newer);db.session.commit()
    with pytest.raises(service.EsignServiceError,match='变化'):
        service.ensure_organization_seal_flow(report.report_no,user,**args)



def test_report_panel_only_returns_current_approved_version(prepared,isolated_client):
    report,version,user,raw=prepared
    old=signed_source(prepared);old.attempt_no=8
    user.role_key='admin'
    report.approved_document_version_id=None
    version.snapshot={'approvalDate':''}
    report.approved_document_version_id=version.id
    # A newer controlled version without a task must not expose the older flow.
    newer=ReportDocumentVersion(report_no=report.report_no,output_kind='official',version_no=2,
        status='approved',profile_code='TEST',composition=[],snapshot={},warnings=[],source_hash='new',sha256=version.sha256,pdf_data=raw)
    db.session.add(newer);db.session.flush();report.approved_document_version_id=newer.id;db.session.commit()
    response=isolated_client.get(f'/api/esign/reports/{report.report_no}',headers=login_headers(isolated_client,user.account))
    assert response.json['data'] is None



def test_seal_grant_does_not_break_generic_permission_export(prepared,scenario_factory,isolated_client):
    from io import BytesIO
    from openpyxl import load_workbook
    report,version,user,raw=prepared
    assign(user,True);db.session.commit()
    admin=scenario_factory.user(scenario_factory.department(),account='export-admin')
    admin.role_key='admin';db.session.commit()
    response=isolated_client.get('/api/admin/permission-templates/export',headers=login_headers(isolated_client,admin.account))
    assert response.status_code==200,response.data[:200]
    book=load_workbook(BytesIO(response.data))
    assert all(row[3]!='report.seal.confirm' for row in book['人员实际操作权限'].iter_rows(min_row=2,values_only=True))
    assert has_permission(user)


def test_org_delivery_grants_roundtrip_preserve_and_revoke(prepared, isolated_client):
    from app.models import User, user_action_permissions
    from app.report_delivery import SEALED_DOWNLOAD, RELEASE_ACTION
    report, version, admin, raw = prepared
    admin.role_key = 'admin'
    from testkit.factories import ScenarioFactory
    target = ScenarioFactory().user(admin.department, account='delivery-grant-target')
    db.session.commit()
    headers = login_headers(isolated_client, admin.account)
    url = f'/api/admin/departments/{target.department_id}/members/{target.id}/authorizations'
    for enabled in (True, False):
        body = {'sealedReportDownload': enabled, 'reportDistribution': enabled}
        response = isolated_client.put(url, json=body, headers=headers)
        assert response.json['code'] == 0, response.json
        data = isolated_client.get(url, headers=headers).json['data']
        assert data['sealedReportDownload'] is enabled and data['reportDistribution'] is enabled
        assert data['reportDeliveryInherited'] is False
        assert isolated_client.put(url, json={}, headers=headers).json['code'] == 0
        codes = {r[0] for r in db.session.execute(db.select(user_action_permissions.c.action_code).where(user_action_permissions.c.user_id == target.id))}
        assert (SEALED_DOWNLOAD in codes) is enabled and (RELEASE_ACTION in codes) is enabled
    for field in ('sealedReportDownload', 'reportDistribution'):
        assert isolated_client.put(url, json={field: 'false'}, headers=headers).json['code'] != 0
    # Non-admin cannot grant themselves authority.
    target_headers = login_headers(isolated_client, target.account)
    response = isolated_client.put(url, json={'sealedReportDownload': True}, headers=target_headers)
    assert response.status_code == 403 or response.json['code'] != 0
