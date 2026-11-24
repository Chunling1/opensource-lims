import json
from types import SimpleNamespace as NS
import pytest
from app.extensions import db
from app.models import ReportEsignFlow, ReportEsignSigner
from app.issuance_data_status import flow_label, current_flows, SIGNING, SEALING, CONFIRMING
from app.business_rows import report_business_row
from test_preserved_approval_and_seal_confirmation import prepared, signed_source
from testkit.factories import login_headers
pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('state,signed,included,file,expected',[
 ('signing',False,False,False,SIGNING),('signing',True,False,False,SEALING),
 ('signing',True,True,False,SEALING),('completed',True,False,True,SEALING),
 ('completed',True,True,True,CONFIRMING),('verified',True,True,True,CONFIRMING),
 ('completed',True,True,False,SEALING),('cancelled',True,True,True,SIGNING),
 ('cancelling',True,False,False,SIGNING),('expired',True,False,False,SIGNING),
 ('failed',True,False,False,SEALING)])
def test_evidence_labels(state,signed,included,file,expected):
 flow=NS(status=state,positioning_json=json.dumps({'organizationSeal':{'included':included}}),
  signed_file_id=1 if file else None,signed_sha256='hash' if file else None,
  signers=[NS(status='signed' if signed else 'pending')])
 assert flow_label(flow)==expected


def test_legacy_organization_attempt_and_no_signers():
 flow=NS(status='ready',positioning_json=json.dumps({'flowKind':'organization_seal','sourceFlowId':1}),signed_file_id=None,signers=[])
 assert flow_label(flow)==SEALING
 flow.positioning_json='{}'
 assert flow_label(flow)==SIGNING
 flow.positioning_json='[]'
 assert flow_label(flow)==SIGNING
 assert flow_label(None)==SIGNING


def test_current_version_latest_attempt_and_projection(prepared,isolated_app,monkeypatch):
 report,version,user,raw=prepared
 assert report.to_row()['dataStatus']==SIGNING
 flow=signed_source(prepared)
 assert report.to_row()['dataStatus']==SEALING
 flow.positioning_json=json.dumps({'organizationSeal':{'included':True,'status':'completed'}})
 db.session.commit()
 assert report_business_row(report)['dataStatus']==CONFIRMING
 assert flow_label(current_flows([report])[report.id])==CONFIRMING
 fresh=ReportEsignFlow(report_id=report.id,report_no=report.report_no,report_document_version_id=version.id,
  attempt_no=flow.attempt_no+1,status='cancelled',source_sha256=version.sha256)
 db.session.add(fresh);db.session.commit()
 assert report.to_row()['dataStatus']==SIGNING  # never fall back to an older sealed attempt
 fresh.status='ready';db.session.commit()
 assert report.to_row()['dataStatus']==SIGNING
 monkeypatch.setitem(isolated_app.config,'ESIGN_PROVIDER_FLOW_MIN_ID',fresh.id+1)
 assert current_flows([report])=={}
 report.approved_document_version_id=report.current_document_version_id=None
 assert report.to_row()['dataStatus']==SIGNING
 report.status='待发放'
 assert report.to_row()['dataStatus']=='报告已盖章，归档中，未发放'
 report.archive_state='归档完成'
 assert report.to_row()['dataStatus']=='报告已归档，发放中'


def test_real_query_filter_by_display_status_preserves_stage_and_scope(prepared,isolated_app):
 report,version,user,raw=prepared
 user.role_key='admin'
 flow=signed_source(prepared)
 db.session.commit()
 client=isolated_app.test_client();headers=login_headers(client,user.account)
 for state,total in [(SEALING,1),(SIGNING,0),(CONFIRMING,0)]:
  body=client.post('/api/reports/query',headers=headers,json={'view':'query','status':state}).get_json()
  assert body['code']==0,body
  assert body['data']['total']==total,body
 flow.positioning_json=json.dumps({'organizationSeal':{'included':True}});db.session.commit()
 body=client.post('/api/reports/query',headers=headers,json={'view':'query','dataStatus':CONFIRMING}).get_json()
 assert body['data']['total']==1,body
 assert body['data']['rows'][0]['status']=='待打印'
 assert body['data']['rows'][0]['dataStatus']==CONFIRMING
 assert report.status=='待打印'
