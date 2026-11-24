"""Synthetic scale only: disposable MySQL and no network."""
from pathlib import Path
import json,time,hashlib,logging
from datetime import datetime
from sqlalchemy import text,event
from app.extensions import db
from app.models import Report,Entrust,OperationAudit
from test_list_query_prototype import prototype_mysql_app,mysql_server

def test_report_volume(prototype_mysql_app):
 from testkit.factories import ScenarioFactory
 from app.security import issue_token
 evidence=Path('/mnt/d/lims-perf-qa/evidence/v195r-volume.json')
 result={'synthetic':True,'productionConnected':False,'groups':[],'fallbacks':[],'maxExecutionTimeMs':120000,'auditsPerReport':51}
 def save():evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
 class Logs(logging.Handler):
  def emit(self,record):
   if 'list query prototype fallback:' in record.getMessage():result['fallbacks'].append(record.getMessage())
 prototype_mysql_app.logger.addHandler(Logs())
 with prototype_mysql_app.app_context():
  f=ScenarioFactory();d=f.department(name='Synthetic');u=f.user(d,role_key='admin',account='admin')
  db.session.add(Entrust(entrust_no='VOLUME-E',client='synthetic',project_name='fixture',info={}));db.session.commit()
  for name,columns in [('ix_oa_object_action','object_type,object_id,action,success,id'),('ix_oa_object_time','object_type,object_id,success,created_at')]:
   db.session.execute(text('CREATE INDEX '+name+' ON operation_audits ('+columns+')'))
  db.session.commit();department_name=d.name;existing=0;h={'Authorization':'Bearer '+issue_token(u)};client=prototype_mysql_app.test_client()
  prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=True,LIST_QUERY_A2=True)
  for count in (2500,25000):
   db.session.execute(text('SET SESSION TRANSACTION READ WRITE'))
   for start in range(existing,count,500):
    rows=[dict(report_no=f'VOLUME-{i:05}',sample_no=f'S-{i:05}',entrust_no='VOLUME-E',department=department_name,status='待批准',sample_reg_state='登记完成',detail={'rawSample':{'sampleName':'needle' if i%100==0 else 'synthetic','schemeName':'fixture','schemeCode':'VOL','projectList':['parameter']}}) for i in range(start,min(count,start+500))]
    db.session.execute(Report.__table__.insert(),rows)
   for start in range(existing*51,count*51,5000):
    audits=[dict(category='business',action='report.data_entry.save' if i%2 else 'unrelated',object_type='report',object_id=f'VOLUME-{i//51:05}',success=i%10!=0,account='synthetic',user_name='synthetic',created_at=datetime(2026,1,1),trace_id=f'volume-{i}') for i in range(start,min(count*51,start+5000))]
    db.session.execute(OperationAudit.__table__.insert(),audits)
   db.session.commit();existing=count;db.session.execute(text('ANALYZE TABLE reports,operation_audits'));db.session.commit()
   queries=[]
   def capture(c,cur,sql,params,ctx,many):
    if sql.lstrip().upper().startswith(('SELECT','WITH')):queries.append((sql,params))
   def readonly(c,record,proxy):
    cur=c.cursor();cur.execute('SET SESSION max_execution_time=120000');cur.execute('SET SESSION TRANSACTION READ ONLY');cur.close()
   event.listen(db.engine,'checkout',readonly);event.listen(db.engine,'before_cursor_execute',capture)
   try:
    for name,extra in [('first',{}),('all_hit',{'contains':'needle','searchField':'all'}),('all_nohit',{'contains':'zzqx9','searchField':'all'}),('number',{'contains':'VOLUME-00001','searchField':'reportNo'})]:
     group={'reports':count,'auditRows':count*51,'scenario':name,'samples':[],'plans':[]};result['groups'].append(group)
     run=0;target=30;maximum=0
     while run<target:
      run+=1;queries.clear();start=time.perf_counter();row={'run':run}
      try:
       resp=client.post('/api/reports/query',headers=h,json={'view':'query','presentation':'report','serverPage':True,'page':1,'pageSize':10,**extra});payload=resp.get_json()
       assert resp.status_code==200 and payload['code']==0
       row.update(status='ok',total=payload['data']['total'],sha256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest())
      except Exception as exc:
       code=getattr(getattr(exc,'orig',None),'args',(None,))[0];row.update(status='timeout' if code in (3024,1969) else 'error',errorType=type(exc).__name__,databaseErrorCode=code)
      finally:row['seconds']=time.perf_counter()-start;db.session.rollback()
      maximum=max(maximum,row['seconds']);target=3 if maximum>10 else 10 if maximum>=1 else 30
      group['samples'].append(row);group.update(actualRuns=run,requiredRuns=target);save()
      print('VOLUME',count,name,run,row['status'],round(row['seconds'],3),flush=True)
     event.remove(db.engine,'before_cursor_execute',capture)
     try:
      for sql,params in list(dict((hashlib.sha256(sql.encode()).hexdigest(),(sql,params)) for sql,params in queries).values()):
       if 'operation_audits' not in sql:continue
       try:group['plans'].append({'sqlSha256':hashlib.sha256(sql.encode()).hexdigest(),'plan':[dict(r._mapping) for r in db.session.connection().exec_driver_sql('EXPLAIN '+sql,params)]})
       except Exception as exc:group['plans'].append({'errorType':type(exc).__name__})
      db.session.rollback()
     finally:event.listen(db.engine,'before_cursor_execute',capture)
     save()
   finally:
    event.remove(db.engine,'checkout',readonly);event.remove(db.engine,'before_cursor_execute',capture);db.session.rollback();db.session.remove()
  result['completed']=True;result['rollbackExecuted']=True;save()
