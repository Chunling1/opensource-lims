import json
import pytest
from app.extensions import db
from app.models import EsignIdentityBinding, ReportEsignFlow, OperationAudit
from app.functions import esign_service as service
from app.functions import esign_cancellation as cancellation
from testkit.factories import login_headers
from test_preserved_approval_and_seal_confirmation import prepared, signed_source

pytest_plugins = ('testkit.fixtures',)


@pytest.fixture
def round_data(prepared, monkeypatch, isolated_app):
    report, version, user, raw = prepared
    user.role_key = 'admin'
    flow = signed_source(prepared)
    db.session.add(EsignIdentityBinding(user_id=user.id, legal_name=user.name,
        psn_account='13800000000', status='verified'))
    db.session.commit()
    monkeypatch.setitem(isolated_app.config, 'ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED', True)
    # Exercise the real integration routes with provider doubles and socket denied
    # by the runner; the fixture restores the isolated profile before teardown.
    monkeypatch.setitem(isolated_app.config, 'DEPLOYMENT_ROLE', 'standard')
    return report, version, user, raw, flow


def provider(monkeypatch, statuses, org=False, seal=False, fail=False):
    calls=[]
    statuses=iter(statuses)
    class Fake:
        def request(self, method, path, payload=None):
            calls.append((method, path, payload))
            if fail and method=='POST':
                raise service.EsignServiceError('provider_unavailable', 'timeout')
            if method=='POST':return {}
            return {'signFlowStatus':next(statuses), 'signers':[{'signerType':1 if org else 0,
                'signStatus':2 if seal else 1, 'signFields':[{'signFieldStatus':4 if seal else 0}]}]}
    monkeypatch.setattr(cancellation, 'EsignV3Client', Fake)
    return calls


def test_partial_signing_revokes_and_returns_pending_round(round_data, monkeypatch, isolated_client):
    report,version,user,raw,old=round_data
    old.status='signing';old.signers[-1].status='pending';db.session.commit()
    before=old.to_dict();calls=provider(monkeypatch,[1,3])
    headers=login_headers(isolated_client,user.account)
    response=isolated_client.post(f'/api/esign/flows/{old.id}/cancel',headers=headers,
        json={'confirmed':True,'reason':'录入更正'})
    assert response.status_code==200,response.json
    new=db.session.get(ReportEsignFlow,response.json['data']['id'])
    assert new.id!=old.id and new.status=='ready' and all(s.status=='pending' and not s.signed_at for s in new.signers)
    assert not new.signed_file_id and not new.provider_flow_id
    assert new.report_document_version_id==version.id and version.pdf_data==raw
    assert old.status=='cancelled' and old.signed_file_id and old.to_dict()['signers']==before['signers']
    assert report.status=='待打印' and report.approved_document_version_id==version.id
    assert [x[0] for x in calls]==['GET','POST','GET']
    assert calls[1][1].endswith('/revoke') and calls[1][2]=={'revokeReason':'录入更正'}
    assert cancellation.cancel_and_restart(old.id,user,'重复点击').id==new.id
    assert len(calls)==3 and ReportEsignFlow.query.count()==2
    assert service.ensure_report_esign_flow(report.report_no,user).id==new.id
    assert OperationAudit.query.filter_by(action='report.esign.cancel.restart').count()==1


def test_completed_personal_pdf_retired_without_revoking_completed_provider(round_data,monkeypatch):
    report,version,user,raw,old=round_data
    calls=provider(monkeypatch,[2])
    new=cancellation.cancel_and_restart(old.id,user,'未盖章重新签署')
    assert len(calls)==1 and old.status=='cancelled' and new.status=='ready'
    assert json.loads(old.positioning_json)['cancellation']['mode']=='retired_personal_round'
    assert old.signed_file_id and old.signed_sha256


@pytest.mark.parametrize('state',['signing','completed'])
def test_nonadmin_denied_before_provider(round_data,monkeypatch,isolated_client,state):
    report,version,user,raw,old=round_data
    old.status=state;user.role_key='staff';db.session.commit()
    calls=provider(monkeypatch,[])
    response=isolated_client.post(f'/api/esign/flows/{old.id}/cancel',headers=login_headers(isolated_client,user.account),json={'confirmed':True,'reason':'test'})
    assert response.status_code==403 and not calls


def _issuer(user, with_step):
    # Batch-3 Q7 (2026-11-07): report issuers (report.print.view -> report.print.pass) may cancel.
    from app.models import Permission, ProjectStep
    user.role_key = 'staff'
    perm = db.session.get(Permission, 'report.print.view') or Permission(code='report.print.view', name='报告签发', ptype='page')
    user.permissions.append(perm)
    if perm not in user.department.permissions:
        user.department.permissions.append(perm)
    if with_step:
        step = ProjectStep.query.filter_by(step_code='report_print').one()
        user.project_steps.append(step)
        if step not in user.department.project_steps:
            user.department.project_steps.append(step)
    db.session.commit()


def test_issuer_with_project_step_can_cancel_unsealed_round(round_data, monkeypatch, isolated_client):
    report, version, user, raw, old = round_data
    old.status = 'signing'; old.signers[-1].status = 'pending'
    _issuer(user, with_step=True)
    assert cancellation.cancel_actor_error(user, old) == ''
    calls = provider(monkeypatch, [1, 3])
    response = isolated_client.post(f'/api/esign/flows/{old.id}/cancel', headers=login_headers(isolated_client, user.account),
        json={'confirmed': True, 'reason': '签发人撤销'})
    assert response.status_code == 200, response.json
    assert old.status == 'cancelled' and [x[0] for x in calls] == ['GET', 'POST', 'GET']
    audit = OperationAudit.query.filter_by(action='report.esign.cancel.restart').one()
    assert audit.account == user.account


def test_issuer_without_project_step_denied_before_provider(round_data, monkeypatch, isolated_client):
    report, version, user, raw, old = round_data
    old.status = 'signing'
    _issuer(user, with_step=False)
    calls = provider(monkeypatch, [])
    response = isolated_client.post(f'/api/esign/flows/{old.id}/cancel', headers=login_headers(isolated_client, user.account),
        json={'confirmed': True, 'reason': 'test'})
    assert response.status_code == 403 and not calls
    assert '报告' in response.json['message']


def test_issuer_still_cannot_cancel_sealed_round(round_data, monkeypatch):
    report, version, user, raw, old = round_data
    _issuer(user, with_step=True)
    old.positioning_json = json.dumps({'organizationSeal': {'included': True}}); db.session.commit()
    calls = provider(monkeypatch, [])
    with pytest.raises(service.EsignServiceError):
        cancellation.cancel_and_restart(old.id, user, 'test')
    assert not calls and ReportEsignFlow.query.count() == 1


@pytest.mark.parametrize('change',['sealed','issued','dispatching','stale','unknown_create'])
def test_ineligible_denied_without_provider(round_data,monkeypatch,change):
    report,version,user,raw,old=round_data
    if change=='sealed':old.positioning_json=json.dumps({'organizationSeal':{'included':True}})
    if change=='issued':report.status='待发放'
    if change=='dispatching':old.status='dispatching'
    if change=='stale':report.approved_document_version_id=None
    if change=='unknown_create':
        old.status='failed';old.provider_flow_id=None;old.provider_file_id='uploaded';old.error_code='provider_unavailable'
    db.session.commit();calls=provider(monkeypatch,[])
    with pytest.raises(service.EsignServiceError):cancellation.cancel_and_restart(old.id,user,'test')
    assert not calls and ReportEsignFlow.query.count()==1


def test_timeout_keeps_gate_and_can_resume_without_duplicate_round(round_data,monkeypatch):
    report,version,user,raw,old=round_data
    old.status='signing';db.session.commit();provider(monkeypatch,[1],fail=True)
    with pytest.raises(service.EsignServiceError):cancellation.cancel_and_restart(old.id,user,'test')
    assert old.status=='cancelling' and ReportEsignFlow.query.count()==1
    with pytest.raises(service.EsignServiceError,match='撤销结果'):service.ensure_report_esign_flow(report.report_no,user)
    db.session.rollback();calls=provider(monkeypatch,[3])
    new=cancellation.cancel_and_restart(old.id,user,'test')
    assert new.status=='ready' and len(calls)==1 and ReportEsignFlow.query.count()==2


@pytest.mark.parametrize('sealed',[True,False])
def test_org_round_checks_real_seal_and_retires_personal_source(round_data,monkeypatch,sealed):
    report,version,user,raw,source=round_data
    org=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=2,status='signing',source_sha256=source.signed_sha256,provider_flow_id='fake-org',
        positioning_json=json.dumps({'flowKind':'organization_seal','sourceFlowId':source.id,'organizationSeal':{'included':True}}))
    db.session.add(org);db.session.commit();calls=provider(monkeypatch,[1,3],org=True,seal=sealed)
    if sealed:
        with pytest.raises(service.EsignServiceError,match='组织盖章'):cancellation.cancel_and_restart(org.id,user,'test')
        assert len(calls)==1 and ReportEsignFlow.query.count()==2 and source.status=='completed'
    else:
        new=cancellation.cancel_and_restart(org.id,user,'test')
        assert new.attempt_no==3 and source.status==org.status=='cancelled'
        assert all(s.status=='pending' for s in new.signers) and source.signed_file_id
        assert service.ensure_report_esign_flow(report.report_no,user).id==new.id


@pytest.mark.parametrize('status',['cancelled','cancelling'])
@pytest.mark.parametrize('action',['SIGN_FLOW_COMPLETE','SIGN_MISSION_COMPLETE','GET_SEAL_POSITION'])
def test_late_callbacks_never_restore_retired_flow(round_data,isolated_client,monkeypatch,status,action):
    from app.blueprints import esign
    report,version,user,raw,old=round_data
    old.status=status;db.session.commit()
    monkeypatch.setattr(esign,'verify_callback_signature',lambda *a:True)
    monkeypatch.setattr(esign,'EsignV3Client',lambda:pytest.fail('must not download or issue'))
    body={'signFlowId':old.provider_flow_id,'action':action,'signFlowStatus':2,'signOrder':1,
        'customBizNum':f'REPORT-POS-{old.id}-{old.source_sha256[:12]}'}
    response=isolated_client.post('/api/esign/callback',json=body)
    assert response.status_code==200 and old.status==status


def test_provider_accepted_but_not_stopped_does_not_clear_signatures(round_data,monkeypatch):
    report,version,user,raw,old=round_data
    old.status='signing';db.session.commit();provider(monkeypatch,[1,1])
    with pytest.raises(service.EsignServiceError,match='尚未确认'):cancellation.cancel_and_restart(old.id,user,'test')
    assert old.status=='cancelling' and all(s.status=='signed' for s in old.signers)
    assert ReportEsignFlow.query.count()==1


def test_validation_deployment_blocks_cancel_route(round_data,isolated_client,isolated_app,monkeypatch):
    report,version,user,raw,old=round_data
    monkeypatch.setitem(isolated_app.config,'DEPLOYMENT_ROLE','validation')
    calls=provider(monkeypatch,[])
    response=isolated_client.post(f'/api/esign/flows/{old.id}/cancel',headers=login_headers(isolated_client,user.account),json={'confirmed':True,'reason':'test'})
    assert response.status_code==423 and not calls


def test_not_dispatched_org_task_can_cancel_from_panel(round_data,monkeypatch,isolated_client):
    report,version,user,raw,source=round_data
    org=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=2,status='ready',source_sha256=source.signed_sha256,
        positioning_json=json.dumps({'flowKind':'organization_seal','sourceFlowId':source.id,'organizationSeal':{'included':True}}))
    db.session.add(org);db.session.commit();calls=provider(monkeypatch,[])
    response=isolated_client.get(f'/api/esign/reports/{report.report_no}',headers=login_headers(isolated_client,user.account))
    assert response.json['data']['canCancel'] is True
    new=cancellation.cancel_and_restart(org.id,user,'重新签署')
    assert not calls and new.status=='ready' and source.status==org.status=='cancelled'
