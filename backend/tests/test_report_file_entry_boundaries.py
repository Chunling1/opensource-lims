"""File entry matrix; isolated DB and distinguishable unsigned/signed bytes."""
import json
import pytest
from app.extensions import db
from app.models import ReportEsignFlow, user_action_permissions
from app.functions.esign_service import store_signed_file
from app.report_delivery import SEALED_DOWNLOAD
from test_preserved_approval_and_seal_confirmation import prepared, signed_source
from test_sealed_archive_release import permissions
from testkit.factories import login_headers
pytest_plugins = ('testkit.fixtures',)

@pytest.fixture
def files(prepared):
    report, version, user, original = prepared
    flow = signed_source(prepared)
    flow.positioning_json = json.dumps({'organizationSeal': {'included': True}})
    signed = original + b'\n% isolated signed and sealed bytes\n'
    store_signed_file(flow, signed, user)
    db.session.commit()
    return report, version, user, original, signed, flow

def request_file(client, user, report, view, suffix=''):
    return client.get(f'/api/report-assurance/reports/{report.report_no}/artifact?view={view}'+suffix,
                      headers=login_headers(client, user.account))

@pytest.mark.parametrize('view', ['query','release','print'])
def test_explicit_entry_returns_signed_only_with_authority(files, isolated_client, view):
    report,version,user,original,signed,flow=files
    user.role_key='admin'
    if view=='release':report.archive_state='归档完成'
    db.session.commit()
    result=request_file(isolated_client,user,report,view,'&signed=1&file=1&download=1')
    assert result.status_code==200, result.get_json()
    assert result.data==signed and result.data!=original
    assert result.headers['Content-Disposition'].startswith('attachment')
    assert request_file(isolated_client,user,report,view,'&signed=1&file=1').status_code==403

@pytest.mark.parametrize('view', ['query','release','print','archive'])
def test_generic_file_never_prefers_existing_signed_pdf(files, isolated_client, view):
    report,version,user,original,signed,flow=files
    user.role_key='admin'
    if view=='release':report.archive_state='归档完成'
    db.session.commit()
    for suffix in ['&file=1','&file=1&download=1']:
        result=request_file(isolated_client,user,report,view,suffix)
        assert result.status_code==200, result.get_json()
        assert result.data==original and result.data!=signed

@pytest.mark.parametrize('view', ['archive','review','approval','data_entry','signing',''])
def test_other_contexts_cannot_request_signed_even_admin(files, isolated_client, view):
    report,version,user,original,signed,flow=files
    user.role_key='admin';db.session.commit()
    assert request_file(isolated_client,user,report,view,'&signed=1&file=1&download=1').status_code==403

def test_released_department_exception_excludes_issuance(files, scenario_factory, isolated_client):
    report,version,user,original,signed,flow=files
    permissions(user,'report.query.view','report.release.view','report.print.view')
    report.status='已发放';report.archive_state='归档完成'
    report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id,'sealedFlowId':flow.id}}
    user.data_scope_type='self';report.owner='another-person';db.session.commit()
    for view in ['query','release']:
        assert request_file(isolated_client,user,report,view,'&signed=1&file=1&download=1').data==signed
    assert request_file(isolated_client,user,report,'print','&signed=1&file=1&download=1').status_code==403
    outsider=scenario_factory.identity_scenario(permission_codes=('report.query.view',)).user
    assert request_file(isolated_client,outsider,report,'query','&signed=1&file=1&download=1').status_code==403

def test_revocation_blocks_pending_signed_not_original(files, scenario_factory, isolated_client):
    report,version,user,original,signed,flow=files
    permissions(user,'report.query.view')
    scenario_factory.grant_action(user,SEALED_DOWNLOAD)
    scenario_factory.grant_action(user,'report.pdf.preview')
    scenario_factory.grant_action(user,'report.pdf.download');db.session.commit()
    assert request_file(isolated_client,user,report,'query','&signed=1&file=1&download=1').data==signed
    db.session.execute(user_action_permissions.delete().where(user_action_permissions.c.user_id==user.id).where(user_action_permissions.c.action_code==SEALED_DOWNLOAD));db.session.commit()
    assert request_file(isolated_client,user,report,'query','&signed=1&file=1&download=1').status_code==403
    assert request_file(isolated_client,user,report,'query','&file=1').data==original
    assert request_file(isolated_client,user,report,'query','&file=1&download=1').data==original

@pytest.mark.parametrize('failure', ['corrupt','missing','new_attempt','version'])
def test_invalid_signed_file_never_falls_back_to_original(files, isolated_client, failure):
    report,version,user,original,signed,flow=files
    user.role_key='admin'
    if failure=='corrupt':flow.signed_sha256='0'*64
    elif failure=='missing':flow.signed_file=None
    elif failure=='version':report.approved_document_version_id=version.id+100
    else:db.session.add(ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,attempt_no=2,status='ready',source_sha256=version.sha256))
    db.session.commit()
    result=request_file(isolated_client,user,report,'query','&signed=1&file=1&download=1')
    assert result.status_code==409
    assert result.data!=original

@pytest.mark.parametrize('released', [False, True])
def test_issuance_requires_download_action_even_after_department_release(files, scenario_factory, isolated_client, released):
    report,version,user,original,signed,flow=files
    permissions(user,'report.print.view')
    if released:
        report.status='已发放';report.archive_state='归档完成'
        report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id,'sealedFlowId':flow.id}}
    db.session.commit()
    endpoint='&signed=1&file=1&download=1'
    assert request_file(isolated_client,user,report,'print',endpoint).status_code==403
    scenario_factory.grant_action(user,SEALED_DOWNLOAD);db.session.commit()
    result=request_file(isolated_client,user,report,'print',endpoint)
    assert result.status_code==200, result.get_json()
    assert result.data==signed
    db.session.execute(user_action_permissions.delete().where(user_action_permissions.c.user_id==user.id));db.session.commit()
    assert request_file(isolated_client,user,report,'print',endpoint).status_code==403
