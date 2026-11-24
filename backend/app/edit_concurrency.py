"""Protect long-lived business forms and concurrent ORM updates."""
import hashlib
import json
from flask import jsonify
from sqlalchemy.orm.exc import StaleDataError
from .extensions import db


def require_edit_version(row, body):
    from .admin_corrections.existing import active
    # Privileged corrections already verify the entire original snapshot.
    if active():
        return None
    expected = body.get('editVersion')
    if type(expected) is not int or expected != row.edit_version:
        return jsonify(code=409, message='资料已更新或页面版本已过期，请保留当前输入，重新打开表单核对后保存。', data=None), 409
    return None


def install_conflict_handler(app):
    @app.errorhandler(StaleDataError)
    def concurrent_write(_error):
        db.session.rollback()
        return jsonify(code=409, message='保存期间资料被其他操作更新，本次修改未保存，请重新打开核对。', data=None), 409


def test_form_version(row):
    """Only authoring inputs/state: attachment and preview operations are independent.

    The row edit_version still protects transactions against concurrent ORM writes.
    A form token protects the input snapshot without requiring a reload after the
    same user's attachment uploads or report-composition choices.
    """
    detail = row.detail or {}
    snapshot = {key: detail.get(key) for key in
                ('checkInput', 'rawSample', 'assigned', 'workflowDates', 'returnPlan')}
    snapshot['report'] = [row.id, row.status, row.sample_status, row.project, row.owner]
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def require_test_form_version(row, body):
    from .admin_corrections.existing import active
    if active():
        return None
    if body.get('testEditVersion') != test_form_version(row):
        return jsonify(code=409, message='检测录入内容已更新或页面版本已过期，请保留当前输入，重新打开核对后保存。', data=None), 409
    return None
