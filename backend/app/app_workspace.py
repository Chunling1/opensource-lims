"""Personal workspace and AJ-Captcha bridge for the supplied UI (real platform data)."""
from app.organization_privileges import has_full_platform_authority
import base64
import hashlib
import io
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from flask import current_app, g, jsonify, request
from .extensions import db
from .models import JSONText, User, Personnel, Report, OperationAudit
from .security import require_auth
from .audit import add_operation_audit


class PersonalProfile(db.Model):
    __tablename__ = 'personal_workspace_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    details = db.Column(JSONText, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def personal_details(user):
    record = db.session.get(PersonalProfile, user.id)
    person = Personnel.query.filter_by(code=user.account, deleted_at=None).first()
    saved = (record.details or {}) if record else {}
    return dict(phone=saved.get('phone', person.mobile or '' if person else ''),
                email=saved.get('email', ''), avatar=saved.get('avatar', ''),
                departmentName=user.department.name if user.department else '',
                position=person.position or '' if person else '',
                jobTitle=person.title or '' if person else '', certificateNumber='')


def aj_captcha_configured():
    key_file = str(current_app.config.get('AJ_CAPTCHA_KEY_FILE') or '').strip()
    return bool(key_file and Path(key_file).is_file())


def captcha_call(action, body):
    account, uid = body.get('account'), body.get('clientUid')
    if not isinstance(account, str) or not 0 < len(account.strip()) <= 40 or not isinstance(uid, str) or not 16 <= len(uid) <= 80:
        raise ValueError('请输入账号后重新验证')
    data = {k: body[k] for k in ('captchaType', 'pointJson', 'token', 'captchaVerification') if k in body}
    data['owner'] = hashlib.sha256((account.strip()+'\0'+uid).encode()).hexdigest()
    data['peer'] = request.remote_addr or 'unknown'
    service_key = Path(current_app.config.get('AJ_CAPTCHA_KEY_FILE', '')).read_text().strip()
    service_url = str(current_app.config.get('AJ_CAPTCHA_SERVICE_URL') or 'http://127.0.0.1:9016').rstrip('/')
    req = Request(service_url + '/' + action, data=json.dumps(data).encode(),
                  headers={'Content-Type': 'application/json', 'X-Lims-Captcha-Key': service_key})
    with urlopen(req, timeout=8) as response:
        return json.load(response)


def verify_aj_captcha(body):
    if not aj_captcha_configured():
        return None
    try:
        result = captcha_call('verification', body)
        if result.get('repCode') == '0000':
            return None
        return jsonify(code=4, message='验证已失效，请重新完成安全验证', data=None), 200
    except ValueError:
        return jsonify(code=4, message='验证参数无效，请重新验证', data=None), 200
    except Exception:
        current_app.logger.warning('AJ-Captcha unavailable during login')
        return jsonify(code=503, message='安全验证服务暂不可用，请稍后重试', data=None), 503


def login_needs_captcha(account):
    if not aj_captcha_configured():
        return False
    from .platform.identity.login_security import LoginEvent
    # Password authentication results are authoritative. Profile reads and password-change events are not login attempts.
    outcomes=('success','first_login_required','invalid_credentials','password_locked','locked')
    event=LoginEvent.query.filter(LoginEvent.account==account,LoginEvent.result.in_(outcomes)).order_by(LoginEvent.occurred_at.desc(),LoginEvent.id.desc()).first()
    if event is not None:return event.result not in ('success','first_login_required')
    # No login history starts without a challenge; retained failure counters survive audit-log expiry.
    user=User.query.filter_by(account=account).first()
    return bool(user and user.failed_attempts)


def validated_details(body):
    if not isinstance(body, dict) or set(body)-{'phone', 'email', 'avatar'}:
        raise ValueError('仅允许修改联系电话、邮箱和头像')
    result = {}
    for field in ('phone', 'email', 'avatar'):
        value = body.get(field, '')
        if not isinstance(value, str): raise ValueError('资料格式无效')
        result[field] = value.strip()
    phone, email, avatar = (result[k] for k in ('phone','email','avatar'))
    if phone and not re.fullmatch(r'[+\d][\d\s()+-]{4,29}', phone): raise ValueError('请输入有效的联系电话')
    if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)): raise ValueError('请输入有效的电子邮箱')
    if avatar:
        if len(avatar)>512*1024 or not avatar.startswith('data:image/png;base64,'): raise ValueError('头像格式无效')
        from PIL import Image
        try:
            raw = base64.b64decode(avatar.split(',',1)[1], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='PNG' or max(image.size)>1024: raise ValueError()
                image.verify()
        except Exception: raise ValueError('头像图片无效，请重新选择')
    return result


ROUTES = {
    'contract_review': ('合同评审','/inspection/entrust/contract_review'),
    'sample_inbound': ('样品入库','/inspection/sample/inbound'),
    'sample_outbound': ('样品领取','/inspection/sample/outbound'),
    'data_entry': ('检测录入','/inspection/testing/data_entry'),
    'data_change': ('退回更改','/inspection/testing/data_change'),
    'review': ('报告审核','/inspection/report/review'),
    'approval': ('报告批准','/inspection/report/approval'),
    'print': ('报告签发','/inspection/report/print'),
    'archive': ('报告归档','/inspection/report/archive'),
    'release': ('报告发放','/inspection/report/release'),
    'entrust_change': ('委托更改','/inspection/entrust/change'),
}
COMPLETIONS = {'report.data_entry.complete':'检测录入完成', 'report.review.pass':'报告审核通过',
               'report.approval.pass':'报告批准通过', 'report.print.pass':'报告签发完成',
               'report.seal.completed':'报告盖章完成', 'report.distribution.complete':'报告发放完成',
               'report.release.pass':'历史报告发放完成', 'report.archive.pass':'报告归档完成', 'sample.inbound.confirm':'样品入库完成',
               'sample.out_warehouse.sign':'样品领取完成', 'report.contract_review.pass':'合同评审通过'}


from .list_reads import reuse_list_reads


@reuse_list_reads
def dashboard_data(user, body):
    from .applications.report_lifecycle import scoped_report_query
    from .applications.report_lifecycle.dashboard import report_todo_view
    from urllib.parse import urlencode
    workbench=body.get('workbench','general')
    permissions=set(user.permission_codes())
    allowed={'general'}
    if has_full_platform_authority(user): allowed.update(('admin','analyst','reviewer','approver'))
    if 'testing.data_entry.view' in permissions: allowed.add('analyst')
    if 'report.review.view' in permissions: allowed.add('reviewer')
    if 'report.approval.view' in permissions: allowed.add('approver')
    if workbench not in allowed: raise PermissionError('无此工作台权限')
    stage_filter={'analyst':{'data_entry','data_change'},'reviewer':{'review'},'approver':{'approval'}}.get(workbench)
    from .list_projection import list_reports
    from .list_reads import prime_identifiers
    reports=list_reports(scoped_report_query(Report.query,user))
    prime_identifiers('report', (r.report_no for r in reports), reports)
    today=(datetime.utcnow()+timedelta(hours=8)).date()
    rows=[]; actions=set(user.action_codes())
    for report in reports:
        stage=report_todo_view(user,report,actions=actions)
        if stage not in ROUTES or stage_filter and stage not in stage_filter: continue
        detail=report.detail or {}; raw=detail.get('rawSample') or {}
        deadline=str(report.deadline or '')
        due=next((str(raw[k])[:10] for k in ('requiredTestDate','testDueDate') if re.match(r'^\d{4}-\d{2}-\d{2}',str(raw.get(k,'')))), '')
        if not due and re.fullmatch(r'\d{4}-\d{2}-\d{2}',deadline): due=deadline
        overdue=deadline=='超期' or bool(due and due<today.isoformat())
        returned=report.status in ('退回待重传','检测更改中','委托更改中')
        rows.append(dict(id=report.report_no,code=report.sample_no or report.report_no,reportCode=report.report_no,
            name=raw.get('sampleName') or report.project or '',plan=report.project or '',inspector=report.owner or '',
            due=due or deadline,status=report.to_row()['dataStatus'],returned=returned,overdue=overdue,
            to=ROUTES[stage][1]+'?'+urlencode({'keyword':report.report_no}),action='去处理',stage=stage))
    rows.sort(key=lambda r:(not r['overdue'],not r['returned'],r['due'] or '9999',r['code']))
    queue_counts=Counter(r['stage'] for r in rows)
    queues=[dict(id='all',title='全部',total=len(rows),to='/dashboard')]+[
        dict(id=k,title=v[0],total=queue_counts[k],to=v[1]) for k,v in ROUTES.items() if queue_counts[k]]
    queue=body.get('queue') or 'all'
    if queue not in {q['id'] for q in queues}:queue='all'
    filtered=[r for r in rows if queue=='all' or r['stage']==queue]
    filter_value=body.get('filter','all')
    if filter_value in ('overdue','returned'): filtered=[r for r in filtered if r[filter_value]]
    size=int(body.get('pageSize',10));page=int(body.get('page',1))
    if size not in (10,20,50) or page<1:raise ValueError('分页参数无效')
    page=min(page,max(1,(len(filtered)+size-1)//size))
    report_by_id={r.report_no:r for r in reports}
    start=datetime.combine(today-timedelta(days=6),datetime.min.time())-timedelta(hours=8)
    from sqlalchemy.orm import load_only
    events=OperationAudit.query.options(load_only(
        OperationAudit.id, OperationAudit.action, OperationAudit.object_id,
        OperationAudit.user_name, OperationAudit.created_at, raiseload=True,
    )).filter(OperationAudit.object_type=='report',OperationAudit.success.is_(True),
        OperationAudit.action.in_(list(COMPLETIONS)),OperationAudit.created_at>=start)
    if workbench!='admin':events=events.filter(OperationAudit.user_id==user.id)
    events=[e for e in events.order_by(OperationAudit.created_at.desc()).all() if e.object_id in report_by_id]
    if stage_filter:
        event_actions={'analyst':{'report.data_entry.complete'},'reviewer':{'report.review.pass'},'approver':{'report.approval.pass'}}[workbench]
        events=[e for e in events if e.action in event_actions]
    days=Counter((e.created_at+timedelta(hours=8)).date().isoformat() for e in events)
    completed_stages={'report.data_entry.complete':'data_entry','report.review.pass':'review','report.approval.pass':'approval',
                      'report.print.pass':'print','report.seal.completed':'print','report.distribution.complete':'release','report.release.pass':'archive','report.archive.pass':'archive','sample.inbound.confirm':'sample_inbound',
                      'sample.out_warehouse.sign':'sample_outbound','report.contract_review.pass':'contract_review'}
    recent=[dict(id=str(e.id),code=e.object_id,name=report_by_id[e.object_id].project or '',actor=e.user_name or '',
                 action=COMPLETIONS[e.action],at=e.created_at.isoformat()+'Z',
                 to=('/inspection/report/query' if 'report.query.view' in permissions else ROUTES[completed_stages[e.action]][1])+'?'+urlencode({'keyword':e.object_id})) for e in events[:6]]
    return dict(pending=len(rows),overdue=sum(r['overdue'] for r in rows),returned=sum(r['returned'] for r in rows),
        completedToday=days[today.isoformat()],queues=queues,queue=queue,items=filtered[(page-1)*size:page*size],
        total=len(filtered),page=page,pageSize=size,urgent=rows[:5],recent=recent,
        trend=[dict(date=(today-timedelta(days=n)).isoformat(),count=days[(today-timedelta(days=n)).isoformat()]) for n in range(6,-1,-1)],
        workload=[dict(name=n or '未分配',count=c) for n,c in Counter(r['inspector'] for r in rows).most_common(8)],updatedAt=datetime.utcnow().isoformat()+'Z')


def register_workspace(bp):
    @bp.post('/login-state')
    def login_state():
        body=request.get_json(silent=True)
        account=body.get('account') if isinstance(body,dict) else None
        if not isinstance(account,str) or not 0<len(account.strip())<=40:
            return jsonify(code=422,message='请输入有效账号',data=None),422
        response=jsonify(code=0,message='ok',data={'captchaRequired':login_needs_captcha(account.strip())})
        response.headers['Cache-Control']='no-store'
        return response

    @bp.post('/aj-captcha/<action>')
    def captcha_api(action):
        if action not in ('get','check'):return jsonify(repCode='FAILED',repMsg='接口不存在'),404
        body=request.get_json(silent=True)
        if not isinstance(body,dict):return jsonify(repCode='FAILED',repMsg='验证参数无效'),400
        try:
            result=captcha_call(action,body)
            response=jsonify(result);response.headers['Cache-Control']='no-store';return response
        except ValueError:return jsonify(repCode='FAILED',repMsg='请填写账号后重新验证'),400
        except Exception:return jsonify(repCode='FAILED',repMsg='安全验证服务暂不可用，请稍后重试'),503

    @bp.get('/personal-profile')
    @require_auth
    def get_personal_profile():
        return jsonify(code=0,message='ok',data=personal_details(g.current_user))

    @bp.put('/personal-profile')
    @require_auth
    def save_personal_profile():
        try:details=validated_details(request.get_json(silent=True))
        except ValueError as e:return jsonify(code=422,message=str(e),data=None),422
        # Serialize saves for this authenticated account. Body cannot select a different user.
        user=User.query.filter_by(id=g.current_user.id).with_for_update().one()
        record=db.session.get(PersonalProfile,user.id)
        if record is None:record=PersonalProfile(user_id=user.id,details={});db.session.add(record)
        before=record.details or {};record.details={**before,**details};record.updated_at=datetime.utcnow()
        audit=lambda d:{'phone':d.get('phone',''),'email':d.get('email',''),'hasAvatar':bool(d.get('avatar'))}
        add_operation_audit('user.profile.update','user',user.account,before=audit(before),after=audit(details))
        db.session.commit()
        return jsonify(code=0,message='个人资料已保存',data=details)

    @bp.post('/workbench')
    @require_auth
    def workbench():
        body=request.get_json(silent=True)
        if not isinstance(body,dict):return jsonify(code=422,message='查询参数无效',data=None),422
        try:result=dashboard_data(g.current_user,body)
        except PermissionError as e:return jsonify(code=403,message=str(e),data=None),403
        except (ValueError,TypeError):return jsonify(code=422,message='查询参数无效',data=None),422
        return jsonify(code=0,message='ok',data=result)
