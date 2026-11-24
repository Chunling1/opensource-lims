"""Re-review rejection must preserve the original work and sample destination."""
import inspect
import pytest
from flask import g
from app.extensions import db
from app.audit import add_operation_audit
from app.applications.report_lifecycle.commands import apply_return_plan, apply_sample_outbound_return_transition
from test_sample_outbound_return_resume import workflow, case

pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('source,mode,expected', [
 ('first','',('待样品入库','待入库')),
 ('outbound','',('待样品领取','已入库')),
 ('testing.data_entry.return','',('检测录入中','已领取')),
 ('report.review.return','entrust_only',('待审核','已领取')),
 ('report.approval.return','entrust_only',('待审核','已领取')),
 ('report.review.return','entrust_and_data',('检测更改中','已领取')),
 ('report.approval.return','entrust_and_data',('检测更改中','已领取')),
])
@pytest.mark.parametrize('rejections',[0,1,2])
def test_resume_destination_after_re_review(workflow, case, scenario_factory, source, mode, expected, rejections):
 app, _, _ = case
 user, report, resubmit, review = workflow
 scenario_factory.grant_action(user,'report.contract_review.return')
 dates={'sampleInboundAt':'2026-10-20','samplePickupAt':'2026-10-20'}
 report.detail={**report.detail,'workflowDates':dates}
 report.sample_pickup={'signed':True,'receiverName':'虚拟领取人'}
 if source != 'first':
  report.status,report.sample_status='检测录入中','已领取'
  if source=='outbound':
   apply_sample_outbound_return_transition(report,note='虚拟更改',actor_account=user.account,actor_name=user.name,occurred_on='2026-10-22')
  else:
   apply_return_plan(report,user,source,'虚拟更改',mode)
  add_operation_audit(source if source!='outbound' else 'sample.out_warehouse.return','report',report.report_no,actor=user)
  db.session.commit()
  resubmit()
  if source not in ('first','outbound'):
   assert report.sample_status=='已领取'
 original_plan=dict((report.detail or {}).get('returnPlan') or {})
 for _ in range(rejections):
  from app.blueprints import reports
  with app.test_request_context(json={'action':'return','opinion':'虚拟再次退回'}):
   g.current_user=user
   response=inspect.unwrap(reports.contract_review)(report.report_no)
   result=(response[0] if isinstance(response,tuple) else response).get_json()
   assert result['code']==0,result
  db.session.refresh(report)
  plan=report.detail['returnPlan']
  if source not in ('first','outbound'):
   for key in ('mode','afterContractReview','afterDataChange','skipSampleFlow','preservedSampleStatus','targetLabel'):
    assert plan.get(key)==original_plan.get(key)
   assert plan['sourceAction']=='report.contract_review.return'
   assert report.detail['returnInfo']['note']=='虚拟再次退回'
  resubmit()
  if source not in ('first','outbound'):
   assert report.sample_status=='已领取'
 review()
 actual=(report.status,report.sample_status)
 print('MATRIX',source,mode,'rejections='+str(rejections),'expected='+str(expected),'actual='+str(actual),flush=True)
 assert actual==expected
 assert report.detail['workflowDates']==dates
 assert report.sample_pickup['signed'] is (source!='outbound')

@pytest.mark.parametrize('destination,mode,expected',[
 ('data_entry','entrust_only','检测录入中'),
 ('review','entrust_only','待审核'),
 ('data_change','entrust_and_data','检测更改中'),
])
def test_pre_fix_review_sample_label_does_not_replace_preserved_state(workflow,destination,mode,expected):
 user,report,resubmit,review=workflow
 report.status,report.sample_status='待合同评审','待合同评审'
 report.sample_pickup={'signed':True}
 report.detail={**report.detail,'returnPlan':{'mode':mode,'afterContractReview':destination,
   'afterDataChange':'review','preservedSampleStatus':'已领取','targetLabel':'虚拟原去向'}}
 apply_return_plan(report,user,'report.contract_review.return','再次退回')
 db.session.commit()
 resubmit()
 assert report.sample_status=='已领取'
 review()
 assert (report.status,report.sample_status)==(expected,'已领取')
 assert report.sample_pickup['signed'] is True

@pytest.mark.parametrize('source',['report.review.return','report.approval.return'])
@pytest.mark.parametrize('mode',['entrust_and_data','data_only'])
def test_data_rework_returns_to_review(case,workflow,scenario_factory,monkeypatch,source,mode):
 app,_,_=case
 user,report,resubmit,review=workflow
 from app.models import ProjectStep
 from app.blueprints import reports
 from app import review_version
 user.project_steps.append(ProjectStep.query.filter_by(
  project_id=user.project_steps[0].project_id,step_code='data_entry').one())
 permission=scenario_factory.permission('testing.data_change.view')
 user.permissions.append(permission)
 user.department.permissions.append(permission)
 # PDF freezing is independent of routing; retain real permission/date checks.
 monkeypatch.setattr(review_version,'freeze_ready_preview',lambda *a: None)
 report.status='待审核' if source=='report.review.return' else '待批准'
 report.sample_status='已领取'
 apply_return_plan(report,user,source,'虚拟退回',mode)
 db.session.commit()
 if mode=='entrust_and_data':
  for _ in range(2):
   resubmit()
   apply_return_plan(report,user,'report.contract_review.return','再次退回')
   db.session.commit()
  resubmit()
  review()
 assert report.status=='检测更改中'
 with app.test_request_context(json={}):
  g.current_user=user
  response=inspect.unwrap(reports.change_test_complete)(report.report_no)
  result=(response[0] if isinstance(response,tuple) else response).get_json()
  assert result['code']==0,result
 assert (report.status,report.sample_status)==('待审核','已领取')

def test_new_return_round_replaces_previous_scope(workflow):
 user,report,resubmit,review=workflow
 report.sample_status='已领取'
 rounds=[('report.approval.return','entrust_and_data','检测更改中'),
         ('testing.data_entry.return','','检测录入中'),
         ('report.review.return','entrust_only','待审核')]
 for source,mode,expected in rounds:
  apply_return_plan(report,user,source,'虚拟新一轮',mode)
  original=dict(report.detail['returnPlan'])
  add_operation_audit(source,'report',report.report_no,actor=user)
  db.session.commit()
  for _ in range(2):
   resubmit()
   apply_return_plan(report,user,'report.contract_review.return','虚拟复评退回')
   db.session.commit()
  resubmit()
  review()
  assert (report.status,report.sample_status)==(expected,'已领取')
  assert report.detail['returnPlan'].get('afterDataChange')==original.get('afterDataChange')
  assert report.detail['returnPlan']['mode']==original['mode']
