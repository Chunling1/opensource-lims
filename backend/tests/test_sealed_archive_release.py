"""Isolated staged delivery and downloadable artifact authority."""
import json
import pytest
from app.extensions import db
from app.models import ReportEsignFlow, OperationAudit, Permission, user_action_permissions
from app.functions.esign_service import store_signed_file
from app.report_delivery import SEALED, ARCHIVED, RELEASED, SEALED_DOWNLOAD, RELEASE_ACTION, sealed_file_access_error
from app.applications.report_lifecycle import execute_report_action, report_allowed_actions
from app.applications.report_lifecycle.dashboard import report_todo_view
from app.report_delivery_grants import grant_existing_users
from test_preserved_approval_and_seal_confirmation import prepared, signed_source
from testkit.factories import login_headers
pytest_plugins = ('testkit.fixtures',)


def seal(prepared):
    report, version, user, raw = prepared
    flow = signed_source(prepared)
    flow.positioning_json = json.dumps({'organizationSeal': {'included': True}})
    store_signed_file(flow, raw, user)
    db.session.commit()
    return flow


def permissions(user, *codes):
    for code in codes:
        p = db.session.get(Permission, code)
        if not p:
            p = Permission(code=code, name=code, ptype='page'); db.session.add(p)
        user.permissions.append(p)
    db.session.commit()


def test_full_seal_archive_release_and_repeat_guards(prepared, scenario_factory):
    report, version, user, raw = prepared
    user.role_key = 'admin'; db.session.commit()
    assert report.to_row()['dataStatus'] == '报告签发中'
    signed_source(prepared)
    assert report.to_row()['dataStatus'] == '报告盖章中'
    flow = ReportEsignFlow.query.first()
    flow.positioning_json = json.dumps({'organizationSeal': {'included': True}})
    store_signed_file(flow, raw, user); db.session.commit()
    assert report.to_row()['dataStatus'] == SEALED
    assert report.status == '待发放' and not report.archive_state
    assert report_todo_view(user, report) == 'archive'
    assert execute_report_action(user, report.report_no, RELEASE_ACTION).code != 0
    assert execute_report_action(user, report.report_no, 'report.archive.pass').code == 0
    assert report.to_row()['dataStatus'] == ARCHIVED
    assert report_todo_view(user, report) == 'release'
    from app.app_workspace import dashboard_data
    board=dashboard_data(user, {'workbench':'general'})
    assert any(q['id']=='release' for q in board['queues'])
    assert RELEASE_ACTION in report_allowed_actions(user, report)
    assert execute_report_action(user, report.report_no, RELEASE_ACTION).code == 0
    assert report.to_row()['dataStatus'] == RELEASED
    from app.applications.report_lifecycle.query_details import query_details
    assert query_details([report])[report.report_no]['reportReleasedBy'] == user.name
    assert report_todo_view(user, report) is None
    assert execute_report_action(user, report.report_no, RELEASE_ACTION).code != 0
    assert execute_report_action(user, report.report_no, 'report.archive.undo').code != 0
    assert 'report.archive.undo' not in report_allowed_actions(user, report)
    store_signed_file(flow, raw, user); db.session.commit()
    assert report.to_row()['dataStatus'] == RELEASED
    assert OperationAudit.query.filter_by(action='report.seal.completed').count() == 1
    assert OperationAudit.query.filter_by(action=RELEASE_ACTION).count() == 1


def test_new_permissions_are_independent_and_revocable(prepared, scenario_factory, isolated_client):
    report, version, user, raw = prepared
    flow = seal(prepared)
    permissions(user, 'report.query.view', 'report.release.view')
    headers = login_headers(isolated_client, user.account)
    base = f'/api/report-assurance/reports/{report.report_no}/artifact?view=query&signed=1'
    assert isolated_client.get(base+'&file=1&download=1', headers=headers).status_code == 403
    assert isolated_client.get(base, headers=headers).status_code == 403
    for url in [f'/api/esign/flows/{flow.id}/signed-pdf',
                f'/api/report-assurance/reports/{report.report_no}/signing-history/{flow.id}/file?view=query']:
        assert isolated_client.get(url, headers=headers).status_code == 410
    scenario_factory.grant_action(user, SEALED_DOWNLOAD); db.session.commit()
    assert isolated_client.get(base+'&file=1&download=1', headers=headers).status_code == 200
    report.archive_state='归档完成'; db.session.commit()
    assert execute_report_action(user, report.report_no, RELEASE_ACTION).code != 0
    scenario_factory.grant_action(user, RELEASE_ACTION); db.session.commit()
    assert execute_report_action(user, report.report_no, RELEASE_ACTION).code == 0
    db.session.execute(user_action_permissions.delete().where(user_action_permissions.c.user_id==user.id));db.session.commit()
    assert not sealed_file_access_error(user, report)
    # Even self-scoped same-department members get this released artifact only.
    report.owner='another-person';user.data_scope_type='self';db.session.commit()
    assert isolated_client.get(base+'&file=1&download=1', headers=headers).status_code==200
    assert isolated_client.get(f'/api/esign/flows/{flow.id}/signed-pdf',headers=headers).status_code==410
    outsider=scenario_factory.identity_scenario().user
    assert sealed_file_access_error(outsider, report)


def test_old_status_is_not_evidence_of_actual_release(prepared):
    report, version, user, raw = prepared
    report.status='已发放';report.archive_state='归档完成';db.session.commit()
    assert report.to_row()['dataStatus']==ARCHIVED
    assert sealed_file_access_error(user, report)


@pytest.mark.parametrize('paging',[None,False,True])
def test_release_list_retains_completed_records_and_pending_scope(prepared,isolated_app,isolated_client,scenario_factory,paging):
    from app.security import issue_token
    report,version,user,raw=prepared
    flow=seal(prepared)
    permissions(user,'report.release.view')
    report.status='已发放';report.archive_state='归档完成'
    report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id,'sealedFlowId':flow.id}}
    db.session.commit()
    isolated_app.config.update(LIST_PAGE_IDS=bool(paging),LIST_QUERY_A2=True,LIST_QUERY_PROTOTYPE=False)
    headers={'Authorization':'Bearer '+issue_token(user)}
    def read(**filters):
        body={'view':'release',**filters}
        if paging is not None:body.update(serverPage=True,presentation='report',page=1,pageSize=1)
        response=isolated_client.post('/api/reports/query',headers=headers,json=body).get_json()
        assert response['code']==0,response
        return response['data']
    data=read(status=RELEASED)
    assert [r['reportNo'] for r in data['rows']]==[report.report_no]
    assert data['rows'][0]['rowProjection']=='recall'
    assert RELEASE_ACTION not in data['rows'][0]['allowedActions']
    assert read(rowProjection='active')['rows']==[]
    assert [r['reportNo'] for r in read()['rows']]==[report.report_no]
    # An old 已发放 label without a valid current release remains pending.
    report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id+1,'sealedFlowId':flow.id}}
    db.session.commit()
    assert read(status=RELEASED)['rows']==[]
    assert [r['reportNo'] for r in read(rowProjection='active')['rows']]==[report.report_no]
    outsider=scenario_factory.identity_scenario(permission_codes=('report.release.view',)).user
    headers={'Authorization':'Bearer '+issue_token(outsider)}
    assert read()['rows']==[]


def test_stale_or_unsealed_callback_does_not_advance(prepared):
    report, version, user, raw=prepared
    old=signed_source(prepared)
    new=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
        attempt_no=2,status='ready',source_sha256=version.sha256)
    db.session.add(new);db.session.commit()
    old.positioning_json=json.dumps({'organizationSeal':{'included':True}})
    store_signed_file(old,raw,user);db.session.commit()
    assert report.status=='待打印'
    assert execute_report_action(user,report.report_no,'report.archive.pass').code!=0


def test_one_time_all_accounts_grant_does_not_regrant_after_admin_removal(prepared):
    report,version,user,raw=prepared
    changes=grant_existing_users();db.session.commit()
    assert {x.get('action') for x in changes}>={SEALED_DOWNLOAD, RELEASE_ACTION}
    assert {SEALED_DOWNLOAD,RELEASE_ACTION} <= set(user.action_codes())
    assert 'report.release.view' in user.permission_codes()
    db.session.execute(user_action_permissions.delete().where(user_action_permissions.c.user_id==user.id));db.session.commit()
    assert grant_existing_users()==[]
    assert SEALED_DOWNLOAD not in user.action_codes()


def test_catalog_has_explicit_assignable_permissions():
    from app.catalog import assignable_action_permissions, MODULE_IMPLIED_ACTIONS
    actions=dict(assignable_action_permissions())
    assert SEALED_DOWNLOAD in actions and RELEASE_ACTION in actions
    assert SEALED_DOWNLOAD not in MODULE_IMPLIED_ACTIONS and RELEASE_ACTION not in MODULE_IMPLIED_ACTIONS


def test_admin_can_save_and_revoke_both_grants_through_org_api(prepared, scenario_factory, isolated_client):
    report, version, user, raw = prepared
    admin = scenario_factory.identity_scenario().user
    admin.role_key = 'admin'; db.session.commit()
    headers = login_headers(isolated_client, admin.account)
    grant_existing_users(); db.session.commit()
    response = isolated_client.put(f'/api/admin/users/{user.id}', headers=headers,
        json={'actionPermissions': [RELEASE_ACTION]})
    assert response.get_json()['code'] == 0
    assert RELEASE_ACTION in user.action_codes() and SEALED_DOWNLOAD not in user.action_codes()
    assert grant_existing_users() == []
    response = isolated_client.put(f'/api/admin/users/{user.id}', headers=headers,
        json={'actionPermissions': [SEALED_DOWNLOAD]})
    assert response.get_json()['code'] == 0
    assert SEALED_DOWNLOAD in user.action_codes() and RELEASE_ACTION not in user.action_codes()


def test_department_download_index_excludes_unreleased_other_dept_and_stale_version(prepared, scenario_factory, isolated_client):
    report, version, user, raw = prepared
    flow = seal(prepared)
    headers = login_headers(isolated_client, user.account)
    index = '/api/report-assurance/released'
    assert isolated_client.get(index, headers=headers).get_json()['data']['total'] == 0
    report.status='已发放'; report.archive_state='归档完成'
    report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id,'sealedFlowId':flow.id}}
    user.data_scope_type='self'; report.owner='another-user'; db.session.commit()
    data=isolated_client.get(index,headers=headers).get_json()['data']
    assert data['rows']==[{'reportNo':report.report_no,'sampleNo':report.sample_no,'department':report.department}]
    outsider=scenario_factory.identity_scenario().user
    other_headers=login_headers(isolated_client,outsider.account)
    assert isolated_client.get(index,headers=other_headers).get_json()['data']['total']==0
    assert isolated_client.get(f'/api/esign/flows/{flow.id}/signed-pdf',headers=other_headers).status_code==410
    report.approved_document_version_id=version.id+100;db.session.commit()
    assert isolated_client.get(index,headers=headers).get_json()['data']['total']==0
    assert isolated_client.get(f'/api/esign/flows/{flow.id}/signed-pdf',headers=headers).status_code==410


def test_release_rejects_other_department_and_rollback_preserves_archive(prepared, scenario_factory, monkeypatch):
    report,version,user,raw=prepared
    seal(prepared); report.archive_state='归档完成';db.session.commit()
    outsider=scenario_factory.identity_scenario(permission_codes=('report.release.view',)).user
    scenario_factory.grant_action(outsider,RELEASE_ACTION);db.session.commit()
    assert execute_report_action(outsider,report.report_no,RELEASE_ACTION).code!=0
    user.role_key='admin';db.session.commit()
    def failed_commit(): raise RuntimeError('isolated failure')
    monkeypatch.setattr(db.session,'commit',failed_commit)
    with pytest.raises(RuntimeError): execute_report_action(user,report.report_no,RELEASE_ACTION)
    db.session.expire_all()
    assert report.status=='待发放' and report.archive_state=='归档完成'
    assert not (report.detail.get('reportDelivery') or {}).get('released')
    assert OperationAudit.query.filter_by(action=RELEASE_ACTION).count()==0


def test_released_index_paginates_and_escapes_search(prepared, isolated_client):
    report,version,user,raw=prepared
    flow=seal(prepared)
    report.status='已发放'; report.archive_state='归档完成'
    report.detail={**report.detail,'reportDelivery':{'released':True,'versionId':version.id,'sealedFlowId':flow.id}}
    db.session.commit()
    headers=login_headers(isolated_client,user.account)
    assert isolated_client.get('/api/report-assurance/released?page=2',headers=headers).get_json()['data']=={'rows':[],'total':1}
    assert isolated_client.get('/api/report-assurance/released?keyword=%25',headers=headers).get_json()['data']['total']==0


def test_unreleased_archive_can_be_undone_and_date_conflicts_preserved(prepared):
    from datetime import datetime, timedelta
    from app.audit import add_operation_audit
    report,version,user,raw=prepared
    user.role_key='admin';db.session.commit();seal(prepared)
    event=OperationAudit.query.filter_by(action='report.seal.completed').one()
    event.created_at=datetime.utcnow()+timedelta(days=5);db.session.commit()
    assert execute_report_action(user,report.report_no,'report.archive.pass').code!=0
    event.created_at=datetime.utcnow();db.session.commit()
    assert execute_report_action(user,report.report_no,'report.archive.pass').code==0
    assert execute_report_action(user,report.report_no,'report.archive.undo').code==0
    assert report.archive_state=='' and report.status=='待发放'
    assert execute_report_action(user,report.report_no,RELEASE_ACTION).code!=0


def test_cli_grant_dry_run_and_one_time_apply(prepared, isolated_app):
    report,version,user,raw=prepared
    runner=isolated_app.test_cli_runner()
    result=runner.invoke(args=['report-delivery-initialize-grants'])
    assert result.exit_code==0 and 'dryRun' in result.output
    assert SEALED_DOWNLOAD not in user.action_codes()
    result=runner.invoke(args=['report-delivery-initialize-grants','--apply'])
    assert result.exit_code==0 and SEALED_DOWNLOAD in user.action_codes()
    result=runner.invoke(args=['report-delivery-initialize-grants','--apply'])
    assert result.exit_code==0 and '"applied": 0' in result.output


def test_history_pdf_cannot_bypass_sealed_permission(prepared, isolated_client, monkeypatch):
    from types import SimpleNamespace
    from app.blueprints import reports
    report,version,user,raw=prepared
    flow=seal(prepared)
    headers=login_headers(isolated_client,user.account)
    monkeypatch.setattr(reports,'_authorized_correction_history',lambda _id:SimpleNamespace(before_data={'report':{'reportNo':report.report_no}}))
    response=isolated_client.get(f'/api/reports/correction-requests/1/history/signed/{flow.id}/pdf',headers=headers)
    assert response.status_code==410


def test_corrupt_sealed_file_blocks_archive_and_release(prepared):
    report,version,user,raw=prepared
    user.role_key='admin';db.session.commit();flow=seal(prepared)
    flow.signed_sha256='0'*64;db.session.commit()
    assert execute_report_action(user,report.report_no,'report.archive.pass').code!=0
    assert not report.archive_state
    report.archive_state='归档完成';db.session.commit()
    assert execute_report_action(user,report.report_no,RELEASE_ACTION).code!=0
    assert not (report.detail.get('reportDelivery') or {}).get('released')


def test_real_list_and_action_endpoints_follow_archive_then_release(prepared, isolated_client):
    report,version,user,raw=prepared
    user.role_key='admin';db.session.commit();seal(prepared)
    headers=login_headers(isolated_client,user.account)
    def query(view,status='',**filters):
        result=isolated_client.post('/api/reports/query',headers=headers,json={'view':view,'status':status,**filters})
        assert result.get_json()['code']==0, result.get_json()
        return result.get_json()['data']['rows']
    def action(code):
        return isolated_client.post(f'/api/reports/{report.report_no}/action',headers=headers,json={'action':code}).get_json()
    assert [r['reportNo'] for r in query('archive')]==[report.report_no]
    assert not query('release')
    assert action('report.archive.pass')['code']==0
    assert [r['reportNo'] for r in query('release',ARCHIVED)]==[report.report_no]
    assert action(RELEASE_ACTION)['code']==0
    assert not query('release',rowProjection='active')
    assert [r['reportNo'] for r in query('release',RELEASED)]==[report.report_no]
    assert [r['reportNo'] for r in query('query',RELEASED)]==[report.report_no]
