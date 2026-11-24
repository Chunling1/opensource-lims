"""Audited correction mode for existing domain commands and their side effects."""
from functools import wraps
from flask import current_app, g, request, make_response
from sqlalchemy import event
from ..extensions import db
from ..platform.audit import add_operation_audit
from . import can_correct_business_data
from .catalog import CATALOG
from .web import fail, revision, values, WARNING


def audited_form(kind, id_argument):
    def decorate(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            body = request.get_json(silent=True)
            proof = body.get("adminCorrection") if isinstance(body, dict) else None
            if proof is None:
                return fn(*args, **kwargs)
            if not can_correct_business_data(g.current_user):
                return fail("没有管理员修订权限", 403)
            if current_app.config.get("APP_BUSINESS_READ_ONLY"):
                return fail("平台处于只读维护状态", 423)
            model = CATALOG[kind][1]
            key = kwargs[id_argument]
            query = model.query.filter_by(report_no=key) if kind == "reports" else model.query.filter_by(id=key)
            row = query.with_for_update().first()
            if row is None:
                return fail("记录不存在", 404)
            before = values(row)
            if not isinstance(proof, dict) or proof.get("confirmed") is not True or proof.get("revision") != revision(before):
                return fail("数据已变化或尚未确认修订，请重新打开表单核对", 409)
            reason = proof.get("reason")
            if not isinstance(reason, str) or not 2 <= len(reason.strip()) <= 300:
                return fail("请填写修改说明（2至300字）")
            # Scoped to this authenticated endpoint, never a caller-supplied flag.
            g.business_correction = dict(kind=kind, row=row, reason=reason.strip())
            session = db.session()
            committed = False
            def audit_before_commit(session):
                nonlocal committed
                if committed:
                    return
                committed = True
                session.flush()
                add_operation_audit("admin.business.correct", kind, str(key), category="business",
                    before=before, after=values(row), message=WARNING + " 修改说明：" + reason.strip())
            event.listen(session, "before_commit", audit_before_commit)
            try:
                response = make_response(fn(*args, **kwargs))
                result = response.get_json(silent=True)
                if isinstance(result, dict) and result.get("code") == 0:
                    if isinstance(result.get("data"), dict):
                        result["data"]["correctionValues"] = values(row)
                        result["data"]["correctionRevision"] = revision(values(row))
                        result["data"]["message"] = "已保存管理员修订，修改人及修改前后内容已记录。"
                    response.set_data(current_app.json.dumps(result))
                else:
                    session.rollback()
                return response
            except Exception:
                session.rollback()
                raise
            finally:
                event.remove(session, "before_commit", audit_before_commit)
                g.pop("business_correction", None)
        return run
    return decorate


def active(kind=None):
    value = getattr(g, "business_correction", None)
    return bool(value and (kind is None or value["kind"] == kind))
