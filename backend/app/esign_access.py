"""Local object authorization shared by eSign routes and services; no provider I/O."""
from .models import Report, ReportEsignFlow
from .authorization_scope import project_step_error
from .platform.identity import has_org_wide_business_scope


def report_scope_error(user, report):
    from .applications.report_lifecycle.queries import scoped_report_query
    if not user or not user.enabled or not report:
        return "账号或报告不存在或不可用"
    from .list_reads import report_visible_to
    if not report_visible_to(user, report.id, lambda:
            scoped_report_query(Report.query, user).with_entities(Report.id).filter(Report.id == report.id).first() is not None):
        return "报告不存在或不在数据范围内"
    # Defense in depth: legacy status compatibility never grants another
    # department's eSign objects. Shared report queries enforce the same scope.
    if (user.data_scope_type == "authorization" and not has_org_wide_business_scope(user)
            and report.department not in user.data_department_names()):
        return "历史数据范围未明确授权该报告部门"
    return ""


def flow_state_error(flow):
    if flow is None:
        return "电子签发任务不存在"
    from .internal_report_corrections import is_historical_flow
    if is_historical_flow(flow):
        return "签署流程属于内部更正前的历史版本"
    report = flow.report
    if not report or flow.report_no != report.report_no or report.voided:
        return "报告不存在、归属不一致或已作废"
    from .functions.esign_stages import is_staged
    if is_staged(flow) and report.current_document_version_id != flow.report_document_version_id:
        return '签署文件已被其他版本替代'
    version = flow.document_version
    if version is None or version.report_no != report.report_no:
        return "签署版本不属于当前报告"
    if report.approved_document_version_id and report.approved_document_version_id != flow.report_document_version_id:
        return "签署流程不是当前批准版本"
    # Attempts are numbered per document version, not across the whole report.
    latest = ReportEsignFlow.query.filter_by(
        report_id=report.id, report_document_version_id=flow.report_document_version_id
    ).order_by(ReportEsignFlow.attempt_no.desc(), ReportEsignFlow.id.desc()).first()
    if not latest or latest.id != flow.id:
        return "签署流程已被新轮次替代"
    if flow.status not in {"binding_required", "ready", "failed", "dispatching", "signing", "completed", "verified"}:
        return "签署流程已失效或撤销"
    return ""


def manager_report_error(user, report):
    error = report_scope_error(user, report)
    if error:
        return error
    if report.voided:
        return "报告已作废"
    if user.role_key != "admin" and "report.print.view" not in user.permission_codes():
        return "无报告签发任务管理权限"
    # Administrator's existing module exception does not invent a project appointment.
    return project_step_error(user, report, "report_print", "报告签发")


def manager_flow_error(user, flow):
    if flow is None:
        return "电子签发任务不存在"
    return manager_report_error(user, flow.report) or flow_state_error(flow)


def signer_access_error(user, flow, signer, *, actionable=False):
    if not user or not flow or not signer or signer.user_id != user.id or signer.flow_id != flow.id:
        return "当前账号没有该报告的签署任务"
    error = report_scope_error(user, flow.report) or flow_state_error(flow)
    if error:
        return error
    rule = {"chief": ("data_entry", "主检"), "chief2": ("data_entry", "主检2"), "reviewer": ("report_review", "报告审核"),
            "approver": ("report_approval", "报告批准")}.get(signer.role_code)
    if not rule:
        return "电子签署角色无法映射到项目环节权限"
    error = project_step_error(user, flow.report, *rule)
    if error or not actionable:
        return error
    from .functions.esign_stages import access_error as stage_access_error
    error = stage_access_error(user, flow, signer)
    if error:
        return error
    if flow.status != "signing" or not flow.provider_flow_id or signer.status not in {"pending", "signing"}:
        return "当前流程没有可执行的待签任务"
    if any(s.sign_order < signer.sign_order and s.status != "signed" for s in flow.signers):
        return "前序签署尚未完成，未轮到当前账号"
    binding = signer.binding
    if not binding or binding.user_id != user.id or binding.status not in {"pending", "verified"}:
        return "当前账号签署身份未绑定或已停用"
    return ""
