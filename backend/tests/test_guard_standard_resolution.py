from copy import deepcopy
import pytest
from app.extensions import db
from app.models import StdLibraryItem, OperationAudit
from app import compliance
from app.standard_resolution import resolution_choices, resolve_identities
from test_standard_association_preflight import case, replace_registration
pytest_plugins=('testkit.fixtures',)


def test_same_code_id_alignment_is_audited_and_idempotent(case):
    _,user,report=case
    new=replace_registration(report,same_code=True)
    before=deepcopy(report.detail)
    p=compliance.build_compliance_preflight(report,'report_review')
    assert p['ready'] and p['finalSeal']=='CMA + CNAS'
    assert report.detail==before
    body={'preflightVersion':p['preflightVersion'],'finalSeal':p['finalSeal']}
    compliance.validate_and_record_acknowledgement(report,user,'report_review',body)
    assert report.detail['checkInput']['standardRecords'][0]['id']==new.id
    assert report.detail['checkInput']['equipmentIds']==[42]
    assert OperationAudit.query.filter_by(action='report.standard_identity.align').count()==1
    with pytest.raises(ValueError,match='不能重复提交'):
        compliance.validate_and_record_acknowledgement(report,user,'report_review',body)


def test_ambiguous_identity_requires_explicit_choice_and_reason(case):
    _,user,report=case
    old=StdLibraryItem.query.one()
    other=StdLibraryItem(code=old.code,name='English',use_depts=report.department,auth_kind='CNAS')
    db.session.add(other);db.session.flush()
    choices=resolution_choices(report)
    assert {r['id'] for r in choices[0]['candidates']}=={old.id,other.id}
    before=deepcopy(report.detail)
    for values,reason in [({old.code:other.id},''),({old.code:9999},'核对'),({},'核对')]:
        with pytest.raises(ValueError):resolve_identities(report,user,values,reason)
        assert report.detail==before
    resolve_identities(report,user,{old.code:other.id},'按委托明确选择英文版本')
    assert report.detail['rawSample']['standardItemIds']==[other.id]
    p=compliance.build_compliance_preflight(report,'contract_review')
    assert not p['standardChoices'] and p['finalSeal']=='CNAS'
    assert OperationAudit.query.filter_by(action='report.standard_identity.confirm').count()==1


def test_missing_parameter_confirmation_removes_marks_and_notifies(case):
    _,user,report=case
    report.detail={**report.detail,'rawSample':{**report.detail['rawSample'],'capabilityEntryIds':[999999]}}
    p=compliance.build_compliance_preflight(report,'contract_review')
    assert p['ready'] and p['requiresOpinion'] and p['finalSeal']==''
    issue=next(i for i in p['issues'] if i['category']=='capability_not_found')
    assert issue['level']=='confirm'
    body={'preflightVersion':p['preflightVersion'],'finalSeal':'','acknowledgedIssueIds':[issue['id']]}
    with pytest.raises(ValueError,match='确认意见'):
        compliance.validate_and_record_acknowledgement(report,user,'contract_review',body)
    compliance.validate_and_record_acknowledgement(report,user,'contract_review',{**body,'complianceOpinion':'原导入参数记录缺失，按实际参数继续'})
    assert OperationAudit.query.filter_by(action='quality.guard_notice').count()==1
    assert report.detail['rawSample']['seal']==''


def test_resolution_http_requires_current_stage_and_fingerprint(case):
    app,user,report=case
    from app.security import issue_token
    original=StdLibraryItem.query.one()
    db.session.add(StdLibraryItem(code=original.code,name='English',use_depts=report.department))
    db.session.commit()
    client=app.test_client();headers={'Authorization':'Bearer '+issue_token(user)}
    p=compliance.build_compliance_preflight(report,'contract_review')
    body={'stage':'contract_review','preflightVersion':'stale','selections':{original.code:original.id},'reason':'依据原委托'}
    url=f'/api/reports/{report.report_no}/standard-resolution'
    assert client.post(url,headers=headers,json=body).get_json()['code']==1
    assert OperationAudit.query.filter_by(action='report.standard_identity.confirm').count()==0
    body['preflightVersion']=p['preflightVersion']
    result=client.post(url,headers=headers,json=body).get_json()
    assert result['code']==0,result
    report.status='已归档';db.session.commit()
    assert client.post(url,headers=headers,json=body).get_json()['code']==403


def test_bulk_identity_resolution_checks_revision_and_preserves_unrelated_bilingual_ids(case):
    app,user,report=case
    from app.security import issue_token
    original=StdLibraryItem.query.one()
    other=StdLibraryItem(code=original.code,name='English',use_depts=report.department,auth_kind='CNAS')
    a=StdLibraryItem(code='SECOND-2026',name='中文',use_depts=report.department)
    b=StdLibraryItem(code='SECOND-2026',name='English',use_depts=report.department)
    db.session.add_all([other,a,b]);db.session.flush()
    report.detail={**report.detail,'rawSample':{**report.detail['rawSample'],
        'testBases':[original.code,a.code],'standardItemIds':[99999,a.id,b.id]}}
    user.role_key='admin';db.session.commit()
    client=app.test_client();headers={'Authorization':'Bearer '+issue_token(user)}
    url=f'/api/quality/std-library/{original.id}'
    impact=client.get(url+'/identity-impact',headers=headers).get_json()
    assert impact['code']==0 and impact['data']['total']==1,impact
    item=impact['data']['rows'][0]
    assert [c['code'] for c in item['choices']]==[original.code]
    body={'reports':[{'reportNo':report.report_no,'revision':'stale','selections':{original.code:original.id}}],'reason':'按原委托确认'}
    assert client.post(url+'/resolve-report-identities',headers=headers,json=body).get_json()['code']==1
    body['reports'][0]['revision']=item['revision']
    result=client.post(url+'/resolve-report-identities',headers=headers,json=body).get_json()
    assert result['code']==0,result
    assert set(report.detail['rawSample']['standardItemIds'])=={original.id,a.id,b.id}


def test_bad_equipment_is_never_acknowledgeable_and_keeps_seals(case,monkeypatch):
    _,user,report=case
    monkeypatch.setattr(compliance,'compute_report_checks',lambda r:([{'group':'仪器有效性校验','status':'不通过','items':[['仪器','缺日期']]}],True,'缺日期'))
    p=compliance.build_compliance_preflight(report,'report_review')
    issue=next(i for i in p['issues'] if i['category']=='instrument_validity')
    assert issue['level']=='block' and not issue['acknowledgeable'] and not p['ready']
    assert p['finalSeal']=='CMA + CNAS'
