import copy
import json
import pytest

from app.extensions import db
from app.models import ReportEsignFlow, ReportEsignSigner, EsignIdentityBinding
from app.functions import esign_service as service, esign_unified as unified, esign_cancellation as cancellation
from app.esign_seal_confirmation import assign
from test_preserved_approval_and_seal_confirmation import prepared
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)
real_organization = unified._organization


@pytest.fixture(params=[False, True], ids=["library", "manual"])
def setup(prepared, monkeypatch, isolated_app, request):
    report, version, user, raw = prepared
    if request.param:
        report.detail = {**report.detail, "rawSample": {"manualCapabilityItems": ["虚拟库外参数"], "manualCapabilityReason": ""}}
    user.role_key = 'admin'
    assign(user, True)
    db.session.add(EsignIdentityBinding(user_id=user.id, legal_name=user.name,
        psn_account='13800000000', status='verified'))
    flow = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
        report_document_version_id=version.id, attempt_no=1, status='signing',
        provider_flow_id='single-flow', provider_file_id='original-file', source_sha256=version.sha256,
        positioning_json=json.dumps({'flowKind': 'person_signing', 'signingMode': unified.MODE,
            'organizationSeal': {'included': False, 'status': 'awaiting_personal_signatures', 'confirmationRequired': True}}))
    db.session.add(flow); db.session.flush()
    for order, role in enumerate(('chief', 'reviewer', 'approver'), 1):
        flow.signers.append(ReportEsignSigner(user_id=user.id, role_code=role, role_name=role,
            legal_name_snapshot=user.name, sign_order=order, status='pending'))
    db.session.commit()
    monkeypatch.setitem(isolated_app.config, 'ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED', True)
    monkeypatch.setitem(isolated_app.config, 'DEPLOYMENT_ROLE', 'standard')

    class Provider:
        def __init__(self):
            self.calls = []
            self.timeout_append = False
            self.timeout_finish = False
            self.detail = {'signFlowStatus': 1, 'signers': [
                {'signerType': 0, 'signOrder': s.sign_order, 'signFields': [{'customBizNum': f'{report.report_no}-{s.role_code.upper()}',
                    'fileId': flow.provider_file_id, 'signFieldStatus': 4}]} for s in flow.signers]}
        def request(self, method, path, payload=None):
            self.calls.append((method, path, payload))
            if method == 'GET': return copy.deepcopy(self.detail)
            if path.endswith('/signers/sign-fields'):
                org = copy.deepcopy(payload['signers'][0])
                for field in org['signFields']: field['signFieldStatus'] = 0
                self.detail['signers'].append(org)
                if self.timeout_append: raise service.EsignServiceError('provider_unavailable', 'timeout')
            elif path.endswith('/finish'):
                self.detail['signFlowStatus'] = 2
                if self.timeout_finish: raise service.EsignServiceError('provider_unavailable', 'timeout')
            elif path.endswith('/revoke'): self.detail['signFlowStatus'] = 3
            else: pytest.fail(path)
            return {}
        def download_signed_pdf(self, provider_id):
            assert self.detail['signFlowStatus'] == 2
            self.calls.append(('download', provider_id, None))
            return raw
        def seal(self):
            for s in self.detail['signers']:
                if s['signerType'] == 1:
                    for f in s['signFields']: f['signFieldStatus'] = 4
    provider = Provider()
    monkeypatch.setattr(unified, '_client', lambda: provider)
    monkeypatch.setattr(cancellation, 'EsignV3Client', lambda: provider)
    # Geometry has its own PDF regression suite; use the real organization payload builder here.
    monkeypatch.setattr(unified, '_organization', lambda f,c,s: service._organization_signer(f.provider_file_id, f.report_no,
        {'cover': {'positionPage': '2','positionX': 100,'positionY': 100},
         'titleCover': {'positionPage': '1','positionX': 100,'positionY': 100}}, force=True, sign_order=4))
    return report, version, user, flow, provider


def confirm(data):
    report, version, user, flow, provider = data
    return unified.confirm(flow.id, user, flow.source_sha256, report.report_no)


def test_all_people_done_stays_open_no_seal_or_download(setup, isolated_client):
    report, version, user, flow, provider = setup
    unified.refresh(flow.id)
    assert flow.status == 'signing' and not flow.signed_file_id
    assert all(s.status == 'signed' for s in flow.signers)
    assert flow.to_dict()['organizationSeal']['status'] == 'awaiting_confirmation'
    assert all(c[0] == 'GET' for c in provider.calls)
    assert not cancellation.cancellation_error(user, flow)
    assert service.issuance_blocker(report)
    assert isolated_client.get(f'/api/esign/flows/{flow.id}/signed-pdf', headers=login_headers(isolated_client,user.account)).status_code == 410


def test_confirmation_appends_once_same_flow_and_finish_after_all_seals(setup):
    report, version, user, flow, provider = setup
    confirm(setup); confirm(setup)
    posts = [c for c in provider.calls if c[0] == 'POST']
    assert len(posts) == 1 and posts[0][1] == '/v3/sign-flow/single-flow/signers/sign-fields'
    assert posts[0][2]['signers'][0]['signConfig']['signOrder'] == 4
    assert ReportEsignFlow.query.count() == 1 and flow.provider_file_id == 'original-file'
    assert not flow.signed_file_id and flow.status == 'signing'
    provider.detail['signers'][-1]['signFields'][0]['signFieldStatus'] = 4
    unified.refresh(flow.id)
    assert not flow.signed_file_id and flow.status == 'signing'
    provider.seal(); unified.refresh(flow.id); unified.refresh(flow.id)
    assert flow.status == 'completed' and flow.signed_file_id
    assert flow.to_dict()['organizationSeal']['status'] == 'completed'
    assert len([c for c in provider.calls if c[1].endswith('/finish')]) == 1
    assert len([c for c in provider.calls if c[0] == 'download']) == 1
    assert service.issuance_blocker(report) is None


@pytest.mark.parametrize('case', ['no_permission','wrong_hash','wrong_report','pending_person','cancelling'])
def test_invalid_confirmation_never_appends(setup, case):
    report, version, user, flow, provider = setup
    sha, no = flow.source_sha256, report.report_no
    if case == 'no_permission': assign(user,False)
    if case == 'wrong_hash': sha = 'wrong'
    if case == 'wrong_report': no = 'OTHER'
    if case == 'pending_person': provider.detail['signers'][-1]['signFields'][0]['signFieldStatus'] = 0
    if case == 'cancelling': flow.status = 'cancelling'
    db.session.commit()
    with pytest.raises(service.EsignServiceError): unified.confirm(flow.id,user,sha,no)
    assert not [c for c in provider.calls if c[0] == 'POST']


def test_timeout_append_reconciles_without_duplicate(setup):
    report, version, user, flow, provider = setup
    provider.timeout_append = True
    with pytest.raises(service.EsignServiceError): confirm(setup)
    assert not cancellation.cancellation_error(user, flow)
    confirm(setup)
    assert len([c for c in provider.calls if c[0] == 'POST']) == 1
    provider.seal(); provider.timeout_finish = True
    with pytest.raises(service.EsignServiceError): unified.refresh(flow.id)
    db.session.rollback()
    unified.refresh(flow.id)
    assert flow.status == 'completed'
    assert len([c for c in provider.calls if c[1].endswith('/finish')]) == 1


@pytest.mark.parametrize('all_signed',[False, True])
def test_admin_revokes_open_provider_and_restarts_without_approval(setup, all_signed):
    report, version, user, flow, provider = setup
    if not all_signed: provider.detail['signers'][-1]['signFields'][0]['signFieldStatus'] = 0
    unified.refresh(flow.id)
    new = cancellation.cancel_and_restart(flow.id,user,'报告更正')
    assert provider.detail['signFlowStatus'] == 3 and flow.status == 'cancelled'
    assert new.id != flow.id and all(s.status == 'pending' for s in new.signers)
    assert report.approved_document_version_id == version.id and report.status == '待打印'
    assert any(c[1].endswith('/revoke') for c in provider.calls)


def test_sealed_upstream_cannot_revoke_even_before_finish(setup):
    report, version, user, flow, provider = setup
    confirm(setup); provider.seal()
    with pytest.raises(service.EsignServiceError,match='盖章'): cancellation.cancel_and_restart(flow.id,user,'修改')
    assert ReportEsignFlow.query.count() == 1
    assert not any(c[1].endswith('/revoke') for c in provider.calls)
    assert flow.status == 'signing'
    unified.refresh(flow.id)
    assert flow.status == 'completed' and flow.signed_file_id


def test_unexpected_personal_completion_cannot_be_called_revocation(setup):
    report, version, user, flow, provider = setup
    provider.detail['signFlowStatus'] = 2
    with pytest.raises(service.EsignServiceError,match='证据'): unified.refresh(flow.id)
    db.session.rollback()
    with pytest.raises(service.EsignServiceError,match='完结'): cancellation.cancel_and_restart(flow.id,user,'修改')
    assert ReportEsignFlow.query.count() == 1 and not flow.signed_file_id


def test_callback_waits_then_finalizes_confirmed_flow(setup, isolated_client, monkeypatch):
    report, version, user, flow, provider = setup
    monkeypatch.setattr('app.blueprints.esign.verify_callback_signature', lambda *a: True)
    monkeypatch.setattr('app.blueprints.esign.send_initial_sms_notifications', lambda *a,**k: None)
    payload={'action':'SIGN_MISSON_COMPLETE','signFlowId':flow.provider_flow_id,'signOrder':3,'signResult':2}
    assert isolated_client.post('/api/esign/callback',json=payload).status_code == 200
    assert flow.status == 'signing' and flow.to_dict()['organizationSeal']['status'] == 'awaiting_confirmation'
    confirm(setup); provider.seal(); payload['signOrder']=4
    assert isolated_client.post('/api/esign/callback',json=payload).status_code == 200
    assert flow.status == 'completed'


def test_calibration_seals_stay_on_original_file_and_verify_source(setup):
    report, version, user, flow, provider = setup
    pos={'positionPage':'1','positionX':100,'positionY':100}
    snapshot={'layoutKind':'calibration','positions':{'cover':pos,'titleCover':pos}}
    org=real_organization(flow,provider,snapshot)
    assert len(org['signFields']) == 2
    assert all(f['fileId']=='original-file' for f in org['signFields'])
    version.pdf_data=b'changed source';db.session.commit()
    with pytest.raises(service.EsignServiceError): real_organization(flow,provider,snapshot)


def test_unknown_append_can_be_revoked_without_resetting_until_provider_stops(setup):
    report, version, user, flow, provider = setup
    provider.timeout_append=True
    with pytest.raises(service.EsignServiceError):confirm(setup)
    new=cancellation.cancel_and_restart(flow.id,user,'修改')
    assert provider.detail['signFlowStatus']==3 and new.status=='ready'
    with pytest.raises(service.EsignServiceError):confirm(setup)
    assert len([c for c in provider.calls if c[1].endswith('/signers/sign-fields')])==1
