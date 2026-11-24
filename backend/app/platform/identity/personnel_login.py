"""Identity commands used by quality roster saves; caller owns the transaction."""
import re
from flask import g, has_request_context
from datetime import datetime
from ...extensions import db
from ...models import Department, User, user_data_departments
from ...security import hash_password
from ..audit import add_operation_audit
from .access import can_manage_users
from .login_security import initial_password
from .department_sync import synchronize_user_department


def personnel_login(actor, *, account, name, department_name, enabled=True):
    if not can_manage_users(actor):
        raise ValueError('建立登录账号需要用户管理权限')
    account, name = str(account or '').strip(), str(name or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{2,40}', account) or not name or len(name)>40:
        raise ValueError('姓名或人员编号不符合账号规则')
    departments=Department.query.filter_by(name=department_name).all()
    if len(departments)!=1:
        raise ValueError('请选择唯一有效的所属部门')
    users=User.query.filter(db.func.lower(db.func.trim(User.account))==account.lower()).all()
    if users:
        if len(users)!=1 or users[0].name.strip()!=name or users[0].department_id!=departments[0].id:
            raise ValueError('该编号已有其他姓名或部门的账号，请先核对，不会自动覆盖')
        return users[0],False
    # Same first-login policy as personnel registration. No role/function/project grants.
    temp_password = initial_password(account)
    user=User(account=account,name=name,password_hash=hash_password(temp_password),
        role_key='custom',role_name='自定义角色',home_path='/inspection/dashboard',
        department_id=departments[0].id,data_scope_type='department',enabled=bool(enabled),must_change_password=True)
    db.session.add(user)
    user._initial_password = temp_password
    db.session.flush()
    if has_request_context():
        credentials = getattr(g, "initial_credentials", [])
        credentials.append({"account": user.account, "name": user.name, "department": departments[0].name,
                            "enabled": bool(user.enabled), "initialPassword": temp_password})
        g.initial_credentials = credentials
    db.session.execute(user_data_departments.insert().values(user_id=user.id,department_id=departments[0].id,
        include_children=False,see_data=True,see_members=True,granted_by=actor.account,
        granted_at=datetime.utcnow().isoformat(timespec='seconds')))
    add_operation_audit('organization.user.create','user',user.id,category='admin',
        after={'account':account,'departmentId':departments[0].id,'fromPersonnel':True},
        message='人员档案同步建号；未授予功能、操作或项目权限')
    return user,True


def update_personnel_login(actor,user,*,name,department,enabled):
    if not can_manage_users(actor):
        raise ValueError('调整登录账号需要用户管理权限')
    if user.id==actor.id and not enabled:
        raise ValueError('不能停用当前登录账号')
    if user.role_key=='admin' and (user.department_id!=department.id or not enabled or user.name!=name):
        raise ValueError('系统管理员账号请在用户管理中单独调整')
    if user.department_id!=department.id:
        old=user.department
        user.department=department
        synchronize_user_department(user,old,department,actor=actor)
    user.name=name
    user.enabled=enabled
