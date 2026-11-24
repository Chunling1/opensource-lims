"""Registration and testing snapshots must not remove marks through mixed IDs."""
from copy import deepcopy
import pytest
from app import compliance
from app.extensions import db
from app.models import StdLibraryItem, CapabilityImportBatch, ComplianceAcknowledgement
from app.report_scope import assess_scope
from app.sample_form_merge import merge_sample_form
from test_compliance_review_round import case
pytest_plugins = ('testkit.fixtures',)


def replace_registration(report, *, same_code=False):
    original = StdLibraryItem.query.one()
    new = StdLibraryItem(code=original.code if same_code else 'NEW-STANDARD-2026',
        name='New English standard', use_depts=report.department, auth_kind='CNAS+CMA+一单一库')
    db.session.add(new); db.session.flush()
    d=deepcopy(report.detail)
    d['rawSample'].update(standardItemIds=[new.id], testBases=[new.code], testBasis=new.code)
    d['checkInput'].update(standards=[original.code], standardRecords=[{'id':original.id,'code':original.code}], equipmentIds=[42])
    d['attachmentEvidence']=['keep']
    report.detail=d; db.session.commit()
    return new


@pytest.mark.parametrize('same_code',[False,True])
def test_review_registration_uses_its_own_ids_and_preserves_testing(case,same_code):
    _,user,report=case
    new=replace_registration(report,same_code=same_code);before=deepcopy(report.detail)
    result=compliance.build_compliance_preflight(report,'contract_review')
    assert result['ready'] and not result['issues']
    assert result['finalSeal']=='CMA + CNAS'
    assert result['standardCoverage'][0]['result']['standardId']==new.id
    assert assess_scope(report)['state']=='in_scope'
    compliance.validate_and_record_acknowledgement(report,user,'contract_review',
        {'preflightVersion':result['preflightVersion'],'finalSeal':result['finalSeal']})
    assert report.detail['checkInput']['standards']==before['checkInput']['standards']
    assert report.detail['checkInput']['equipmentIds']==[42]
    assert report.detail['attachmentEvidence']==['keep']


@pytest.mark.parametrize('stage',['report_review','report_approval'])
@pytest.mark.parametrize('same_code',[False])
def test_later_stage_blocks_stale_testing_and_keeps_requested_marks(case,stage,same_code):
    _,user,report=case
    replace_registration(report,same_code=same_code);before=deepcopy(report.detail)
    result=compliance.build_compliance_preflight(report,stage)
    assert not result['ready'] and result['finalSeal']=='CMA + CNAS'
    assert any(x['category']=='standard_selection_mismatch' for x in result['hardBlockers'])
    with pytest.raises(ValueError,match='不能确认绕过'):
        compliance.validate_and_record_acknowledgement(report,user,stage,
            {'preflightVersion':result['preflightVersion'],'finalSeal':result['finalSeal'],
             'acknowledgedIssueIds':[x['id'] for x in result['issues']],'complianceOpinion':'不能绕过'})
    assert report.detail==before and ComplianceAcknowledgement.query.count()==0


@pytest.mark.parametrize('problem',['ambiguous','missing','invalid','mismatch'])
@pytest.mark.parametrize('stage',['contract_review','report_review','report_approval'])
def test_identity_failure_is_never_a_seal_downgrade(case,problem,stage):
    _,user,report=case
    original=StdLibraryItem.query.one();d=deepcopy(report.detail)
    if problem=='ambiguous':
        db.session.add(StdLibraryItem(code=original.code,name='English',use_depts=report.department))
    else:
        d['rawSample']['standardItemIds']={'missing':[99999],'invalid':['bad'],'mismatch':[original.id]}[problem]
        if problem=='mismatch':d['rawSample']['testBases']=['WRONG-2026']
    report.detail=d;db.session.commit();before=deepcopy(report.detail)
    result=compliance.build_compliance_preflight(report,stage)
    assert not result['ready'] and result['finalSeal']=='CMA + CNAS'
    assert any(x['category']=='standard_identity_unresolved' for x in result['hardBlockers'])
    scope=assess_scope(report)
    assert scope['state']=='needs_review' and not scope['outOfScope']
    with pytest.raises(ValueError,match='不能确认绕过'):
        compliance.validate_and_record_acknowledgement(report,user,stage,
            {'preflightVersion':result['preflightVersion'],'finalSeal':result['finalSeal']})
    assert report.detail==before and ComplianceAcknowledgement.query.count()==0


def test_identity_block_applies_without_active_parameter_batch(case):
    _,user,report=case
    CapabilityImportBatch.query.update({'status':'inactive'})
    report.detail={**report.detail,'rawSample':{**report.detail['rawSample'],'standardItemIds':[99999]}}
    db.session.commit()
    result=compliance.build_compliance_preflight(report,'contract_review')
    assert result['required'] and not result['ready']
    with pytest.raises(ValueError):
        compliance.validate_and_record_acknowledgement(report,user,'contract_review',
            {'preflightVersion':result['preflightVersion'],'finalSeal':'CMA + CNAS'})


def test_confirmed_absence_of_cma_keeps_existing_authorization_rule(case):
    _,_,report=case
    item=StdLibraryItem.query.one();item.auth_kind='CNAS';db.session.commit()
    result=compliance.build_compliance_preflight(report,'contract_review')
    assert result['ready'] and result['finalSeal']=='CNAS'
    assert result['issues'] and not result['hardBlockers']


def test_changing_only_standard_id_requires_testing_review():
    before={'rawSample':{'testBases':['EN 442-1:2014'],'standardItemIds':[1]},
            'checkInput':{'standards':['EN 442-1:2014'],'equipmentIds':[42]}}
    out=merge_sample_form(before,{'rawSample':{'standardItemIds':[2]}})
    assert 'standardItemIds' in out['testDataReviewRequired']['fields']
    assert out['checkInput']==before['checkInput']


def test_legacy_unique_and_explicit_bilingual_records_still_pass(case):
    _,_,report=case
    original=StdLibraryItem.query.one()
    assert compliance.build_compliance_preflight(report,'contract_review')['ready']
    other=StdLibraryItem(code=original.code,name='English',use_depts=report.department,auth_kind=original.auth_kind)
    db.session.add(other);db.session.flush()
    report.detail={**report.detail,'rawSample':{**report.detail['rawSample'],'standardItemIds':[original.id,other.id]}}
    db.session.commit()
    result=compliance.build_compliance_preflight(report,'contract_review')
    assert result['ready'] and result['finalSeal']=='CMA + CNAS'
    assert len(result['standardCoverage'])==2


def test_real_contract_review_submission_uses_registration_pair(case,monkeypatch):
    import inspect
    from flask import g
    from app.blueprints import reports
    from app import workflow_hooks as hooks
    app,user,report=case
    new=replace_registration(report);before=deepcopy(report.detail)
    original=reports._sample_configuration
    seen=[]
    def configuration(standard,department,seal,scheme,**kwargs):
        seen.append((standard,kwargs.get('standard_item_ids')))
        assert standard==new.code and kwargs['standard_item_ids']==[new.id]
        # Real standard verdict is already checked by the real compliance handler;
        # project configuration here is unrelated to the association regression.
        return {'ready':True}
    monkeypatch.setattr(reports,'_sample_configuration',configuration)
    monkeypatch.setattr(reports,'_apply_report_prefix_change',lambda *a:None)
    monkeypatch.setattr(hooks,'blocker',lambda *a:None)
    monkeypatch.setattr(hooks,'capture',lambda *a:None)
    result=compliance.build_compliance_preflight(report,'contract_review')
    body={'action':'pass','cma':True,'cnas':True,'items':{k:True for k,_ in reports.CR_ITEMS},
          'preflightVersion':result['preflightVersion'],'finalSeal':result['finalSeal']}
    with app.test_request_context(json=body):
        g.current_user=user
        response=inspect.unwrap(reports.contract_review)(report.report_no)
        data=(response[0] if isinstance(response,tuple) else response).get_json()
    assert data['code']==0,data
    assert seen and report.detail['checkInput']['standards']==before['checkInput']['standards']
    assert report.detail['rawSample']['seal']=='CMA + CNAS'
