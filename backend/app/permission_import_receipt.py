"""Signed, short-lived preview receipts. Contains hashes only, no credentials/PII."""
import hashlib
import json
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadData
from sqlalchemy import select, text
from .extensions import db

TABLES = (
    'users', 'departments', 'permissions', 'projects', 'project_steps', 'permission_templates',
    'user_permissions', 'user_action_permissions', 'user_project_permissions', 'user_data_departments',
    'user_data_sites', 'permission_template_permissions', 'permission_template_project_steps',
    'permission_template_users', 'department_permissions', 'department_project_permissions',
    'department_project_step_permissions',
)
USER_COLUMNS = ('id', 'account', 'name', 'department_id', 'enabled', 'role_key', 'data_scope_type')

def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(',', ':')).encode()).hexdigest()

def authorization_fingerprint():
    values = {}
    for name in TABLES:
        table = db.metadata.tables[name]
        columns = [table.c[c] for c in USER_COLUMNS] if name == 'users' else list(table.columns)
        rows = [dict(row) for row in db.session.execute(select(*columns)).mappings()]
        values[name] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))
    return _hash(values)

def preview_binding(preview):
    return _hash({
        'people': sorted((name, user.id) for name, user in preview['_matched_users'].items()),
        'projects': sorted((key, project.id) for key, project in preview['_resolved_projects'].items()),
        'newProjects': sorted(preview['_new_projects'].items()),
        'grants': sorted(preview['_grants']),
    })

def _serializer():
    return URLSafeTimedSerializer(current_app.config['JWT_SECRET'], salt='permission-appointment-preview-v1')

def issue_receipt(preview, actor):
    return _serializer().dumps({'actor': actor.id, 'file': preview['sourceSha256'],
        'state': authorization_fingerprint(), 'binding': preview_binding(preview), 'scope': 'report-managed'})

def validate_receipt(token, preview, actor):
    try:
        value = _serializer().loads(token, max_age=1800)
    except (BadData, TypeError, ValueError):
        return False
    return value == {'actor': actor.id, 'file': preview['sourceSha256'],
        'state': authorization_fingerprint(), 'binding': preview_binding(preview), 'scope': 'report-managed'}

def lock_import_snapshot():
    # Called before any import mutation. Authentication may already have opened
    # a read transaction; never reuse its MySQL repeatable-read snapshot.
    connection = db.session.connection()
    if connection.dialect.name == 'sqlite':
        if connection.connection.driver_connection.in_transaction:
            raise ValueError('当前导入事务已开始，请重新预检后提交')
        db.session.execute(text('BEGIN IMMEDIATE'))
    elif connection.dialect.name == 'mysql':
        if db.session.new or db.session.dirty or db.session.deleted:
            raise ValueError('当前导入事务存在未提交修改，请重新预检后提交')
        db.session.rollback()
        # Full primary-index locking reads at RR lock both existing rows and
        # gaps (including empty tables). This protects against ordinary manual
        # grant writers too, not only other cooperative importer processes.
        db.session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        engines = dict(db.session.execute(text(
            'SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES '
            'WHERE TABLE_SCHEMA = DATABASE()'
        )).all())
        if any(engines.get(name) != 'InnoDB' for name in TABLES):
            db.session.rollback()
            raise ValueError('权限导入需要全部授权表使用 InnoDB，禁止提交')
        for name in TABLES:
            table = db.metadata.tables[name]
            columns = list(table.primary_key.columns)
            if not columns:
                db.session.rollback()
                raise ValueError('权限表缺少主键，禁止提交')
            db.session.execute(select(*columns).order_by(*columns).with_for_update()).all()
    else:
        raise ValueError('当前数据库尚未配置权限导入并发保护，禁止提交')
    db.session.expire_all()
