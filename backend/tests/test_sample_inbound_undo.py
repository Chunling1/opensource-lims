"""Receipt cancellation enforces the live state, scope, transaction and audit."""
from copy import deepcopy
import pytest
from app.extensions import db
from app.models import OperationAudit
from app.security import issue_token
from test_inbound_business_date import case, receive

pytest_plugins = ('testkit.fixtures',)


def undo(case, user=None):
    client, actor, report, _ = case
    return client.post(f'/api/samples/{report.report_no}/inbound-undo', json={},
        headers={'Authorization': 'Bearer ' + issue_token(user or actor)}).get_json()


def stocked(case):
    assert receive(case, {'inboundDate':'2026-10-15'})['code'] == 0
    return case[2]


def test_undo_preserves_history_and_allows_new_receipt(case):
    r = stocked(case)
    before = deepcopy(r.detail)
    assert undo(case)['code'] == 0
    db.session.expire_all()
    assert (r.status, r.sample_status) == ('待样品入库', '待入库')
    assert 'sampleInboundAt' not in r.detail['workflowDates']
    assert 'sampleAvailableAt' not in r.detail['workflowDates']
    assert r.detail['rawSample'] == before['rawSample']
    assert OperationAudit.query.filter_by(action='sample.inbound.confirm',object_id=r.report_no).count() == 1
    event = OperationAudit.query.filter_by(action='sample.inbound.undo',object_id=r.report_no).one()
    assert event.account == case[1].account and event.success
    assert event.before_data['workflowDates']['sampleInboundAt']=='2026-10-15'
    assert 'sampleInboundAt' not in event.after_data['workflowDates']
    assert undo(case)['code'] != 0
    assert OperationAudit.query.filter_by(action='sample.inbound.undo',object_id=r.report_no).count() == 1
    assert receive(case, {'inboundDate':'2026-10-16'})['code'] == 0
    assert r.detail['workflowDates']['sampleInboundAt'] == '2026-10-16'


@pytest.mark.parametrize('status,sample', [('待样品入库','待入库'),('检测录入中','已领取'),
    ('待审核','已领取'),('待打印','已入库'),('待样品领取','已处置'),('委托更改中','已入库')])
def test_other_states_cannot_be_cancelled(case, status, sample):
    r = stocked(case); r.status=status; r.sample_status=sample; db.session.commit()
    before=deepcopy(r.detail)
    assert undo(case)['code'] != 0
    db.session.expire_all()
    assert (r.status,r.sample_status,r.detail)==(status,sample,before)
    assert OperationAudit.query.filter_by(action='sample.inbound.undo').count()==0


def test_voided_sample_rejected(case):
    r=stocked(case);r.voided=True;db.session.commit()
    assert undo(case)['code'] != 0
    assert r.sample_status=='已入库'


@pytest.mark.parametrize('allowed_action', [False,True])
def test_scope_and_action_are_enforced(case, scenario_factory, allowed_action):
    r=stocked(case)
    other=scenario_factory.identity_scenario(permission_codes=('sample.inbound.view',),granted_step_codes=('sample_inbound',))
    if allowed_action: scenario_factory.grant_action(other.user,'sample.inbound.confirm')
    db.session.commit()
    assert undo(case,other.user)['code'] != 0
    assert r.sample_status=='已入库'


def test_project_step_is_required(case, monkeypatch):
    r=stocked(case)
    from app.applications.sample_logistics import commands
    monkeypatch.setattr(commands,'project_step_error',lambda *a:'无项目步骤权限')
    assert undo(case)['code']==403
    assert r.sample_status=='已入库'


def test_audit_failure_rolls_back_state_and_dates(case, monkeypatch):
    r=stocked(case);before=deepcopy(r.detail)
    from app.applications.sample_logistics import commands
    def fail(*a,**kw): raise RuntimeError('audit unavailable')
    monkeypatch.setattr(commands,'add_operation_audit',fail)
    with pytest.raises(RuntimeError,match='audit unavailable'):
        commands.execute_sample_inbound_undo(case[1],r.report_no)
    db.session.expire_all()
    assert (r.status,r.sample_status,r.detail)==('待样品领取','已入库',before)


def test_old_outbound_return_plan_cannot_skip_receipt_after_undo(case):
    r=stocked(case);r.detail={**r.detail,'returnPlan':{'sourceAction':'sample.out_warehouse.return',
        'afterContractReview':'sample_outbound','preservedSampleStatus':'已入库'}};db.session.commit()
    assert undo(case)['code']==0
    from app.applications.report_lifecycle import resumes_sample_outbound
    assert not resumes_sample_outbound(r.detail)
    assert r.detail['returnPlan']['preservedSampleStatus']=='待入库'


@pytest.mark.parametrize('paged', [False,True])
def test_inbound_list_exposes_undo_only_while_waiting_for_pickup(case, isolated_app, paged):
    isolated_app.config['LIST_PAGE_IDS']=True
    isolated_app.config['LIST_QUERY_A2']=True
    r=stocked(case);client,user,_,_=case
    def rows():
        result=client.post('/api/samples/query',json={'view':'inbound','serverPage':paged,'page':1,'pageSize':10,'presentation':'inbound'},headers={'Authorization':'Bearer '+issue_token(user)}).get_json()
        assert result['code']==0,result
        data=result['data'];return data['rows'] if isinstance(data,dict) else data
    assert next(x for x in rows() if x['reportNo']==r.report_no)['canUndoSampleInbound'] is True
    assert undo(case)['code']==0
    assert next(x for x in rows() if x['reportNo']==r.report_no)['canUndoSampleInbound'] is False
