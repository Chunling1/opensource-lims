"""Disposable synthetic database; never uses the backup database or network."""
from pathlib import Path
import json, time, hashlib, logging
from datetime import datetime, timedelta
from sqlalchemy import text, event
from app.extensions import db
from app.models import Report, Entrust, OperationAudit
from test_list_query_prototype import prototype_mysql_app, mysql_server


def test_audit_scale(prototype_mysql_app):
    from testkit.factories import ScenarioFactory
    from app.security import issue_token
    from app.applications.report_lifecycle.query_details import STAGES
    evidence=Path('/mnt/d/lims-perf-qa/evidence/a2-scale.json')
    result={'synthetic':True,'productionConnected':False,'baseAudits':13098,'groups':[],
            'fixture':{'reports':257,'entrusts':26,'auditKinds':['report','entrust','other'],
                       'successRatio':'9/10','latestRule':'ID; timestamps deliberately repeat and disagree with ID',
                       'payload':'synthetic small JSON; does not represent production form size'},'maxExecutionTimeMs':120000}
    def save():evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    result['fallbacks']=[]
    class CaptureFallback(logging.Handler):
        def emit(self,record):
            if 'list query prototype fallback:' in record.getMessage():result['fallbacks'].append(record.getMessage())
    prototype_mysql_app.logger.addHandler(CaptureFallback())
    with prototype_mysql_app.app_context():
        factory=ScenarioFactory();department=factory.department(name='synthetic');user=factory.user(department,role_key='admin',account='admin')
        for i in range(26):db.session.add(Entrust(entrust_no='SCALE-WT-'+str(i),client='synthetic',info={}))
        for i in range(257):
            db.session.add(Report(report_no='SCALE-R-'+str(i),entrust_no='SCALE-WT-'+str(i%26),sample_no='S-'+str(i),
                department=department.name,status='待批准',sample_reg_state='登记完成',
                detail={'rawSample':{'sampleName':'yp' if i<16 else 'synthetic','sendDate':'2026-01-02','schemeCode':'SYN','schemeName':'fixture'},
                        'summary':[{'fields':[['检测方案','fixture (SYN)'],['委托日期','2026-01-01']]}]}))
        db.session.commit()
        for name,columns in [('ix_oa_object_action','object_type,object_id,action,success,id'),('ix_oa_object_time','object_type,object_id,success,created_at')]:
            db.session.execute(text('CREATE INDEX '+name+' ON operation_audits ('+columns+')'))
        db.session.commit()
        headers={'Authorization':'Bearer '+issue_token(user)}
        actions=list(dict.fromkeys(action for _,group in STAGES.values() for action in group))+['sample.inbound.confirm','sample.out_warehouse.sign','unrelated']
        base=datetime(2026,1,1);existing=0
        client=prototype_mysql_app.test_client()
        prototype_mysql_app.config.update(LIST_QUERY_PROTOTYPE=True,LIST_QUERY_A2=True)
        for scale in (10,30):
            # Only this newly created synthetic database is written. Requests
            # below run in read-only transactions with a per-SELECT limit.
            db.session.execute(text('SET SESSION TRANSACTION READ WRITE'))
            target=13098*scale
            for start in range(existing,target,5000):
                batch=[]
                for i in range(start,min(start+5000,target)):
                    kind=('report','entrust','other')[i%3]
                    identity='SCALE-R-'+str(i%257) if kind=='report' else 'SCALE-WT-'+str(i%26) if kind=='entrust' else 'OTHER-'+str(i%1000)
                    batch.append(dict(category='business',action=actions[i%len(actions)],object_type=kind,object_id=identity,
                        trace_id='synthetic-'+str(i),account='synthetic',user_name='' if i%2 else 'synthetic',
                        success=i%10!=0,created_at=base+timedelta(seconds=(target-i)//3)))
                db.session.execute(OperationAudit.__table__.insert(),batch)
            db.session.commit();existing=target
            db.session.execute(text('ANALYZE TABLE operation_audits'))
            count=db.session.execute(text('SELECT COUNT(*) FROM operation_audits')).scalar();assert count==target
            db.session.commit()
            queries=[]
            def capture(c,cur,sql,params,ctx,many):
                if sql.lstrip().upper().startswith(('SELECT','WITH')):queries.append((sql,params))
            def readonly(c,record,proxy):
                cursor=c.cursor();cursor.execute('SET SESSION max_execution_time=120000');cursor.execute('SET SESSION TRANSACTION READ ONLY');cursor.close()
            event.listen(db.engine,'checkout',readonly);event.listen(db.engine,'before_cursor_execute',capture)
            try:
                for name,term in [('first',''),('yp','yp')]:
                    group={'scale':scale,'auditRows':count,'scenario':name,'actualRuns':0,'samples':[],'plans':[]}
                    result['groups'].append(group)
                    for run in range(1,4):
                        queries.clear();start=time.perf_counter();row={'run':run}
                        try:
                            response=client.post('/api/reports/query',headers=headers,json=dict(view='query',presentation='report',serverPage=True,page=1,pageSize=10,contains=term,searchField='all'))
                            payload=response.get_json();assert response.status_code==200 and payload['code']==0
                            row.update(status='ok',total=payload['data']['total'],sha256=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
                        except Exception as exc:
                            code=getattr(getattr(exc,'orig',None),'args',(None,))[0]
                            row.update(status='timeout' if code in (3024,1969) else 'error',errorType=type(exc).__name__,databaseErrorCode=code)
                        finally:row['seconds']=time.perf_counter()-start;db.session.rollback()
                        group['samples'].append(row);group['actualRuns']+=1;save()
                        print('SCALE',scale,name,run,row,flush=True)
                    captured=list(dict((hashlib.sha256(sql.encode()).hexdigest(),(sql,params)) for sql,params in queries).items())
                    event.remove(db.engine,'before_cursor_execute',capture)
                    try:
                        for sha,(sql,params) in captured:
                            if 'operation_audits' not in sql:continue
                            plan=[dict(r._mapping) for r in db.session.connection().exec_driver_sql('EXPLAIN '+sql,params)]
                            group['plans'].append({'sqlSha256':sha,'characters':len(sql),'plan':plan})
                        db.session.rollback()
                    finally:event.listen(db.engine,'before_cursor_execute',capture)
                    save()
                    assert all(r['status']=='ok' for r in group['samples'])
                    assert len({r['sha256'] for r in group['samples']})==1
            finally:
                event.remove(db.engine,'checkout',readonly);event.remove(db.engine,'before_cursor_execute',capture)
                db.session.rollback();db.session.remove()
        result['completed']=True;result['rollbackExecuted']=True;save()
        assert not result['fallbacks']
