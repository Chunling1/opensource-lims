import pytest
from sqlalchemy import literal
from app.extensions import db
from app.models import Report,Entrust
from app import list_paging as p
from test_list_query_prototype import prototype_mysql_app,mysql_server

@pytest.mark.parametrize('presentation',['report','registration-sample','entry','inbound','outbound','flow'])
def test_ten_search_fields(presentation):
 fields={k:literal('x') for k in (*p.REPORT_ALL_SEARCH_KEYS,'schemeDisplay','clientAddress','reportReviewedBy')}
 expected=list(p.REPORT_ALL_SEARCH_KEYS)
 if presentation=='report':expected[expected.index('schemeName')]='schemeDisplay'
 assert p.all_search_keys({'presentation':presentation},fields)==expected

def test_entrust_five_fields():
 assert p.all_search_keys({},dict.fromkeys(['id',*p.ENTRUST_ALL_SEARCH_KEYS,'editedAt','clientAddress']))==list(p.ENTRUST_ALL_SEARCH_KEYS)

def test_excluded_fields_are_still_individually_searchable(prototype_mysql_app):
 from testkit.factories import ScenarioFactory
 with prototype_mysql_app.app_context():
  f=ScenarioFactory();d=f.department();u=f.user(d,role_key='admin',account='admin')
  db.session.add(Entrust(entrust_no='E',client='customer',info={'clientAddress':'PRIVATE-ADDR','remark':'PRIVATE-NOTE'}))
  db.session.add(Report(report_no='R',entrust_no='E',detail={'rawSample':{'sampleName':'MATCH','testLocation':'PRIVATE-LOCATION'}}));db.session.commit()
  for enabled in (False,True):
   prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=enabled,LIST_QUERY_A2=enabled)
   for term,key,total in [('PRIVATE-ADDR','all',0),('PRIVATE-ADDR','clientAddress',1),('MATCH','all',1),('PRIVATE-LOCATION','all',0),('PRIVATE-LOCATION','testingLocation',1)]:
    rows,meta=p.load_report_page(Report.query,u,'query',{'contains':term,'searchField':key,'presentation':'report'})
    assert meta['total']==total
   for term,key,total in [('PRIVATE-NOTE','all',0),('PRIVATE-NOTE','remark',1),('customer','all',1)]:
    rows,meta=p.load_entrust_page(Entrust.query,{'contains':term,'searchField':key,'presentation':'commission'})
    assert meta['total']==total
