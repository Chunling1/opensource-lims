from ..edit_concurrency import require_edit_version, require_test_form_version, test_form_version
from app.organization_privileges import has_full_platform_authority
from ..admin_corrections import can_correct_business_data
from ..admin_corrections.existing import audited_form, active as correcting
"""报告接口 — 含数据授权过滤（规格 2.1 数据授权 / 2.5 报告模块）。"""
import copy
import hashlib
import re
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request
from ..adapters.eln import eln_completion_error

from ..applications.report_lifecycle import (
    COMPLIANCE_STAGE_ACCESS,
    augment_report_summary,
    compliance_stage_access_error,
    execute_report_action,
    get_authorized_report_for_view,
    has_report_feature_access,
    report_allowed_actions,
    report_data_entry_step_error,
    report_processing_step_error,
    scoped_report_query,
    persist_report_attachment,
    return_plan,
    resumes_sample_outbound,
)
from ..applications.report_lifecycle import (
    apply_return_plan as _apply_return_plan,
)
from ..applications.report_lifecycle import (
    report_content_editable as application_report_content_editable,
)
from ..applications.testing_records import complete_test_data, save_test_draft
from ..checks import compute_report_checks
from ..preflight_reads import reuse_preflight_reads
from ..cnas_capabilities import normalize_standard_code
from ..covers import signature_state
from ..extensions import db
from ..sample_pricing import contract_completion_error as sample_pricing_error, price_error as sample_price_error
from ..functions.report_standard_text import format_report_standards, load_report_standard_names, load_report_standard_records, standard_separator, display_separator, SEPARATORS
from ..models import (
    CapabilityEntry,
    ComplianceAcknowledgement,
    Entrust,
    EquipmentItem,
    EquipmentUsageRecord,
    Personnel,
    Report,
    ReportAttachment,
    ReportCorrectionRequest,
    ReportDocumentContent,
    ReportDocumentVersion,
    ReportRenderJob,
    Standard,
    User,
)
from ..platform.audit import (
    add_operation_audit,
    edit_time_text,
    latest_operation_audit,
    records_by_edit_time,
    repoint_operation_audits,
)
from ..platform.identity import (
    denied_standard_item_ids,
    has_function_permission,
    project_for_report,
    project_step_error,
    standard_is_authorized,
    standard_matches_department,
    user_has_org_wide_scope,
    user_has_project_step,
    validate_project_department,
    validate_project_selection,
)
from ..platform.workflow import (
    REPORT_LIST_VIEW_PERMISSIONS,
    report_matches_view,
    report_projection,
)
from ..platform.file_vault import safe_content_type, safe_file_name
from ..project_workflow import advance_skipped_project_steps
from ..sample_entrust import normalize_sample_entrust_snapshot, stamp_sample_registrar, sample_client_from_detail, sample_party_error, persist_sample_contract_selection
from ..security import require_auth
from ..storage import StorageLimitExceeded
from ..workflow_dates import (
    business_date,
    business_today,
    latest_workflow_date,
    parse_date,
    validate_after_previous,
)

bp = Blueprint("reports", __name__, url_prefix="/api/reports")

def _legacy_allowed_actions(user, report):
    """Compatibility alias; ownership policy lives at the application boundary."""

    return report_allowed_actions(user, report)


def _sample_outbound_recall_allowed(user, report):
    """Mirror the outbound list's audit-aware recall projection."""

    from ..platform.workflow import sample_return_stock_blocker

    from ..data_entry_state import report_data_entry_started
    data_entry_started = report_data_entry_started(report)
    return bool(
        sample_return_stock_blocker(report, data_entry_started) is None
        and (
            has_full_platform_authority(user)
            or "sample.return_stock" in user.action_codes()
        )
    )

# 撤销（回退一步）：动作 → (要求当前状态, 撤销后状态)
# 兼容旧“撤销校核”权限码：现表示撤销检测录入完成，待审核→检测录入中。
# 撤销审核完成：待批准→待审核；撤销批准完成：待打印→待批准。
# R6 补齐：撤销评审（待样品入库→待合同评审，样品必须仍待入库）、撤销打印、撤销发放（样品回库）
def _scope_filter(query, user):
    """按数据授权范围过滤报告。department 模式支持跨部门（多个授权部门）。"""
    return scoped_report_query(query, user)


def report_content_editable(report):
    """报告内容只能由检测人员在数据录入或数据更改节点修改。"""
    return application_report_content_editable(report)


def _numbering_scheme_identity(report, detail=None):
    source = detail if isinstance(detail, dict) else (report.detail or {})
    raw_sample = source.get("rawSample") or {}
    scheme_code = str(raw_sample.get("schemeCode") or "").strip().upper()
    center_prefix = str(raw_sample.get("centerPrefix") or "").strip().upper()
    scheme_name = str(raw_sample.get("schemeName") or "").strip()
    if not scheme_code:
        for number in (report.sample_no, report.report_no):
            match = re.search(r"(?:^|-)\d{4}([A-Z0-9]+)-", str(number or "").upper())
            if match:
                scheme_code = match.group(1)
                break
    if not center_prefix:
        match = re.match(r"^([A-Z0-9]+)-", str(report.report_no or "").upper())
        if match:
            center_prefix = match.group(1)
    return scheme_code, center_prefix, scheme_name


def _preserve_numbering_scheme(report, detail):
    """编号生成后锁定检测方案编号；报告标题前缀可独立调整。"""
    if getattr(report, "main_report_no", None) or (report.detail or {}).get("derivedFrom"):
        from ..derived_registration import lock_source_scheme
        error = lock_source_scheme(report, detail)
        if error:
            return error
    original_code, original_center, original_name = _numbering_scheme_identity(report)
    requested_code, requested_center, _ = _numbering_scheme_identity(report, detail)
    if original_code and requested_code and requested_code != original_code:
        return f"报告编号已生成，检测方案编号类别已锁定为 {original_code}，不能改为 {requested_code}"
    raw_sample = dict(detail.get("rawSample") or {})
    if original_code:
        raw_sample["schemeCode"] = original_code
    if not requested_center and original_center:
        raw_sample["centerPrefix"] = original_center
    elif requested_center:
        raw_sample["centerPrefix"] = requested_center
    if original_name:
        raw_sample["schemeName"] = original_name
    detail["rawSample"] = raw_sample
    return None


def _apply_report_prefix_change(report, detail):
    """只变更报告标题前缀，保留样品号及已占用的流水序号。"""
    scheme_error = _preserve_numbering_scheme(report, detail)
    if scheme_error:
        return scheme_error

    # 样品编号及其中的方案类别、流水号一经生成即不可修改。
    from ..sample_identity import sample_number
    fixed_sample_no = sample_number(report)
    raw_sample = dict(detail.get("rawSample") or {})
    if fixed_sample_no:
        raw_sample["sampleNo"] = fixed_sample_no
        for section in detail.get("summary") or []:
            section["fields"] = [
                [key, fixed_sample_no if key in {"样品编号", "样品/抽样单编号"} else value]
                for key, value in section.get("fields") or []
            ]
    detail["rawSample"] = raw_sample

    _, original_center, _ = _numbering_scheme_identity(report)
    _, requested_center, _ = _numbering_scheme_identity(report, detail)
    requested_center = requested_center or original_center
    if not requested_center or requested_center == original_center:
        raw_sample["reportNo"] = report.report_no
        return None
    if not re.fullmatch(r"[A-Z0-9]{1,20}", requested_center):
        return "报告标题前缀只能使用 1—20 位大写字母或数字"
    if not report.sample_no:
        return "当前记录缺少固定样品编号，不能修改报告标题前缀"

    # A title change must retain the report suffix, independently of sample identity.
    report_tail = report.report_no.split("-", 1)[-1]
    new_report_no = f"{requested_center}-{report_tail}"
    if len(new_report_no) > 40:
        return "修改后的报告编号过长"
    duplicate = Report.query.filter(
        Report.report_no == new_report_no,
        Report.id != report.id,
    ).first()
    if duplicate:
        return f"报告编号 {new_report_no} 已存在，请选择其他报告标题"

    # The shared before_flush hook moves all current links atomically, including
    # Erp tasks, signature records and derived-report source references.
    report.report_no = new_report_no
    raw_sample["reportNo"] = new_report_no
    return None


def _has_report_access(user):
    """功能权限闸：是否持有任一报告模块权限点。数据范围 ≠ 功能权限，二者双门禁。"""
    return has_report_feature_access(user)


# 报告列表必须绑定实际进入的业务模块。查询模块可以查看数据范围内的全部状态；
# 办理模块只返回当前节点记录，以及按既有撤回规则允许本账号撤回的下一节点记录。
def _report_list_view_allowed(user, view):
    permission = REPORT_LIST_VIEW_PERMISSIONS.get(view)
    if not permission:
        return False
    return (
        has_full_platform_authority(user)
        or (view == "query" and can_correct_business_data(user))
        or permission in user.permission_codes()
    )


def _report_row_matches_list_view(row, view):
    return report_matches_view(row, view)


def _stored_report_type(report):
    detail = report.detail or {}
    raw_sample = detail.get("rawSample") or {}
    if str(raw_sample.get("reportType") or "").strip():
        return str(raw_sample["reportType"]).strip()
    for section in detail.get("summary") or []:
        if section.get("title") != "送样信息":
            continue
        for label, value in section.get("fields") or []:
            if label == "报告类型" and str(value or "").strip():
                return str(value).strip()
    return ""


def _split_combined_cover_pdf(pdf_bytes, part):
    """校准报告使用合并模板；独立预览时封面取第一页，首页取其余页。"""
    if part == "all":
        return pdf_bytes
    import fitz

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as source:
            if source.page_count < 2:
                return None
            output = fitz.open()
            if part == "cover":
                output.insert_pdf(source, from_page=0, to_page=0)
            else:
                output.insert_pdf(source, from_page=1, to_page=source.page_count - 1)
            data = output.tobytes()
            output.close()
            return data
    except Exception:
        return None


def _entrust_completed_date(entrust):
    return parse_date((entrust.info or {}).get("entrustDate"))


def _form_date(value):
    text = str(value or "").strip()
    return "" if text in ("", "—", "待填写", "待录入") else text


def _sample_detail_date(detail, raw_sample, raw_key, section, *labels):
    value = _form_date(raw_sample.get(raw_key))
    if raw_key in raw_sample:
        return value
    for label in labels:
        value = _form_date(_field(detail, section, label))
        if value:
            return value
    return ""


def _validate_sample_detail_dates(user, detail, entrust, *, require_send=False):
    from .technical_subprojects import canonical_detail
    canonical_financial_subprojects = lambda d, *a, **k: d
    try:
        normalized = canonical_detail(detail)
        normalized = canonical_financial_subprojects(normalized, entrust)
        from ..production_dates import canonical_detail as canonical_production_dates
        normalized = canonical_production_dates(normalized)
        from ..report_date_policy import synchronize_sample_date_summary
        normalized = synchronize_sample_date_summary(normalized)
    except ValueError as exc:
        return None, str(exc)
    source_raw_sample = normalized.get("rawSample")
    raw_sample = dict(source_raw_sample) if isinstance(source_raw_sample, dict) else {}
    # Business entrust date, not the time someone later completed registration.
    entrust_date = (parse_date((entrust.info or {}).get("entrustDate")) or _entrust_completed_date(entrust)) if entrust else None
    from ..report_date_policy import sample_date_values
    from ..report_date_rules import validate_date_order
    try:
        date_values = sample_date_values(normalized, entrust_date)
    except ValueError as error:
        return None, str(error)
    from ..report_date_policy import saved_business_dates
    date_values.update(saved_business_dates(normalized))
    error = validate_date_order(date_values)
    if error:
        return None, error
    for index, interval in enumerate((normalized.get("checkInput") or {}).get("testIntervals") or []):
        if not isinstance(interval, dict):
            return None, f"第 {index + 1} 个试验区间格式无效"
        error = validate_date_order({**date_values, "testStart": interval.get("start"), "testEnd": interval.get("end")})
        if error:
            return None, f"第 {index + 1} 个试验区间：{error}"

    send_value = _sample_detail_date(
        normalized, raw_sample, "sendDate", "送样信息", "送样日期",
    ) or _sample_detail_date(normalized, raw_sample, "sendDate", "样品信息", "送样日期")
    if require_send and not send_value:
        return None, "送样日期为必填"
    send_date = None
    if send_value:
        send_date = parse_date(send_value)
        if send_date is None:
            return None, "送样日期必须为有效日期"
        if "sendDate" in raw_sample:
            raw_sample["sendDate"] = send_date.isoformat()

    sample_time = _sample_detail_date(
        normalized, raw_sample, "sampleTime", "抽样信息", "抽样时间", "抽样日期",
    )
    if sample_time:
        if parse_date(sample_time) is None:
            return None, "抽样日期必须为有效日期"
        if "sampleTime" in raw_sample:
            raw_sample["sampleTime"] = parse_date(sample_time).isoformat()

    arrival_value = _sample_detail_date(
        normalized, raw_sample, "sampleArrivalDate", "抽样信息", "样品到达日期",
    )
    if arrival_value:
        error = validate_after_previous(
            user,
            arrival_value,
            send_date or entrust_date,
            "样品到达日期",
            "送样日期" if send_date else "委托登记",
        )
        if error:
            return None, error
        if "sampleArrivalDate" in raw_sample:
            raw_sample["sampleArrivalDate"] = parse_date(arrival_value).isoformat()

    produce_date = _sample_detail_date(
        normalized, raw_sample, "produceDate", "送样信息", "生产日期",
    )
    if produce_date and not raw_sample.get('productionDates'):
        from ..report_date_rules import production_date
        try:
            parsed_produce = production_date(produce_date)
        except ValueError:
            return None, "生产日期须为有效年月或日期（YYYY-MM 或 YYYY-MM-DD）"
        if "produceDate" in raw_sample:
            raw_sample["produceDate"] = parsed_produce

    promise_previous = send_date or entrust_date
    promise_previous_label = "送样日期" if send_date else "委托登记"
    for key, labels, field_label in (
        ("sendOutTime", ("报告承诺时间(外部)", "报告寄送(对外)"), "报告承诺时间(外部)"),
        ("sendInTime", ("报告承诺时间(内部)", "报告寄送(内部)"), "报告承诺时间(内部)"),
        ("innerStdDate", ("约定检测日期", "内业标准日期"), "约定检测日期"),
    ):
        value = _sample_detail_date(normalized, raw_sample, key, "报告发送", *labels)
        if not value:
            continue
        error = validate_after_previous(
            user, value, promise_previous, field_label, promise_previous_label,
        )
        if error:
            return None, error
        if key in raw_sample:
            raw_sample[key] = parse_date(value).isoformat()

    if "rawSample" in normalized:
        normalized["rawSample"] = raw_sample
    return normalized, None


def _sample_pickup_date(report):
    pickup_date = parse_date(
        ((report.detail or {}).get("workflowDates") or {}).get("samplePickupAt"),
    ) or parse_date((report.sample_pickup or {}).get("pickupTime"))
    return pickup_date


def _validated_test_dates(user, report, test_start, test_end):
    from ..applications.testing_records.commands import _test_date_error
    error = _test_date_error(user, report, test_start, test_end)
    if error:
        return None, None, error
    return parse_date(test_start).isoformat(), parse_date(test_end).isoformat(), None



def _next_report_no(prefix):
    """Allocate report + sample numbers from the durable category sequence."""
    from ..platform.numbering import allocate_report_numbers
    return allocate_report_numbers(prefix)


@bp.post("/create")
@require_auth
def create():
    """新建检测业务：委托与样品信息落库后进入合同评审（规格 2.2-2.5）。"""
    user = g.current_user
    permissions = user.permission_codes()
    if "entrust.sample_register.view" not in permissions and "report.report_check.view" not in permissions:
        return jsonify({"code": 403, "message": "无样品登记权限", "data": None}), 200
    body = request.get_json(silent=True) or {}
    reg_state = str(body.get("regState") or "登记完成").strip()
    if reg_state not in ("登记中", "登记完成"):
        return jsonify({"code": 1, "message": "样品登记状态无效", "data": None}), 200
    if (
        reg_state == "登记完成"
        and "entrust.sample_register.view" not in permissions
        and "report.report_check.view" not in permissions
        and "sample.register.complete" not in user.action_codes()
    ):
        return jsonify({"code": 403, "message": "无完成样品登记权限", "data": None}), 200
    # R6-AC2：委托登记完成后才可流转样品登记（上一环未完成拦截）
    entrust_no_in = (body.get("entrustNo") or "").strip()
    if not entrust_no_in:
        return jsonify({"code": 1, "message": "请先选择已完成登记的委托单", "data": None}), 200
    from ..platform.workflow import entrust_can_add_sample
    ent = Entrust.query.filter_by(entrust_no=entrust_no_in).first()
    if not ent:
        return jsonify({"code": 1, "message": f"委托单 {entrust_no_in} 不存在", "data": None}), 200
    blocker = entrust_can_add_sample(ent)
    if blocker:
        return jsonify({"code": 1, "message": blocker, "data": None}), 200
    report_category = (body.get("reportCategory") or "").strip()
    report_no = (body.get("reportNo") or "").strip()
    # 普通报告：前端只给前缀（检测中心-年方案编号，如 LAB-2026ASHP），后端按同前缀顺序自动分配序号（4 位补零）
    prefix = (body.get("reportNoPrefix") or "").strip()
    # 普通样品只接受后端分配的正式编号；客户端不能指定或复用旧号。
    auto_number = bool(prefix) and report_category in ("", "普通")
    if auto_number:
        try:
            from ..numbering import report_number_stem
            report_number_stem(prefix)  # Validate format without reserving a serial.
        except ValueError as error:
            return jsonify({"code": 1, "message": str(error), "data": None}), 200
    if not report_no and not auto_number:
        return jsonify({"code": 1, "message": "报告编号必填", "data": None}), 200
    if not auto_number and Report.query.filter_by(report_no=report_no).first():
        return jsonify({"code": 1, "message": "报告编号已存在", "data": None}), 200
    # 样品编号 = 报告编号去掉前面的检测中心编号（如 LAB-2026ASHP-0002 → 2026ASHP-0002）
    sample_no = (body.get("sampleNo") or "").strip() or (
        report_no.split("-", 1)[1] if "-" in report_no else report_no
    )
    # 补充/英文/分项报告：基于一份已有报告派生，继承其委托+样品+报告信息（新填字段覆盖继承）
    base_no = (body.get("baseReportNo") or "").strip()
    base = _scope_filter(Report.query, user).filter_by(report_no=base_no).first() if base_no else None
    if base_no and (base is None or base.voided):
        return jsonify({"code": 1, "message": "原报告不存在、已作废或不在数据范围内", "data": None}), 200
    kind_by_category = {"补充": "supplement", "英文": "english", "分项": "itemized"}
    derived_kind = kind_by_category.get(report_category, "main")
    derived_suffix = ""
    if derived_kind != "main":
        if not base:
            return jsonify({"code": 1, "message": "派生报告必须选择有效主报告", "data": None}), 200
        base = _main_report(base)
        if base.voided or not _scope_filter(Report.query, user).filter_by(id=base.id).first():
            return jsonify({"code": 1, "message": "主报告已作废或不在数据范围内", "data": None}), 200
        custom_suffix = report_no[len(base.report_no) + 1:] if derived_kind == "itemized" and report_no.startswith(f"{base.report_no}-") else ""
        try:
            expected_no, derived_suffix = _derived_report_no(base.report_no, derived_kind, custom_suffix)
        except ValueError as exc:
            return jsonify({"code": 1, "message": str(exc), "data": None}), 200
        if report_no != expected_no:
            return jsonify({"code": 1, "message": f"派生报告编号必须为 {expected_no}", "data": None}), 200
    detail = dict(body.get("detail") or {})
    from ..sample_form_merge import normalize_judgment_entries
    try:
        normalize_judgment_entries(detail)
    except ValueError as exc:
        return jsonify(code=1, message=str(exc), data=None), 200
    # The document-content endpoint exclusively owns per-report rendering policy.
    detail.pop('reportComposition', None)
    if base:
        from ..sample_form_merge import merge_sample_form
        from ..derived_registration import lock_source_scheme
        if base.entrust_no and base.entrust_no != entrust_no_in:
            return jsonify({"code": 1, "message": "派生报告必须继承原报告的委托单，请重新选择原报告", "data": None}), 200
        if body.get("department") and body["department"] != base.department:
            return jsonify({"code": 1, "message": "派生报告的检测部门不能更改", "data": None}), 200
        detail = merge_sample_form(base.detail, detail)
        # A newly registered derivative needs its own contract review.
        detail.pop("contractReview", None)
        detail.pop("complianceResolution", None)
        detail.pop('reportComposition', None)
        scheme_error = lock_source_scheme(base, detail)
        if scheme_error:
            return jsonify({"code": 1, "message": scheme_error, "data": None}), 200
        body["department"] = base.department
        raw = detail.setdefault("rawSample", {})
        raw.update(reportCategory=report_category, baseReportNo=base.report_no)
        if report_category == "英文":
            raw["reportLanguage"] = "EN"
            detail["requiresContractReReview"] = True
        detail["derivedFrom"] = base.report_no
        detail["reportCategory"] = report_category
    detail = dict(detail)
    party_error = sample_party_error(detail, ent)
    if party_error:
        return jsonify({"code": 1, "message": party_error, "data": None}), 200
    detail["entrustSnapshot"] = normalize_sample_entrust_snapshot(
        detail.get("entrustSnapshot"), ent, select_contract=True,
    )
    detail = stamp_sample_registrar(detail, user)
    if reg_state == "登记完成":
        detail, validation_error = _validate_sample_registration_completion(
            user,
            detail,
            ent,
            project=body.get("project") or "",
            department=body.get("department") or "",
        )
    else:
        detail, validation_error = _validate_sample_detail_dates(
            user, detail, ent, require_send=False,
        )
        if not validation_error:
            completed_detail, completion_error = _validate_sample_registration_completion(
                user,
                detail,
                ent,
                project=body.get("project") or "",
                department=body.get("department") or "",
            )
            if not completion_error:
                detail = completed_detail
    if validation_error:
        return jsonify({"code": 1, "message": validation_error, "data": None}), 200
    price_error = sample_price_error(detail, derived=derived_kind != "main")
    if price_error:
        return jsonify({"code": 1, "message": price_error, "data": None}), 200
    # Rejected form input must not consume a number. Reserve only after all
    # validation passes, still before any business write; later DB failures
    # continue to retain the durable reservation and cannot reuse a number.
    if auto_number:
        report_no, sample_no = _next_report_no(prefix)
    elif derived_kind != "main":
        from ..sample_identity import sample_number
        sample_no = sample_number(base)
        if not sample_no:
            return jsonify({"code": 1, "message": "原报告缺少样品编号，请先核对原样品", "data": None}), 200
    if not detail.get("sampleRegisteredAt"):
        from datetime import date
        detail["sampleRegisteredAt"] = date.today().isoformat()
    # Persist allocated identities, never the frontend's pre-save placeholder.
    detail["rawSample"] = {
        **(detail.get("rawSample") or {}),
        "sampleNo": sample_no,
        "reportNo": report_no,
    }
    # 把后端分配的真实样品编号回填进 detail（前端普通报告序号为自动占位）
    for sec in (detail.get("summary") or []):
        if sec.get("title") in ("送样信息", "样品信息", "抽样信息"):
            sec["fields"] = [([k, sample_no] if k in ("样品编号", "样品/抽样单编号") else [k, v]) for k, v in sec.get("fields", [])]
    r = Report(
        report_no=report_no,
        sample_no=sample_no,
        project=body.get("project"),
        project_name=detail["entrustSnapshot"]["projectName"],
        client=detail["entrustSnapshot"]["client"],
        template=body.get("template") or "REPORT_TEMPLATE",
        version=body.get("version") or "V1.0",
        status="待合同评审",  # 委托/样品登记后先进入合同评审
        sign="主检已签",
        deadline=body.get("deadline") or "正常",
        department=body.get("department") or (base.department if base else None) or (user.department.name if user.department else ""),
        owner=body.get("owner") or user.name,
        detail=detail,
        sample_status="待合同评审",  # 合同评审通过后才变「待入库」，方可入库/出库
        entrust_no=entrust_no_in,  # 样品归属的委托单
        # R3 两步保存：regState=登记中(保存占号) / 登记完成(完成登记，默认，兼容既有一步式)
        sample_reg_state=reg_state,
        main_report_no=base.report_no if base and derived_kind != "main" else None,
        report_kind=derived_kind,
        report_suffix=derived_suffix,
    )
    db.session.add(r)
    db.session.flush()
    if base and derived_kind != "main":
        _copy_report_artifacts(base, r)
    persist_sample_contract_selection(r)
    from .report_publication import issue as issue_report_query
    issue_report_query(r)  # same registration transaction; not publicly released
    skipped_nodes = advance_skipped_project_steps(r)
    audit_action = (
        "sample.register.complete"
        if r.sample_reg_state == "登记完成"
        else "sample.register.save"
    )
    from ..report_date_policy import audit_sample_date_alignment
    audit_sample_date_alignment(r.report_no, body.get('detail') or {}, user)
    add_operation_audit(
        audit_action, "report", r.report_no, category="workflow", after=r.to_row(),
    )
    db.session.commit()
    from ..sample_preview_warmup import schedule_after_save
    schedule_after_save(r)
    message = "样品单已保存（登记中）" if reg_state == "登记中" else "样品登记已完成，进入合同评审"
    if skipped_nodes:
        message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
    return jsonify({"code": 0, "message": message, "data": r.to_row()})


@bp.post("/<report_no>/sample-reg")
@require_auth
def sample_reg(report_no):
    """R6 样品登记两态：complete 登记中→登记完成（进入合同评审待办）；uncomplete 反向（已评审流转则拦截）。"""
    user = g.current_user
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "样品单不存在或不在数据范围内", "data": None}), 200
    act = ((request.get_json(silent=True) or {}).get("action") or "").strip()
    if act == "complete":
        permissions = user.permission_codes()
        if (
            "entrust.sample_register.view" not in permissions
            and "report.report_check.view" not in permissions
            and "sample.register.complete" not in user.action_codes()
        ):
            return jsonify({"code": 403, "message": "无完成样品登记权限", "data": None}), 200
        if (r.sample_reg_state or "登记完成") == "登记完成":
            return jsonify({"code": 1, "message": "该样品单已是登记完成", "data": None}), 200
        if r.voided or (r.sample_reg_state or "") == "已作废":
            return jsonify({"code": 1, "message": "样品单已作废，不能完成登记", "data": None}), 200
        if r.status != "待合同评审":
            return jsonify({"code": 1, "message": f"报告已流转至「{r.status}」，不能完成样品登记", "data": None}), 200
        entrust = Entrust.query.filter_by(entrust_no=r.entrust_no).first() if r.entrust_no else None
        if not entrust:
            return jsonify({"code": 1, "message": "关联委托单不存在，不能完成样品登记", "data": None}), 200
        normalized_detail, validation_error = _validate_sample_registration_completion(
            user,
            r.detail or {},
            entrust,
            project=r.project or "",
            department=r.department or "",
        )
        if validation_error:
            return jsonify({"code": 1, "message": validation_error, "data": None}), 200
        price_error = sample_price_error(normalized_detail, report=r)
        if price_error:
            return jsonify({"code": 1, "message": price_error, "data": None}), 200
        before = r.to_row()
        from ..report_date_policy import audit_sample_date_alignment
        audit_sample_date_alignment(r.report_no, r.detail or {}, user)
        r.detail = stamp_sample_registrar(normalized_detail, user, previous=r.detail or {})
        r.sample_reg_state = "登记完成"
        skipped_nodes = advance_skipped_project_steps(r)
        add_operation_audit(
            "sample.register.complete", "report", r.report_no, category="workflow",
            before=before, after=r.to_row(),
        )
        db.session.commit()
        message = f"{r.report_no} 样品登记完成，进入合同评审待办"
        if skipped_nodes:
            message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
        return jsonify({"code": 0, "message": message, "data": r.to_row()})
    if act == "uncomplete":
        if "entrust.sample_register.view" not in user.permission_codes():
            return jsonify({"code": 403, "message": "无撤销样品登记权限", "data": None}), 200
        if r.status != "待合同评审":
            return jsonify({"code": 1, "message": f"报告已流转至「{r.status}」，不能撤销登记完成", "data": None}), 200
        before = r.to_row()
        r.sample_reg_state = "登记中"
        add_operation_audit(
            "sample.register.undo", "report", r.report_no, category="workflow",
            before=before, after=r.to_row(),
        )
        db.session.commit()
        return jsonify({"code": 0, "message": f"{r.report_no} 已撤销登记完成，可继续修改", "data": r.to_row()})
    return jsonify({"code": 1, "message": "未知动作", "data": None}), 200


DERIVATIVE_KIND_LABELS = {
    "supplement": "补充报告",
    "english": "英文报告",
    "itemized": "分项报告",
    "correction": "更正报告",
}
DERIVATIVE_FIXED_SUFFIXES = {
    "supplement": "BC",
    "english": "(E)",
    "correction": "GZ",
}


def _main_report(report):
    main_no = str(report.main_report_no or report.report_no or "").strip()
    return Report.query.filter_by(report_no=main_no).first() or report


def _derived_report_no(main_no, kind, custom_suffix=""):
    if kind in DERIVATIVE_FIXED_SUFFIXES:
        return f"{main_no}{DERIVATIVE_FIXED_SUFFIXES[kind]}", DERIVATIVE_FIXED_SUFFIXES[kind]
    if kind != "itemized":
        raise ValueError("派生报告类型无效")
    suffix = str(custom_suffix or "").strip().lstrip("-")
    if not suffix:
        raise ValueError("请填写分项报告后缀")
    if len(suffix) > 20 or not re.fullmatch(r"[\w\u4e00-\u9fff.-]+", suffix, flags=re.UNICODE):
        raise ValueError("分项后缀限20字，仅支持中文、字母、数字、点、下划线和短横线")
    return f"{main_no}-{suffix}", suffix


def _copy_report_artifacts(source, target):
    content = ReportDocumentContent.query.filter_by(report_no=source.report_no).first()
    if content:
        db.session.add(ReportDocumentContent(
            report_no=target.report_no,
            profile_code=content.profile_code,
            result_groups=copy.deepcopy(content.result_groups or []),
            remarks=content.remarks,
            photos=copy.deepcopy(content.photos or []),
            extra_pages=copy.deepcopy(content.extra_pages or []),
            updated_by=target.owner,
        ))
    # 正式版本和签署版必须在新编号下重新生成；只复制业务附件，排除历史系统封面。
    allowed_sources = {"报告后续页", "原始记录", "其他附件"}
    for attachment in ReportAttachment.query.filter_by(
        report_no=source.report_no, deleted_at=None
    ).order_by(ReportAttachment.id).all():
        if attachment.source not in allowed_sources:
            continue
        db.session.add(ReportAttachment(
            report_no=target.report_no,
            name=attachment.name,
            content_type=attachment.content_type,
            kind=attachment.kind,
            source=attachment.source,
            status="复制自主报告",
            file_id=attachment.file_id,
            data=attachment.data if not attachment.file_id else None,
            uploaded_by=target.owner,
        ))


def _clone_derived_report(main, report_no, kind, suffix, actor, *, return_mode=""):
    from ..sample_identity import sample_number
    detail = copy.deepcopy(main.detail or {})
    if isinstance(detail.get('reportComposition'), dict):
        detail['reportComposition'].pop('preserveUploadedReport', None)
    detail["derivedFrom"] = main.report_no
    detail["mainReportNo"] = main.report_no
    detail["reportCategory"] = DERIVATIVE_KIND_LABELS[kind]
    detail["reportKind"] = kind
    detail["reportSuffix"] = suffix
    signatures = dict(detail.get("signatures") or {})
    signatures.pop("审核", None)
    signatures.pop("批准", None)
    detail["signatures"] = signatures
    status = "待校核"
    if kind == "correction":
        plan = return_plan("report.approval.return", return_mode)
        plan.update({
            "sourceAction": "report.correction.approved",
            "sourceStatus": main.status,
            "preservedSampleStatus": main.sample_status or "已领取",
            "createdAt": business_today().isoformat(),
            "createdBy": actor.account,
        })
        detail["changeRound"] = True
        detail["returnPlan"] = plan
        detail["returnInfo"] = {
            "source": "更正申请审批通过",
            "by": actor.name or actor.account,
            "date": business_today().isoformat(),
            "note": detail.get("correctionReason") or "",
            "mode": plan["mode"],
            "target": plan["targetLabel"],
        }
        status = "委托更改中" if plan["mode"] in {"entrust_only", "entrust_and_data"} else "检测更改中"
    target = Report(
        report_no=report_no,
        sample_no=sample_number(main),
        project=main.project,
        project_name=main.project_name,
        client=main.client,
        template=main.template,
        version=main.version,
        status=status,
        sign="",
        deadline=main.deadline,
        department=main.department,
        owner=actor.name or actor.account,
        detail=detail,
        out_of_scope=main.out_of_scope,
        out_of_scope_note=main.out_of_scope_note,
        sample_status=main.sample_status,
        sample_pickup=copy.deepcopy(main.sample_pickup),
        entrust_no=main.entrust_no,
        stamped=False,
        sample_reg_state="登记完成",
        archive_state="",
        voided=False,
        main_report_no=main.report_no,
        report_kind=kind,
        report_suffix=suffix,
    )
    db.session.add(target)
    db.session.flush()
    _copy_report_artifacts(main, target)
    return target


def _correction_page_access(user):
    return has_full_platform_authority(user) or "report.change_request.view" in user.permission_codes()


@bp.post("/<report_no>/correction-requests")
@require_auth
def create_correction_request(report_no):
    user = g.current_user
    if not _correction_page_access(user) or "report.change.request" not in user.action_codes():
        return jsonify({"code": 403, "message": "无报告更正申请权限", "data": None}), 200
    source = _scope_filter(Report.query, user).filter(Report.report_no == report_no).with_for_update().first()
    if not source:
        return jsonify({"code": 1, "message": "主报告不存在或不在数据范围内", "data": None}), 200
    main = _main_report(source)
    if main.report_no != source.report_no:
        return jsonify({"code": 1, "message": "更正申请必须针对主报告发起", "data": None}), 200
    if main.status not in ("待打印", "待发放", "已发放") and (main.archive_state or "") != "归档完成":
        return jsonify({"code": 1, "message": "仅签发流程开始后或已归档的主报告可申请更正", "data": None}), 200
    existing_gz = Report.query.filter_by(report_no=f"{main.report_no}GZ").first()
    if existing_gz and not (existing_gz.report_kind == 'correction_history'
                           and request.form.get('correctionType') == 'internal'):
        return jsonify({"code": 1, "message": "该主报告已存在 GZ 更正报告", "data": None}), 200
    from ..internal_report_corrections import blocks_new_request
    active = ReportCorrectionRequest.query.filter(
        ReportCorrectionRequest.main_report_no == main.report_no,
        ReportCorrectionRequest.status.in_(("pending_approval", "pending_director", "pending_leader", "approved")),
    ).all()
    if any(blocks_new_request(item, main) for item in active):
        return jsonify({"code": 1, "message": "该主报告已有进行中的更正申请", "data": None}), 200
    reason = str(request.form.get("reason") or "").strip()
    return_mode = str(request.form.get("returnMode") or "").strip()
    if not reason:
        return jsonify({"code": 1, "message": "请填写更正原因", "data": None}), 200
    if return_mode not in {"entrust_only", "data_only", "entrust_and_data"}:
        return jsonify({"code": 1, "message": "请选择更改委托、检测数据或两者都改", "data": None}), 200
    correction_type = str(request.form.get("correctionType") or "").strip()
    if correction_type not in {"internal", "external"}:
        return jsonify(code=1, message="请选择内部更正或外部更正", data=None), 200
    required = [("internalFile", "内部签字文件（偏离许可）")]
    if correction_type == "external":
        required.append(("receiptFile", "甲方回执／确认文件"))
    # Validate every upload before persisting either file.
    validated = []
    max_bytes = int(current_app.config.get("MAX_FILE_BYTES", 30 * 1024 * 1024))
    types = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
             "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    for key, label in required:
        uploaded = request.files.get(key)
        if not uploaded or not uploaded.filename:
            return jsonify(code=1, message=f"必须上传{label}", data=None), 200
        name = safe_file_name(uploaded.filename, max_length=200)
        extension = name.rsplit(".", 1)[-1].lower()
        if extension not in types:
            return jsonify(code=1, message=f"{label}仅支持 PDF、PNG、JPG、Word", data=None), 200
        raw = uploaded.stream.read(max_bytes + 1)
        if not raw or len(raw) > max_bytes:
            return jsonify(code=1, message=f"{label}不能为空且不能超过 {max_bytes // (1024 * 1024)} MB", data=None), 200
        validated.append((name, raw, types[extension], label, extension))
    try:
        attachments = []
        for name, raw, content_type, label, extension in validated:
            attachments.append(persist_report_attachment(
                main, raw, category="correction_application", name=name,
                content_type=content_type,
                kind="PDF" if extension == "pdf" else "Word" if extension in {"doc", "docx"} else "图片",
                source=label, status="待审批",
                uploaded_by=user.name or user.account, created_by=user.name or user.account,
                max_bytes=max_bytes,
            ))
        row = ReportCorrectionRequest(
            main_report_no=main.report_no,
            return_mode=return_mode,
            reason=reason,
            application_attachment_id=attachments[0].id,
            receipt_attachment_id=attachments[1].id if len(attachments) > 1 else None,
            correction_type=correction_type,
            status="pending_director",
            applicant_account=user.account,
            applicant_name=user.name or user.account,
            department=main.department or (user.department.name if user.department else ""),
        )
        db.session.add(row)
        db.session.flush()
        add_operation_audit(
            "report.correction.request", "report", main.report_no, category="workflow",
            after=row.to_dict(), message=reason, actor=user,
        )
        db.session.commit()
    except StorageLimitExceeded:
        db.session.rollback()
        return jsonify({"code": 1, "message": "更正附件超过允许大小", "data": None}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("create correction request failed")
        return jsonify({"code": 1, "message": "更正申请保存失败", "data": None}), 500
    return jsonify({"code": 0, "message": "更正申请已提交，等待一审", "data": row.to_dict()})


def _correction_projection(row, user):
    data = row.to_dict()
    from ..internal_report_corrections import blocks_new_request, history_for
    from ..report_correction_permissions import authorization_payload
    data['blocksNewRequest'] = blocks_new_request(row)
    data['hasHistory'] = history_for(row.id) is not None
    if row.status == "pending_approval":
        data["status"] = "pending_director"
    data.update(canApproveDirector=False, canApproveLeader=False)
    if data["status"] not in {"pending_director", "pending_leader"} or not _correction_page_access(user):
        return data
    grants = authorization_payload(user)
    same_department = bool(user.department and user.department.name == row.department)
    data["canApproveDirector"] = (data["status"] == "pending_director" and
        grants["correctionApprovalLevel1"] and same_department)
    data["canApproveLeader"] = (data["status"] == "pending_leader" and
        grants["correctionApprovalLevel2"] and
        (row.director_account or "").casefold() != user.account.casefold())
    return data


@bp.get("/correction-requests")
@require_auth
def correction_request_inbox():
    user = g.current_user
    if not _correction_page_access(user):
        return jsonify(code=403, message="无报告更改申请页面权限", data=None), 200
    scoped_numbers = _scope_filter(Report.query, user).with_entities(Report.report_no)
    rows = ReportCorrectionRequest.query.filter(
        ReportCorrectionRequest.main_report_no.in_(scoped_numbers)
    ).order_by(ReportCorrectionRequest.id.desc()).all()
    return jsonify(code=0, message="ok", data={"rows": [_correction_projection(row, user) for row in rows]})


@bp.get("/<report_no>/correction-requests")
@require_auth
def correction_requests(report_no):
    user = g.current_user
    if not _correction_page_access(user):
        return jsonify(code=403, message="无报告更改申请页面权限", data=None), 200
    source = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not source:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    main = _main_report(source)
    rows = ReportCorrectionRequest.query.filter_by(main_report_no=main.report_no).order_by(
        ReportCorrectionRequest.id.desc()
    ).all()
    return jsonify({"code": 0, "message": "ok", "data": {"rows": [_correction_projection(row, user) for row in rows]}})


@bp.post("/correction-requests/<int:request_id>/decision")
@require_auth
def decide_correction_request(request_id):
    user = g.current_user
    row = db.session.get(ReportCorrectionRequest, request_id)
    if not row:
        return jsonify({"code": 1, "message": "更正申请不存在", "data": None}), 200
    main = _scope_filter(Report.query, user).filter(Report.report_no == row.main_report_no).first()
    if not main:
        return jsonify({"code": 1, "message": "主报告不存在或不在数据范围内", "data": None}), 200
    projection = _correction_projection(row, user)
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision") or "").strip()
    note = str(body.get("note") or "").strip()
    if decision not in {"approve", "reject"}:
        return jsonify({"code": 1, "message": "审批决定无效", "data": None}), 200
    stage = projection["status"]
    if stage not in {"pending_director", "pending_leader"}:
        return jsonify(code=1, message="该申请已处理，不能重复审批", data=None), 200
    if body.get("stage") != stage:
        return jsonify(code=1, message="申请环节已变化，请刷新后核对", data=None), 200
    if stage == "pending_director" and not projection["canApproveDirector"]:
        return jsonify(code=403, message="一审须由有报告更改第一级权限的本部门人员办理", data=None), 200
    if stage == "pending_leader" and not projection["canApproveLeader"]:
        return jsonify(code=403, message="二审须由有报告更改第二级权限且未办理本次一审的人员办理", data=None), 200
    if decision == "reject" and not note:
        return jsonify(code=1, message="请填写驳回原因", data=None), 200
    if decision == "approve":
        attachments = [row.application_attachment]
        if row.correction_type == "external":
            attachments.append(row.receipt_attachment)
        if any(not item or item.deleted_at for item in attachments):
            return jsonify(code=1, message="申请附件缺失，不能审批", data=None), 200
    if stage == "pending_leader" and decision == "approve":
        main = Report.query.filter_by(id=main.id).with_for_update().populate_existing().one()
        if main.status not in {"待打印", "待发放", "已发放"} and main.archive_state != "归档完成":
            db.session.rollback()
            return jsonify(code=1, message="原报告状态已变化，请刷新后重新核对", data=None), 200
    now = datetime.utcnow()
    before = row.to_dict()
    claimed = ReportCorrectionRequest.query.filter_by(id=row.id, status=row.status).update(
        {"status": "processing"}, synchronize_session=False)
    if claimed != 1:
        db.session.rollback()
        return jsonify(code=1, message="申请状态已变化，请刷新后核对", data=None), 200
    if stage == "pending_director":
        row.director_account = user.account
        row.director_name = user.name or user.account
        row.director_note = note
        row.director_at = now
        row.status = "pending_leader" if decision == "approve" else "rejected"
    else:
        row.leader_account = user.account
        row.leader_name = user.name or user.account
        row.leader_note = note
        row.leader_at = now
        row.status = "rejected" if decision == "reject" else "approved"
    try:
        if row.status == "approved" and row.correction_type == 'internal':
            from ..internal_report_corrections import begin_internal_correction
            begin_internal_correction(main, row, user)
        elif row.status == "approved":
            correction_no, suffix = _derived_report_no(main.report_no, "correction")
            if Report.query.filter_by(report_no=correction_no).first():
                db.session.rollback()
                return jsonify(code=1, message=f"报告编号 {correction_no} 已存在", data=None), 200
            target = _clone_derived_report(main, correction_no, "correction", suffix, user, return_mode=row.return_mode)
            detail = dict(target.detail or {})
            detail["correctionRequestId"] = row.id
            detail["correctionReason"] = row.reason
            from ..report_correction_dates import freeze_original_date
            detail['correctionOriginalIssueDate'] = freeze_original_date(main, row.id)
            return_info = dict(detail.get("returnInfo") or {})
            return_info["note"] = row.reason
            detail["returnInfo"] = return_info
            target.detail = detail
            row.correction_report_no = correction_no
        db.session.flush()
        add_operation_audit(
            "report.correction.decision", "report", main.report_no, category="workflow",
            before=before, after=row.to_dict(), message=note, actor=user,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("decide correction request failed")
        return jsonify({"code": 1, "message": "更正审批保存失败", "data": None}), 500
    message = "更正申请已驳回，可重新申请" if row.status == "rejected" else (
        (f"审批完成，{row.main_report_no} 沿用原编号进入更改，旧版已留存历史" if row.correction_type == 'internal'
         else f"审批完成，已创建 {row.correction_report_no}") if row.status == "approved" else "一审已通过，等待二审"
    )
    return jsonify({"code": 0, "message": message, "data": _correction_projection(row, user)})


def _authorized_correction_history(request_id):
    from ..internal_report_corrections import history_for
    row = db.session.get(ReportCorrectionRequest, request_id)
    if (not row or not _correction_page_access(g.current_user) or not
            _scope_filter(Report.query, g.current_user).filter_by(report_no=row.main_report_no).first()):
        return None
    return history_for(request_id)


@bp.get('/correction-requests/<int:request_id>/history')
@require_auth
def correction_history(request_id):
    audit = _authorized_correction_history(request_id)
    if not audit:
        return jsonify(code=1, message='历史记录不存在或无权查看', data=None), 404
    return jsonify(code=0, message='ok', data=audit.before_data)


@bp.get('/correction-requests/<int:request_id>/history/<kind>/<int:identity>/pdf')
@require_auth
def correction_history_pdf(request_id, kind, identity):
    from io import BytesIO
    from flask import send_file
    from ..internal_report_corrections import history_pdf
    audit = _authorized_correction_history(request_id)
    if not audit:
        return jsonify(code=1, message='历史记录不存在或无权查看', data=None), 404
    if kind == 'signed':
        return jsonify(code=410, message='历史签署文件仅保留审计，不再提供此处下载；请到报告签发、报告查询或报告发放下载当前签字盖章版', data=None), 410
    try:
        raw = history_pdf(audit, kind, identity)
    except ValueError as exc:
        return jsonify(code=1, message=str(exc), data=None), 400
    response = send_file(BytesIO(raw), mimetype='application/pdf', as_attachment=True,
                         download_name=f'{audit.before_data["report"]["reportNo"]}-history-{kind}-{identity}.pdf')
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@bp.post("/derivable")
@require_auth
def derivable():
    """分页选择来源；分项和英文报告可使用数据范围内已有样品。"""
    user = g.current_user
    if not _has_report_access(user) and "entrust.sample_register.view" not in user.permission_codes():
        return jsonify({"code": 403, "message": "无报告查看权限", "data": None}), 200
    from sqlalchemy import or_
    from sqlalchemy.orm import load_only
    body = request.get_json(silent=True) or {}
    try:
        page = max(1, int(body.get("page") or 1))
        size = min(50, max(1, int(body.get("size") or 20)))
    except (TypeError, ValueError):
        return jsonify({"code": 1, "message": "分页参数无效", "data": None}), 200
    query = _scope_filter(Report.query, user).filter(Report.voided.is_(False))
    keyword = str(body.get("keyword") or "").strip()[:200]
    if keyword:
        query = query.filter(or_(*[column.contains(keyword, autoescape=True) for column in (
            Report.sample_no, Report.report_no, Report.project_name, Report.client)]))
    if body.get("category") in ("分项", "英文"):
        if body.get("category") == "英文":
            from sqlalchemy import func
            query = query.filter(func.trim(Report.sample_no) != "")
        total = query.count()
        query = query.order_by(Report.id.desc()).offset((page - 1) * size).limit(size)
    else:
        # detail is portable TEXT JSON, not a native JSON column. Preserve the
        # existing supplement eligibility without dialect-specific SQL
        # or loading every full Report/audit into memory.
        selected_ids, total = [], 0
        for report_id, detail in query.with_entities(Report.id, Report.detail).order_by(Report.id.desc()).yield_per(100):
            if not ((detail or {}).get("checkInput") or {}).get("standard"):
                continue
            if (page - 1) * size <= total < page * size:
                selected_ids.append(report_id)
            total += 1
        query = query.filter(Report.id.in_(selected_ids)).order_by(Report.id.desc())
    rows = query.options(load_only(Report.report_no, Report.main_report_no, Report.sample_no,
        Report.client, Report.project_name, Report.project, Report.status)).all()
    from ..sample_identity import sample_number
    out = [{"reportNo": r.report_no, "mainReportNo": r.main_report_no or r.report_no,
            "client": r.client, "projectName": r.project_name, "sampleNo": sample_number(r),
            "project": r.project, "status": r.status} for r in rows]
    return jsonify({"code": 0, "message": "ok", "data": {"rows": out,
        "total": total, "page": page, "size": size}})


@bp.post("/cover-preview")
@require_auth
def cover_preview():
    """样品录入阶段预览报告封面：按 检测中心×报告类型 选模板，用当前表单信息填充，返回 docx。"""
    from types import SimpleNamespace

    from flask import Response

    from ..cover_render import build_cover_parts, cover_preview_html
    from ..docx_pdf import docx_list_to_pdf
    body = request.get_json(silent=True) or {}
    prefix = (body.get("centerPrefix") or "LAB").strip()
    rt = (body.get("reportType") or "产品报告").strip()
    def gv(k):
        value = body.get(k)
        return value.strip() if isinstance(value, str) else ""
    trademark = gv("trademark") or gv("brand")
    detail = {"trademarkImage": gv("trademarkImage"), "summary": [
        {"title": "委托信息", "fields": [["委托单位", gv("client")], ["工程名称", gv("projectName")],
                                       ["委托日期", gv("entrustDate")], ["盖章要求", gv("seal")]]},
        {"title": "送样信息", "fields": [["样品编号", gv("sampleNo")], ["样品名称", gv("sampleName")],
                                       ["报告类型", rt], ["规格型号", gv("spec")], ["生产厂家", gv("manufacturer")],
                                       ["送样日期", gv("sendDate")], ["检测类别", gv("testCategory")],
                                       ["检测地点", gv("testLocation")], ["样品数量", gv("sampleAmount")],
                                       ["出厂编号", gv("factoryNo")], ["生产日期", gv("produceDate")], ["商标", trademark]]},
        {"title": "实验信息", "fields": [["检测项目", gv("project")], ["检测依据", gv("testBasis")],
                                       ["判定标准", gv("standardJudge") or gv("testBasis")],
                                       ["执行标准", gv("testBasis")], ["检测设备", ""], ["检测日期", ""]]},
        {"title": "原始记录", "fields": [["结论", ""]]},
    ]}
    scheme = (body.get("schemeCode") or "").strip()
    serial = (body.get("serial") or "0001").strip()
    report_no = f"{prefix}-{business_today().year}{scheme or 'R'}-{serial}"
    rep = SimpleNamespace(report_no=report_no, sample_no=gv("sampleNo") or report_no.split("-", 1)[-1],
                          client=gv("client"), project=gv("project"), project_name=gv("projectName"),
                          detail=detail, out_of_scope=False, stamped=False, status="待校核")
    # 首选：封面/首页各自与模板一比一填充 → 分别转 PDF（WPS 优先）→ 合并预览；失败回退 HTML
    try:
        parts = build_cover_parts(rep)
        pdf = docx_list_to_pdf(parts) if parts else None
    except Exception:
        pdf = None
    if pdf:
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": "inline; filename=cover-preview.pdf"})
    return jsonify({"code": 0, "message": "ok", "data": {"html": cover_preview_html(rep)}})


@bp.get("/<report_no>/cover")
@require_auth
def report_cover(report_no):
    """对已存在报告渲染真实模板（封面+首页），按 detail 字段填充。?format=pdf 网页预览(默认)，docx 下载。"""
    from flask import Response

    from ..cover_render import (
        build_cover_from_template,
        build_cover_parts,
        cover_preview_html,
        cover_templates_are_combined,
    )
    from ..docx_pdf import docx_list_to_pdf
    user = g.current_user
    view = str(request.args.get("view") or "").strip()
    r, _projection, access_error = get_authorized_report_for_view(
        user, report_no, view
    )
    if access_error:
        code = 1 if access_error in {"报告详情入口无效", "报告不存在或不在数据范围内"} else 403
        return jsonify({"code": code, "message": access_error, "data": None}), 200
    fmt = (request.args.get("format") or "pdf").lower()
    part = (request.args.get("part") or "all").strip().lower()
    if part not in {"all", "cover", "homepage"}:
        return jsonify({"code": 1, "message": "预览类型无效，请选择报告封面或报告首页", "data": None}), 200
    if part != "all" and not _stored_report_type(r):
        return jsonify({"code": 1, "message": "样品未保存报告类型，无法生成独立预览", "data": None}), 200
    if fmt == "docx":
        if part != "all":
            return jsonify({"code": 1, "message": "报告封面和报告首页独立导出不在本次预览功能范围内", "data": None}), 200
        # Word 下载：docxcompose 合并封面+首页（保留双方样式/节设置，一比一）
        try:
            docx = build_cover_from_template(r)
        except Exception:
            docx = None
        if not docx:
            return jsonify({"code": 1, "message": "未匹配到模板", "data": None}), 200
        from urllib.parse import quote
        # 文件名含中文，HTTP 头必须 latin-1，用 RFC 5987（ASCII 兜底 + UTF-8 真名）
        disp = f"attachment; filename={report_no}-cover.docx; filename*=UTF-8''{quote(report_no + '-封面首页.docx')}"
        return Response(docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": disp})
    # PDF 预览：默认合并；样品登记页可按 part 独立预览封面或首页
    try:
        parts = build_cover_parts(r, part)
        pdf = docx_list_to_pdf(parts) if parts else None
    except Exception:
        parts = []
        pdf = None
    if part != "all" and not parts:
        label = "报告封面" if part == "cover" else "报告首页"
        return jsonify({"code": 1, "message": f"未匹配到{label}模板", "data": None}), 200
    if pdf and part != "all" and cover_templates_are_combined(r):
        pdf = _split_combined_cover_pdf(pdf, part)
        if not pdf:
            return jsonify({"code": 1, "message": "合并模板无法可靠拆分为报告封面和报告首页", "data": None}), 200
    if pdf:
        suffix = "cover" if part in {"all", "cover"} else "homepage"
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": f"inline; filename={report_no}-{suffix}.pdf"})
    # LibreOffice 不可用时回退 HTML 预览
    return jsonify({"code": 0, "message": "ok", "data": {"html": cover_preview_html(r, part)}})


# ---------- 基础库：标准库 / 检测方案库 / 检测项目库（样品录入时选择）----------

@bp.post("/lib/standards")
@require_auth
def lib_standards():
    from ..models import CapabilityEntry, Department, StdLibraryItem

    body = request.get_json(silent=True) or {}
    keyword = (body.get("keyword") or "").strip()
    query = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(db.or_(StdLibraryItem.code.ilike(like), StdLibraryItem.name.ilike(like)))
    department = g.current_user.department.name if g.current_user.department else ""
    denied = denied_standard_item_ids(g.current_user)
    from ..applications.quality_resources.testing_locations import workbook_capability_owners
    capability_owners = workbook_capability_owners()
    candidates = query.order_by(StdLibraryItem.id).limit(500).all()
    rows = []
    for item in candidates:
        data = item.to_row()
        if data["status"] != "现行":
            continue
        if item.id in denied or not standard_matches_department(item, department):
            continue
        if body.get("cmaOnly") and ("CMA" not in (item.auth_kind or "") or "一单一库" not in (item.auth_kind or "")):
            continue
        capabilities = (
            CapabilityEntry.query.filter_by(
                standard_item_id=capability_owners.get(item.id, item.id),
            )
            .all()
        )
        rows.append({
            "id": item.id, "code": item.code, "name": item.name, "qualKind": item.auth_kind or "",
            "category": item.category or "", "dept": "、".join(data["useDepts"]),
            "capabilityTypes": sorted({row.capability_type for row in capabilities}),
            "sites": sorted({row.site for row in capabilities}),
            "hasActiveCapability": bool(capabilities),
        })
        if len(rows) >= 60:
            break
    return jsonify({"code": 0, "message": "ok", "data": {"rows": rows}})


from ..list_reads import reuse_list_reads


@bp.post("/plan-counts")
@require_auth
@reuse_list_reads
def report_plan_counts():
    """Only count identities visible in the requested report module."""
    view=str((request.get_json(silent=True) or {}).get('view') or '')
    if view not in {'query','review','approval','print','archive','release'}:
        return jsonify(code=1,message='报告方案范围无效',data=None)
    user=g.current_user
    if not _report_list_view_allowed(user,view):
        return jsonify(code=403,message='无当前报告模块查看权限',data=None)
    from sqlalchemy import func
    from ..list_page_access import report_candidates
    from ..list_paging import j, first, scheme_fields, summary
    code,_name=scheme_fields()
    department=first(j(Report.detail,'rawSample.testDept'),summary('检测部门','检测科室'),Report.department)
    query=report_candidates(_scope_filter(Report.query,user),user,view)
    values=query.with_entities(Report.department.label('department'),department.label('test_department'),code.label('scheme_code')).subquery()
    rows=db.session.query(values.c.department,values.c.test_department,values.c.scheme_code,func.count()).group_by(values.c.department,values.c.test_department,values.c.scheme_code).all()
    return jsonify(code=0,message='ok',data={'rows':[
        dict(department=r[0],testDepartment=r[1],schemeCode=r[2],sampleCount=r[3]) for r in rows]})


@bp.post("/lib/schemes")
@require_auth
def lib_schemes():
    from ..library import schemes_tree
    kw = (request.get_json(silent=True) or {}).get("keyword", "")
    # 超级管理员负责维护和排查全院方案，不受本人所属部门限制；
    # 普通用户仍只能选择本部门方案。
    department = ""
    if not user_has_org_wide_scope(g.current_user):
        department = g.current_user.department.name if g.current_user.department else ""
    return jsonify({"code": 0, "message": "ok", "data": {"tree": schemes_tree(kw, department)}})


@bp.post("/lib/validate-sample")
@require_auth
def lib_validate_sample():
    """加入样品清单前校验方案、部门、标准及委托盖章资质范围。"""
    body = request.get_json(silent=True) or {}
    requested_department = (body.get("department") or "").strip()
    department = (
        requested_department
        if user_has_org_wide_scope(g.current_user) and requested_department
        else (g.current_user.department.name if g.current_user.department else "")
    )
    result = _sample_configuration(
        body.get("testBases") or (body.get("testBasis") or "").strip(),
        department,
        (body.get("seal") or "").strip(),
        (body.get("schemeCode") or "").strip(),
        project=(body.get("project") or "").strip(),
        test_room=(body.get("testRoom") or "").strip(),
        standard_judge=(body.get("standardJudge") or "").strip(),
        standard_item_ids=body.get("standardItemIds"),
        defer_accreditation=True,
    )
    # ``project`` contains the selected capability parameter names after a
    # standard capability is chosen (for example, "采光面积"). Department
    # project authorization belongs to the scheme, not to those parameters.
    scheme_code = str(body.get("schemeCode") or "").strip()
    project_error = (
        validate_project_department(
            g.current_user,
            body.get("department") or "",
        )
        if scheme_code
        else validate_project_selection(
            g.current_user,
            body.get("project") or "",
            body.get("department") or "",
        )
    )
    if project_error:
        result["errors"] = list(dict.fromkeys([*result.get("errors", []), project_error]))
        result["ready"] = False
    return jsonify({"code": 0, "message": "ok", "data": result})


@bp.post("/lib/items")
@require_auth
def lib_items():
    from ..library import search_items
    body = request.get_json(silent=True) or {}
    requested_department = (body.get("department") or "").strip()
    department = (
        requested_department
        if user_has_org_wide_scope(g.current_user) and requested_department
        else (g.current_user.department.name if g.current_user.department else "")
    )
    return jsonify({"code": 0, "message": "ok", "data": {"rows": search_items(body.get("keyword", ""), department)}})


@bp.get("/lib/testing-locations")
@require_auth
def lib_testing_locations():
    from ..applications.quality_resources.testing_locations import available_testing_addresses
    return jsonify({"code": 0, "message": "ok", "data": {"rows": available_testing_addresses()}})


@bp.post("/lib/capability-items")
@require_auth
@reuse_preflight_reads
def lib_capability_items():
    """List every parameter attached to authorized selected standard identities."""
    from ..models import CapabilityEntry
    from ..applications.quality_resources.testing_locations import workbook_capability_owners, capability_address, capability_accreditation, parameter_address_key
    from ..authorization_scope import all_standard_items, department_standard_items, normalize_code, standard_has_department
    from sqlalchemy.orm import selectinload

    body = request.get_json(silent=True) or {}
    locations = []
    try:
        paged = 'page' in body
        page, size = int(body.get('page', 1)), int(body.get('size', 20))
        ids, codes = body.get('ids'), body.get('standardCodes')
        selected_ids = body.get('standardItemIds')
        location_filter = body.get('locationFilter', '')
        if not isinstance(location_filter, str) or len(location_filter) > 500:
            raise ValueError()
        location_filter = parameter_address_key(location_filter)
        accreditation_filter = body.get('accreditationFilter', '')
        if not isinstance(accreditation_filter, str) or accreditation_filter not in ('', 'CMA', 'CNAS'):
            raise ValueError()
        single_id = body.get('standardItemId')
        if selected_ids is None and single_id is not None:
            selected_ids = [int(single_id)]
        if selected_ids is not None and (not isinstance(selected_ids, list) or len(selected_ids) > 200 or any(type(i) is not int or i < 1 for i in selected_ids)):
            raise ValueError()
        if page < 1 or not 1 <= size <= 100 or len(str(body.get('keyword') or '')) > 200:
            raise ValueError()
        if ids is not None and (not isinstance(ids, list) or len(ids) > 500 or any(type(i) is not int or i < 1 for i in ids)):
            raise ValueError()
        if codes is not None and (not isinstance(codes, list) or len(codes) > 200 or any(not isinstance(c, str) for c in codes)):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '查询或分页参数无效', 'data': None}), 400

    def result(rows, total=0):
        data = {'rows': rows, 'total': total, 'page': page, 'size': size}
        if body.get('includeLocations') is True:
            data['locations'] = locations
        return jsonify({'code': 0, 'message': 'ok', 'data': data})

    org_wide = user_has_org_wide_scope(g.current_user)
    user_department = g.current_user.department.name if g.current_user.department else ''
    department = str(body.get('department') or '').strip() if org_wide else user_department
    denied = set() if org_wide else denied_standard_item_ids(g.current_user)
    standards = all_standard_items() if org_wide else department_standard_items(user_department)
    allowed = {item.id: item for item in standards if item.id not in denied and standard_has_department(item)
               and (not department or standard_matches_department(item, department))
               and item.to_row()['status'] == '现行'}
    if selected_ids is not None:
        if not set(selected_ids).issubset(allowed):
            return result([])
        allowed = {i: item for i, item in allowed.items() if i in selected_ids}
    else:
        # Compatibility for old code-only callers; same-code ambiguity still
        # requires an explicit record. Codes never re-filter an explicit ID.
        requested_codes = codes if codes is not None else ([body['standardCode']] if body.get('standardCode') else None)
        if requested_codes is not None:
            wanted = {normalize_code(code) for code in requested_codes}
            for code in wanted:
                if sum(normalize_code(item.code) == code for item in allowed.values()) > 1:
                    return jsonify({'code': 1, 'message': '存在同编号标准，请选择具体标准记录后再查询参数', 'data': None}), 200
            allowed = {i: item for i, item in allowed.items() if normalize_code(item.code) in wanted}
        elif body.get('allStandards') is not True:
            return result([])
    owners = workbook_capability_owners()
    selected_by_owner = {}
    for item in allowed.values():
        selected_by_owner.setdefault(owners.get(item.id, item.id), []).append(item)
    query = CapabilityEntry.query.filter(CapabilityEntry.standard_item_id.in_(list(selected_by_owner) or [-1]))
    if ids is not None:
        query = query.filter(CapabilityEntry.id.in_(ids))
    # An explicit picker filter, not a business restriction or legacy site hint.
    # Build choices from the authorized standard scope before keyword/pagination.
    if location_filter or accreditation_filter or body.get('includeLocations') is True:
        location_rows = query.with_entities(CapabilityEntry.id, CapabilityEntry.site, CapabilityEntry.raw_cells).all()
        locations_by_id = {row.id: capability_address(row) or parameter_address_key(row.site or '') or '__unspecified__'
                           for row in location_rows}
        locations = sorted(set(locations_by_id.values()))
        if location_filter:
            matching_ids = [i for i, location in locations_by_id.items() if location == location_filter]
            query = query.filter(CapabilityEntry.id.in_(matching_ids))
        if accreditation_filter:
            matching_ids = [row.id for row in location_rows if capability_accreditation(row) == accreditation_filter]
            query = query.filter(CapabilityEntry.id.in_(matching_ids))
    # Old clients may still send type/date/site; these no longer constrain
    # parameters. Explicit text search and pagination remain user controls.
    for term in str(body.get('keyword') or '').strip().split():
        like = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(db.or_(CapabilityEntry.item_name.ilike(like, escape='\\'),
            CapabilityEntry.object_name.ilike(like, escape='\\'),
            CapabilityEntry.standard_code.ilike(like, escape='\\'),
            CapabilityEntry.standard_name.ilike(like, escape='\\')))
    total = query.count()
    query = query.order_by(CapabilityEntry.site, CapabilityEntry.object_seq, CapabilityEntry.item_seq, CapabilityEntry.id)
    if paged:
        query = query.offset((page - 1) * size).limit(size)
    output = []
    for entry in query.options(selectinload(CapabilityEntry.departments)).all():
        row = entry.to_row()
        source_metadata = entry.raw_cells if isinstance(entry.raw_cells, dict) else {}
        row.update(sourceStandardCode=entry.standard_code, sourceStandardName=entry.standard_name or '',
                   superseded=bool(source_metadata.get('parameterSupersededBy')))
        matches = selected_by_owner.get(entry.standard_item_id, [])
        if selected_ids is not None and len(matches) == 1:
            row.update(standardItemId=matches[0].id, standardCode=matches[0].code, standardName=matches[0].name)
        output.append(row)
    return result(output, total)


# 合同评审 7 项确认（流程图：合同评审）
CR_ITEMS = [
    ("tech", "技术能力"), ("instrument", "仪器设备"), ("env", "环境"),
    ("method", "方法"), ("personnel", "人员"), ("sample", "样品"), ("basisAuth", "检验依据授权"),
]


def _standard_values(value):
    from ..standard_control import split_standard_codes

    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(split_standard_codes(str(item or "")))
    else:
        values = split_standard_codes(str(value or ""))
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _sample_standard_values(detail):
    raw_sample = (detail or {}).get("rawSample") or {}
    values = _standard_values(raw_sample.get("testBases") or raw_sample.get("testBasis"))
    if values:
        return values
    wanted = {"检测依据", "执行标准", "检测标准", "判定依据"}
    for section in (detail or {}).get("summary") or []:
        for field in section.get("fields") or []:
            if isinstance(field, (list, tuple)) and len(field) >= 2 and field[0] in wanted:
                values = _standard_values(field[1])
                if values:
                    return values
    return []


def _report_standard_values(detail):
    check_input = detail.get("checkInput") or {}
    values = _standard_values(check_input.get("standards") or check_input.get("standard"))
    return values or _sample_standard_values(detail)


def _report_standard_text(detail):
    return "；".join(_report_standard_values(detail))


def _report_seal_requirement(detail):
    for section in (detail or {}).get("summary") or []:
        if section.get("title") != "委托信息":
            continue
        for field in section.get("fields") or []:
            if isinstance(field, (list, tuple)) and len(field) >= 2 and field[0] == "盖章要求":
                return str(field[1] or "").strip()
    return ""


def _seal_flags(value):
    text = (value or "").upper()
    return "CMA" in text, "CNAS" in text


def _department_family(value):
    text = " ".join(str(value or "").split())
    return re.sub(r"\s*[（(][^（）()]*[）)]\s*$", "", text)


_CAPABILITY_SITE_FULL_ADDRESSES = {
    "示例站点A": {"示例市科技园区一号院1号楼"},
    "示例站点B": {"示例市东区实验大道2号"},
    "示例站点C": {"示例园区实验楼 A 座"},
    "示例站点D": {
        "示例市南区高新街7号5号楼",
        "示例市南区科研西路30号院",
    },
    "示例站点E": {"示例市华南工业园西区12号"},
    "示例站点F": {"示例市华北产业园兴业大街6号"},
    "示例站点G": {"示例市华东检测基地166号"},
    "示例站点H": {"示例市齐鲁产业园88号"},
    "示例站点I": {"示例市海滨实验园2号"},
}


def _capability_site_for_full_address(value):
    address = str(value or "").strip()
    for site, addresses in _CAPABILITY_SITE_FULL_ADDRESSES.items():
        if address in addresses:
            return site
    return ""


def _scheme_department_matches(expected, actual):
    expected_text = " ".join(str(expected or "").split())
    actual_text = " ".join(str(actual or "").split())
    return expected_text == actual_text or _department_family(expected_text) == _department_family(actual_text)


def _sample_configuration(
    standard,
    department,
    seal,
    scheme_code="",
    *,
    project="",
    test_room="",
    standard_judge="",
    defer_accreditation=False,
    standard_item_ids=None,
):
    from ..library import find_scheme
    from ..standard_control import find_controlled_standard, validate_stamp_standards

    errors = []
    warnings = []
    standards = _standard_values(standard)
    standard_text = "；".join(standards)
    required_cma, required_cnas = _seal_flags(seal)
    scheme = find_scheme(scheme_code, department) if scheme_code else None
    if scheme_code and not scheme:
        errors.append(f"检测方案 {scheme_code} 不存在或已停用")
    if scheme:
        required = ("project", "testDept", "testRoom", "testBasis", "standardJudge")
        missing = [key for key in required if not scheme.get(key)]
        current_mapping = {
            "project": project,
            "testDept": department,
            "testRoom": test_room,
            "testBasis": standard_text,
            "standardJudge": standard_judge or standard_text,
        }
        unresolved = [key for key in missing if not str(current_mapping.get(key) or "").strip()]
        if unresolved:
            errors.append(f"检测方案 {scheme_code} 映射不完整：{','.join(unresolved)}")
        elif missing:
            warnings.append(
                f"检测方案 {scheme_code} 库内映射不完整（{','.join(missing)}），已使用当前表单值完成校验"
            )
        expected_department = scheme.get("testDept") or scheme.get("dept") or ""
        if expected_department and not _scheme_department_matches(expected_department, department):
            errors.append(f"检测方案 {scheme_code} 仅适用于部门「{expected_department}」")
        expected_standard = scheme.get("testBasis") or ""
        expected_standards = _standard_values(expected_standard)
        if expected_standards and standards and not all(
            any(
                normalize_standard_code(actual) == normalize_standard_code(expected)
                or normalize_standard_code(actual).startswith(normalize_standard_code(expected))
                for actual in standards
            )
            for expected in expected_standards
        ):
            errors.append(f"检测方案 {scheme_code} 应使用检测依据「{expected_standard}」")
    standard_rows = []
    standard_results = []
    if not standards:
        errors.append("未选择检测依据")
        standard_results.append({"valid": False, "reason": "未选择检测依据"})
    else:
        from ..standard_control import selected_controlled_standards, standard_scope_failures
        resolved = selected_controlled_standards(standards, standard_item_ids, department)
        for standard_row, standard_result in resolved:
            standard_code = standard_result["code"]
            if standard_row:
                standard_rows.append(standard_row)
            standard_results.append({"code": standard_code, **standard_result})
            marks = [mark for mark, enabled in [('CMA', required_cma), ('CNAS', required_cnas)] if enabled]
            stamp_errors = [standard_code + '：' + failure['message'] for failure in standard_scope_failures(standard_result, marks)]
            if defer_accreditation:
                accreditation_errors = [
                    message for message in stamp_errors
                    if "CMA" in message or "CNAS" in message or "一单一库" in message
                ]
                warnings.extend(
                    f"{message}；已转为合同评审、报告审核和批准节点逐项确认"
                    for message in accreditation_errors
                )
                errors.extend(message for message in stamp_errors if message not in accreditation_errors)
            else:
                errors.extend(stamp_errors)
    if standard_rows and not required_cma and not required_cnas:
        warnings.append("当前委托未要求 CMA/CNAS，仍已按受控标准有效性完成检查")
    return {
        "ready": not errors,
        "errors": list(dict.fromkeys(errors)),
        "warnings": warnings,
        "standard": standard_rows[0].to_row() if standard_rows else None,
        "standards": [row.to_row() for row in standard_rows],
        "standardResult": standard_results[0] if standard_results else None,
        "standardResults": standard_results,
        "scheme": scheme,
        "requiredCma": required_cma,
        "requiredCnas": required_cnas,
    }


def _validate_sample_registration_completion(user, detail, entrust, *, project="", department=""):
    normalized, date_error = _validate_sample_detail_dates(
        user, detail, entrust, require_send=True,
    )
    if date_error:
        return None, date_error

    pricing_error = sample_pricing_error(normalized, entrust)
    if pricing_error:
        return None, pricing_error

    raw_sample = normalized.get("rawSample")
    if not isinstance(raw_sample, dict):
        return normalized, None
    if 'locationWorkflowVersion' in raw_sample and (type(raw_sample['locationWorkflowVersion']) is not int or raw_sample['locationWorkflowVersion'] not in (0, 1)):
        return None, "检测地点流程版本无效，请刷新表单"

    project_list = raw_sample.get("projectList")
    project_value = str(
        raw_sample.get("project")
        or ("、".join(project_list) if isinstance(project_list, list) else "")
        or project
        or ""
    ).strip()
    department_value = str(
        raw_sample.get("testDept")
        or _field(normalized, "送样信息", "检测部门")
        or _field(normalized, "样品信息", "检测部门")
        or ""
    ).strip()
    # 新登记统一使用一个“检测部门/检测室”组织字段。继续镜像 testRoom，
    # 以兼容既有委托单、报告模板和历史查询字段。
    room_value = department_value
    raw_sample["testRoom"] = department_value
    location_value = str(
        raw_sample.get("testLocation")
        or _field(normalized, "送样信息", "检测地点")
        or _field(normalized, "样品信息", "检测地点")
        or ""
    ).strip()
    standard_values = _standard_values(
        raw_sample.get("testBases")
        or raw_sample.get("testBasis")
        or _report_standard_values(normalized)
    )
    standard_value = "；".join(standard_values)
    raw_sample["testBases"] = standard_values
    raw_sample["testBasis"] = standard_value
    judge_value = str(
        raw_sample.get("standardJudge")
        or _field(normalized, "实验信息", "判定标准")
        or _field(normalized, "实验信息", "标准/判定")
        or ""
    ).strip()
    scheme_code = str(raw_sample.get("schemeCode") or "").strip()
    report_category = str(raw_sample.get("reportCategory") or normalized.get("reportCategory") or "普通").strip()
    center_prefix = str(raw_sample.get("centerPrefix") or "").strip()
    base_report_no = str(raw_sample.get("baseReportNo") or normalized.get("derivedFrom") or "").strip()

    required = [
        (scheme_code, "检测方案"),
        (project_value, "检测项目"),
        (department_value, "检测部门/检测室"),
        (location_value or raw_sample.get("capabilityEntryIds"), "检测地点完整地址"),
        (standard_value, "检测依据"),
        (judge_value, "判定标准"),
    ]
    if report_category == "普通":
        required.append((center_prefix, "报告标题/检测中心"))
    else:
        required.append((base_report_no, "原报告"))
    missing = [label for value, label in required if not value or value == "—"]
    if missing:
        return None, "完成登记缺少必填项：" + "、".join(missing)
    # Capability item names are report parameters and do not have to equal the
    # department project master name. The scheme code is the project identity.
    project_error = (
        validate_project_department(
            user,
            department_value or department,
        )
        if scheme_code
        else validate_project_selection(
            user,
            project_list
            if isinstance(project_list, list) and project_list
            else project_value,
            department_value or department,
        )
    )
    if project_error:
        return None, project_error
    unauthorized = [
        code for code in standard_values
        if not standard_is_authorized(user, code, department_value or department)
    ]
    if unauthorized:
        return None, "以下检测依据未授权给当前账号：" + "、".join(unauthorized)

    capability_ids = []
    for value in raw_sample.get("capabilityEntryIds") or []:
        try:
            capability_ids.append(int(value))
        except (TypeError, ValueError):
            return None, f"能力项目编号「{value}」无效"
    entries = CapabilityEntry.query.filter(CapabilityEntry.id.in_(capability_ids)).all() if capability_ids else []
    if len(entries) != len(set(capability_ids)):
        return None, "所选能力项目已不存在，请根据检测依据重新选择"
    from ..standard_control import selected_controlled_standards, capability_matches_standard
    selected_records = selected_controlled_standards(standard_values, raw_sample.get('standardItemIds'), department_value or department)
    if any(item is None for item, _ in selected_records):
        return None, "检测依据无法唯一确认，请重新选择对应的标准记录"
    selected_items = [item for item, _ in selected_records]
    if any(item.to_row()['status'] != '现行' for item in selected_items):
        return None, '所选标准当前不可用，请重新选择标准'
    denied = set() if user_has_org_wide_scope(user) else denied_standard_item_ids(user)
    if any(item.id in denied or not standard_matches_department(item, department_value or department)
           for item in selected_items):
        return None, "所选标准未授权给检测部门，请重新选择标准"
    if any(not any(capability_matches_standard(entry, item) for item in selected_items) for entry in entries):
        return None, "所选参数不属于选中的标准记录，请重新选择参数"
    raw_sample['standardItemIds'] = [item.id for item in selected_items]
    if raw_sample.get("locationWorkflowVersion") == 1 or entries:
        from ..applications.quality_resources.testing_locations import resolve_testing_location
        by_id = {entry.id: entry for entry in entries}
        ordered_entries = [by_id[i] for i in dict.fromkeys(capability_ids)]
        try:
            resolved = resolve_testing_location(
                {"isOnsiteTesting": False, **raw_sample}, ordered_entries, department_value or department,
                None, None,
                selected_standards=selected_items,
            )
        except ValueError as exc:
            return None, str(exc)
        raw_sample.update(resolved)
        location_value = resolved["testLocation"]
    elif entries:
        location_site = _capability_site_for_full_address(location_value)
        if location_site:
            mismatched_site_entries = [entry for entry in entries if entry.site and entry.site != location_site]
            if mismatched_site_entries:
                return None, "检测地点与所选标准认可场所不一致"
            expected_sites = "、".join(sorted({entry.site for entry in mismatched_site_entries}))
            return None, f"检测地点与所选标准能力场所不一致：能力场所为「{expected_sites}」"

    config_check = _sample_configuration(
        standard_values,
        department_value or department,
        _report_seal_requirement(normalized),
        scheme_code,
        project=project_value,
        test_room=room_value,
        standard_judge=judge_value,
        standard_item_ids=raw_sample.get("standardItemIds"),
        defer_accreditation=True,
    )
    if not config_check["ready"]:
        return None, "样品方案配置校验未通过：" + "；".join(config_check["errors"])
    normalized["sampleConfiguration"] = config_check
    return normalized, None


@bp.post("/<report_no>/contract-review")
@require_auth
def contract_review(report_no):
    """合同评审：7 项逐条确认 + 委托盖章要求硬校验，通过后仅进入待样品入库。"""
    user = g.current_user
    body = request.get_json(silent=True) or {}
    action = body.get("action")  # pass / return
    need = "report.contract_review.pass" if action == "pass" else "report.contract_review.return"
    if need not in user.action_codes():
        return jsonify({"code": 403, "message": "无合同评审权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).with_for_update().first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    grant_error = project_step_error(user, r, "entrust_review", "合同评审")
    if grant_error:
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200
    if r.status != "待合同评审":
        return jsonify({"code": 1, "message": f"报告当前处于「{r.status}」，不在合同评审节点", "data": None}), 200
    if (r.sample_reg_state or "登记完成") != "登记完成":
        return jsonify({"code": 1, "message": "样品登记尚未完成，不能进入合同评审", "data": None}), 200

    items = body.get("items") or {}
    cma = bool(body.get("cma"))
    cnas = bool(body.get("cnas"))
    opinion = (body.get("opinion") or body.get("note") or "").strip()
    detail = dict(r.detail or {})
    from ..seal_requirements import requested_seal
    seal_requirement = requested_seal(detail)
    required_cma, required_cnas = _seal_flags(seal_requirement)
    before_row = r.to_row()
    from ..workflow_hooks import capture as finance_capture, blocker as finance_blocker
    finance_error = finance_blocker(r, need)
    if finance_error:
        return jsonify({"code": 1, "message": finance_error, "data": None}), 200

    if action == "pass":
        missing = [name for key, name in CR_ITEMS if not items.get(key)]
        if missing:
            return jsonify({"code": 1, "message": f"以下评审项未确认：{'、'.join(missing)}，不予通过", "data": None}), 200
        missing_seals = []
        if required_cma and not cma:
            missing_seals.append("CMA")
        if required_cnas and not cnas:
            missing_seals.append("CNAS")
        if missing_seals:
            return jsonify({
                "code": 1,
                "message": f"委托要求 {' + '.join(missing_seals)}，必须逐项确认且授权校验通过后方可评审通过",
                "data": {
                    "sealRequirement": seal_requirement,
                    "requiredCma": required_cma,
                    "requiredCnas": required_cnas,
                },
            }), 200
        from ..compliance import validate_and_record_acknowledgement

        try:
            validate_and_record_acknowledgement(r, user, "contract_review", body)
        except ValueError as exc:
            return jsonify({"code": 1, "message": str(exc), "data": None}), 200
        detail = dict(r.detail or {})
        from ..report_standard_selection import standards_for_authorization
        standard = "；".join(standards_for_authorization(detail))
        # 合规确认可能依法移除了无能力依据的标识；后续校验必须使用最终标识，
        # 原委托要求仍保存在 complianceResolution.requestedSealOriginal 中。
        effective_seals = _report_seal_requirement(detail)
        validation = _sample_configuration(
            standard,
            r.department or "",
            effective_seals,
            ((detail.get("rawSample") or {}).get("schemeCode") or "").strip(),
            standard_item_ids=(detail.get("rawSample") or {}).get("standardItemIds"),
            project=r.project or "",
            test_room=((detail.get("rawSample") or {}).get("testRoom") or "").strip(),
            standard_judge=(
                ((detail.get("rawSample") or {}).get("standardJudge") or "").strip()
                or _field(detail, "实验信息", "判定标准")
                or standard
            ),
        )
        if not validation["ready"]:
            return jsonify({
                "code": 1,
                "message": f"盖章授权校验未通过：{'；'.join(validation['errors'])}",
                "data": validation,
            }), 200
        from datetime import UTC, datetime

        detail["contractReview"] = {
            "items": items, "cma": cma, "cnas": cnas, "opinion": opinion, "result": "通过",
            "sealRequirement": seal_requirement,
            "requiredCma": required_cma,
            "requiredCnas": required_cnas,
            "reviewer": user.name or user.account,
            "reviewerAccount": user.account,
            "signature": __import__("app.contract_review_output", fromlist=["snapshot_image"]).snapshot_image(user),
            "signatureSource": "account-image-v1",
            "reviewedAt": datetime.now(UTC).isoformat(),
            "standardAuthorization": {
                "standard": standard,
                "validated": True,
                "result": validation,
            },
        }
        detail.pop("requiresContractReReview", None)
        r.detail = detail
        after_review = str((detail.get("returnPlan") or {}).get("afterContractReview") or "")
        preserved_sample_status = str(
            (detail.get("returnPlan") or {}).get("preservedSampleStatus") or ""
        ).strip()
        if resumes_sample_outbound(detail):
            r.status = "待样品领取"
            r.sample_status = "已入库"
        elif after_review == "data_entry":
            r.status = "检测录入中"
            r.sample_status = "已领取"
        elif after_review == "data_change":
            r.status = "检测更改中"
            if preserved_sample_status:
                r.sample_status = preserved_sample_status
        elif after_review == "review":
            r.status = "待审核"
            if preserved_sample_status:
                r.sample_status = preserved_sample_status
        else:
            r.status = "待样品入库"
            r.sample_status = "待入库"  # 评审通过 → 等待样品入库（样品入库页手动入库）
        skipped_nodes = advance_skipped_project_steps(r)
        add_operation_audit(
            "report.contract_review.pass", "report", r.report_no, category="workflow",
            before=before_row, after=r.to_row(), message=opinion,
        )
        finance_capture(r, "CONTRACT_REVIEW_COMPLETED", user)
        db.session.commit()
        message = f"{r.report_no} 合同评审通过，已进入「{r.status}」"
        if skipped_nodes:
            message += f"；按项目流程已跳过：{'、'.join(skipped_nodes)}"
        return jsonify({"code": 0, "message": message, "data": r.to_row()})
    else:
        if not opinion:
            return jsonify({"code": 1, "message": "退回需填写不通过原因", "data": None}), 200
        detail["contractReview"] = {
            "items": items, "cma": cma, "cnas": cnas, "opinion": opinion, "result": "退回",
            "sealRequirement": seal_requirement, "requiredCma": required_cma, "requiredCnas": required_cnas,
        }
        detail["changeNote"] = opinion
        detail["changeSource"] = {"status": r.status, "sampleStatus": r.sample_status or ""}  # R6-AC4 来源态留档
        r.detail = detail
        _apply_return_plan(r, user, need, opinion, "entrust_only")
        add_operation_audit(
            "report.contract_review.return", "report", r.report_no, category="workflow",
            before=before_row, after=r.to_row(), message=opinion,
        )
        db.session.commit()
        return jsonify({"code": 0, "message": f"{r.report_no} 合同评审退回，转委托更改：{opinion}", "data": {"reportNo": r.report_no, "status": r.status}})


@bp.put("/<report_no>/edit")
@require_auth
def report_edit(report_no):
    """修改尚未完成的样品登记信息。

    样品登记完成后，委托和样品快照一并锁定。后续节点只能查看；
    如需修改，必须先按流程撤销完成或退回委托更改节点。
    """
    user = g.current_user
    permissions = user.permission_codes()
    if (
        "entrust.sample_register.view" not in permissions
        and "sample.register.complete" not in user.action_codes()
    ):
        return jsonify({"code": 403, "message": "无样品登记修改权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    if (r.sample_reg_state or "登记完成") != "登记中":
        return jsonify({
            "code": 1,
            "message": "样品登记已完成，委托单和样品单已锁定；请先撤销完成或退回委托更改环节",
            "data": None,
        }), 200
    body = request.get_json(silent=True) or {}
    conflict = require_edit_version(r, body)
    if conflict:
        return conflict
    full = body.get("fullDetail")
    if not (isinstance(full, dict) and full.get("summary")):
        return jsonify({"code": 1, "message": "缺少表单数据", "data": None}), 200
    before = r.to_row()
    from ..sample_form_merge import merge_sample_form, normalize_judgment_entries
    try:
        normalize_judgment_entries(full)
    except ValueError as exc:
        return jsonify(code=1, message=str(exc), data=None), 200
    detail = merge_sample_form(r.detail, full)
    detail.pop('reportComposition', None)
    if 'reportComposition' in (r.detail or {}):
        detail['reportComposition'] = (r.detail or {})['reportComposition']
    scheme_error = _preserve_numbering_scheme(r, detail)
    if scheme_error:
        return jsonify({"code": 1, "message": scheme_error, "data": None}), 200
    change_round = (r.detail or {}).get("changeRound")
    if change_round:
        detail["changeRound"] = change_round
    entrust = Entrust.query.filter_by(entrust_no=r.entrust_no).first() if r.entrust_no else None
    party_error = sample_party_error(detail, entrust, r.detail, r.id)
    if party_error:
        return jsonify({"code": 1, "message": party_error, "data": None}), 200
    # Independent sample dates must be checked even if a legacy record has
    # no associated entrust. Do this before changing any report fields.
    detail, date_error = _validate_sample_detail_dates(user, detail, entrust)
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    if entrust:
        detail["entrustSnapshot"] = normalize_sample_entrust_snapshot(
            detail.get("entrustSnapshot") or (r.detail or {}).get("entrustSnapshot"),
            entrust, report_id=r.id, select_contract=True,
        )
        detail, date_error = _validate_sample_detail_dates(
            user,
            detail,
            entrust,
            require_send=(r.sample_reg_state or "登记完成") == "登记完成",
        )
        if date_error:
            return jsonify({"code": 1, "message": date_error, "data": None}), 200
        if (r.sample_reg_state or "登记完成") == "登记完成":
            detail, completion_error = _validate_sample_registration_completion(
                user,
                detail,
                entrust,
                project=r.project or "",
                department=r.department or "",
            )
            if completion_error:
                return jsonify({"code": 1, "message": completion_error, "data": None}), 200

    price_error = sample_price_error(detail, report=r)
    if price_error:
        return jsonify({"code": 1, "message": price_error, "data": None}), 200

    def _fv(sec, k):
        for s in full.get("summary", []):
            if s.get("title") == sec:
                for kk, vv in s.get("fields", []):
                    if kk == k:
                        return vv
        return ""
    prefix_error = _apply_report_prefix_change(r, detail)
    if prefix_error:
        return jsonify({"code": 1, "message": prefix_error, "data": None}), 200
    snapshot = detail.get("entrustSnapshot") or {}
    r.project_name = snapshot.get("projectName") or full.get("projectName") or _fv("委托信息", "工程名称") or r.project_name
    r.client = sample_client_from_detail(detail, r.client)
    raw_sample = detail.get("rawSample")
    if isinstance(raw_sample, dict):
        project_list = raw_sample.get("projectList")
        r.project = str(
            raw_sample.get("project")
            or ("、".join(project_list) if isinstance(project_list, list) else "")
            or ""
        ).strip()
        sample_department = str(raw_sample.get("testDept") or "").strip()
        if sample_department:
            r.department = sample_department
    else:
        r.project = _fv("实验信息", "检测项目") or r.project
    detail = stamp_sample_registrar(detail, user, previous=r.detail or {})
    r.detail = detail
    from ..report_date_policy import audit_sample_date_alignment
    audit_sample_date_alignment(r.report_no, body.get('fullDetail') or body.get('detail') or {}, user)
    add_operation_audit(
        "sample.register.update", "report", r.report_no,
        category="workflow", before=before, after=r.to_row(),
    )
    persist_sample_contract_selection(r)
    db.session.flush()
    saved_row = r.to_row()
    db.session.commit()
    from ..sample_preview_warmup import schedule_after_save
    schedule_after_save(r)
    return jsonify({"code": 0, "message": f"{r.report_no} 已保存修改", "data": saved_row})


@bp.post("/<report_no>/change-resubmit")
@require_auth
def change_resubmit(report_no):
    """委托更改：修改委托/样品基本信息后「提交委托更改完成」，回到待合同评审重走流程（流程图 #5/#7）。"""
    return _save_entrust_change(report_no, complete=True)


@bp.post("/<report_no>/change-save")
@require_auth
def change_save(report_no):
    """保存更改中的表单，不完成登记、不推进退回流程。"""
    return _save_entrust_change(report_no, complete=False)


def _save_entrust_change(report_no, *, complete):
    user = g.current_user
    if (
        "entrust.change.view" not in user.permission_codes()
        and "entrust.change.resubmit" not in user.action_codes()
    ):
        return jsonify({"code": 403, "message": "无委托更改权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    if r.status != "委托更改中":
        return jsonify({"code": 1, "message": f"报告当前「{r.status}」，不在委托更改节点", "data": None}), 200
    body = request.get_json(silent=True) or {}
    conflict = require_edit_version(r, body)
    if conflict:
        return conflict
    before = r.to_row()
    full = body.get("fullDetail")
    if not complete and not (isinstance(full, dict) and full.get("summary")):
        return jsonify({"code": 1, "message": "缺少表单数据", "data": None}), 200
    if not complete and r.voided:
        return jsonify({"code": 403, "message": "作废报告不能保存更改", "data": None}), 200
    # Both full-form and legacy basic-field change submissions share the gate.
    from ..sample_form_merge import merge_sample_form, normalize_judgment_entries
    if isinstance(full, dict):
        try:
            normalize_judgment_entries(full)
        except ValueError as exc:
            return jsonify(code=1, message=str(exc), data=None), 200
    date_detail = merge_sample_form(r.detail, full) if isinstance(full, dict) and full.get("summary") else (r.detail or {})
    date_entrust = Entrust.query.filter_by(entrust_no=r.entrust_no).first() if r.entrust_no else None
    party_error = sample_party_error(date_detail, date_entrust, r.detail, r.id)
    if party_error:
        return jsonify({"code": 1, "message": party_error, "data": None}), 200
    date_detail, date_error = _validate_sample_detail_dates(user, date_detail, date_entrust, require_send=complete)
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    pricing_error = sample_pricing_error(date_detail, date_entrust) if complete else None
    if pricing_error:
        return jsonify({"code": 1, "message": pricing_error, "data": None}), 200
    price_error = sample_price_error(date_detail, report=r)
    if price_error:
        return jsonify({"code": 1, "message": price_error, "data": None}), 200
    if isinstance(full, dict) and full.get("summary"):
        previous_detail = dict(r.detail or {})
        change_round = previous_detail.get("changeRound")
        detail = merge_sample_form(previous_detail, full)
        detail.pop('reportComposition', None)
        if 'reportComposition' in previous_detail:
            detail['reportComposition'] = previous_detail['reportComposition']
        scheme_error = _preserve_numbering_scheme(r, detail)
        if scheme_error:
            return jsonify({"code": 1, "message": scheme_error, "data": None}), 200
        if change_round:
            detail["changeRound"] = change_round
        for key in ("returnPlan", "returnInfo", "changeSource", "changeNote"):
            if key in previous_detail:
                detail[key] = previous_detail[key]
        entrust = Entrust.query.filter_by(entrust_no=r.entrust_no).first() if r.entrust_no else None
        if entrust:
            detail["entrustSnapshot"] = normalize_sample_entrust_snapshot(
                detail.get("entrustSnapshot") or (r.detail or {}).get("entrustSnapshot"),
                entrust, report_id=r.id, select_contract=True,
            )
            detail, date_error = _validate_sample_detail_dates(
                user, detail, entrust, require_send=complete,
            )
            if date_error:
                return jsonify({"code": 1, "message": date_error, "data": None}), 200
            if complete:
                detail, completion_error = _validate_sample_registration_completion(
                    user,
                    detail,
                    entrust,
                    project=r.project or "",
                    department=r.department or "",
                )
                if completion_error:
                    return jsonify({"code": 1, "message": completion_error, "data": None}), 200
        def _fv(sec, k):
            for s in full.get("summary", []):
                if s.get("title") == sec:
                    for kk, vv in s.get("fields", []):
                        if kk == k:
                            return vv
            return ""
        snapshot = detail.get("entrustSnapshot") or {}
        r.project_name = snapshot.get("projectName") or full.get("projectName") or _fv("委托信息", "工程名称") or r.project_name
        r.client = sample_client_from_detail(detail, r.client)
        r.project = _fv("实验信息", "检测项目") or r.project
    else:
        detail = dict(r.detail or {})
        entrust = Entrust.query.filter_by(entrust_no=r.entrust_no).first() if r.entrust_no else None
        if entrust:
            detail["entrustSnapshot"] = normalize_sample_entrust_snapshot(
                detail.get("entrustSnapshot"), entrust, report_id=r.id,
            )
        # 允许修改的基本字段
        if isinstance(body.get("client"), str):
            r.client = body["client"].strip()
        if body.get("projectName"):
            r.project_name = body["projectName"].strip()
        if body.get("project"):
            r.project = body["project"].strip()
        if entrust:
            snapshot = dict(detail.get("entrustSnapshot") or {})
            snapshot_info = dict(snapshot.get("info") or {})
            if isinstance(body.get("client"), str):
                snapshot["client"] = r.client
                snapshot_info["client"] = r.client
            if body.get("projectName"):
                snapshot["projectName"] = r.project_name
                snapshot_info["projectName"] = r.project_name
            snapshot["info"] = snapshot_info
            detail["entrustSnapshot"] = normalize_sample_entrust_snapshot(snapshot, entrust, report_id=r.id)
        # 回写委托/样品摘要（按字段键回写，不限分区标题）
        def _rewrite(k, v):
            if k == "委托单位":
                return [k, r.client]
            if k == "工程名称":
                return [k, r.project_name]
            if k == "样品编号":
                return [k, r.sample_no]
            return [k, v]
        for sec in detail.get("summary", []):
            sec["fields"] = [_rewrite(k, v) for k, v in sec.get("fields", [])]
    detail["changeNote"] = (body.get("note") or detail.get("changeNote") or "").strip()
    prefix_error = _apply_report_prefix_change(r, detail)
    if prefix_error:
        return jsonify({"code": 1, "message": prefix_error, "data": None}), 200
    detail = stamp_sample_registrar(detail, user, previous=r.detail or {})
    from ..report_date_policy import audit_sample_date_alignment
    audit_sample_date_alignment(r.report_no, body.get('fullDetail') or {}, user)
    r.detail = detail
    persist_sample_contract_selection(r)
    if not complete:
        add_operation_audit(
            "report.entrust_change.save", "report", r.report_no, category="workflow",
            before=before, after=r.to_row(),
        )
        db.session.flush()
        saved_row = r.to_row()
        db.session.commit()
        return jsonify({"code": 0, "message": "已保存修改，仍处于委托更改中，尚未提交", "data": saved_row})
    # Every entrust change, including an issued correction, requires re-review.
    # Contract selection may autoflush JSON; assign a new object after that flush.
    detail = {**(r.detail or {}), "requiresContractReReview": True}
    r.detail = detail
    r.status = "待合同评审"
    return_plan = detail.get("returnPlan") or {}
    if resumes_sample_outbound(detail):
        r.sample_status = "已入库"
    elif return_plan.get("skipSampleFlow") or return_plan.get("afterContractReview") in {"data_entry", "data_change", "review"}:
        r.sample_status = str(return_plan.get("preservedSampleStatus") or r.sample_status or "已领取")
    else:
        r.sample_status = "待合同评审"
    add_operation_audit(
        "report.entrust_change.complete", "report", r.report_no, category="workflow",
        before=before, after=r.to_row(),
    )
    db.session.flush()
    saved_row = r.to_row()
    db.session.commit()
    return jsonify({"code": 0, "message": f"{r.report_no} 委托更改完成，重新进入合同评审", "data": saved_row})


@bp.post("/<report_no>/request-change")
@require_auth
def request_change(report_no):
    """Legacy JSON entry is closed so callers cannot bypass scan + two-level approval."""
    return jsonify({
        "code": 409,
        "message": "更正报告必须上传申请表扫描件，并依次完成一审和二审",
        "data": {"endpoint": f"/api/reports/{report_no}/correction-requests"},
    }), 409


@bp.post("/<report_no>/change-test-complete")
@require_auth
def change_test_complete(report_no):
    """检测更改完成：检测更改中 → 待审核（保留更改标记，审核环节显示为更改）。"""
    user = g.current_user
    if (
        "testing.data_change.view" not in user.permission_codes()
        and "report.change.test_complete" not in user.action_codes()
    ):
        return jsonify({"code": 403, "message": "无检测更改完成权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    r = Report.query.filter_by(id=r.id).with_for_update().populate_existing().one()
    if r.status != "检测更改中":
        return jsonify({"code": 1, "message": f"报告当前「{r.status}」，不在检测更改节点", "data": None}), 200
    grant_error = report_data_entry_step_error(user, r)
    if grant_error:
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200
    if r.voided:
        return jsonify({"code": 403, "message": "作废报告不能完成检测更改", "data": None}), 200
    from ..report_date_policy import report_date_error
    date_error = report_date_error(r, "testEnd")
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    from ..functions import esign_stages
    existing = esign_stages.current_flow(r)
    if existing:
        result = esign_stages.response(existing, user)
        return jsonify({'code': 0, 'message': result['message'], 'data': result})
    before = r.to_row()
    from ..functions.esign_service import EsignServiceError
    try:
        from ..review_version import freeze_ready_preview
        version = freeze_ready_preview(r, user)
        from ..functions import esign_stages
        if esign_stages.selected(r):
            flow = esign_stages.begin(r, version, user)
            db.session.commit()
            result = esign_stages.response(flow, user)
            return jsonify({'code': 0, 'message': result['message'], 'data': result})
    except (ValueError, EsignServiceError) as exc:
        db.session.rollback()
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    after_change = str(((r.detail or {}).get("returnPlan") or {}).get("afterDataChange") or "review")
    r.status = {
        "data_check": "待校核",
        "report_check": "待校核",
        "review": "待审核",
    }.get(after_change, "待审核")
    add_operation_audit(
        "report.test_change.complete", "report", r.report_no, category="workflow",
        before=before, after=r.to_row(),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"{r.report_no} 检测更改完成，已进入「{r.status}」", "data": {"reportNo": r.report_no, "status": r.status}})


def _field(detail, section, key, default=""):
    for sec in (detail or {}).get("summary", []):
        if sec.get("title") == section:
            for k, v in sec.get("fields", []):
                if k == key:
                    return v
    return default


@bp.put("/<report_no>/report-pages")
@require_auth
def update_report_pages(report_no):
    """报告附加页：数据录入页只生成报告首页结论，其余页面经报告预览编辑保存（表单汇总）。"""
    user = g.current_user
    if "report.attachment.upload" not in user.action_codes():
        return jsonify({"code": 403, "message": "无报告编辑权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    grant_error = report_data_entry_step_error(user, r)
    if grant_error:
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200
    if not report_content_editable(r):
        return jsonify({
            "code": 1,
            "message": f"报告当前为「{r.status}」，内容已锁定；请退回检测数据更改环节后修改",
            "data": None,
        }), 200
    body = request.get_json(silent=True) or {}
    pages = body.get("pages")
    if not isinstance(pages, list):
        return jsonify({"code": 1, "message": "pages 需为数组", "data": None}), 200
    clean = [{"title": (p.get("title") or "").strip(), "content": (p.get("content") or "").strip()}
             for p in pages if isinstance(p, dict)]
    before = r.to_row()
    detail = dict(r.detail or {})
    detail["reportPages"] = clean
    r.detail = detail
    add_operation_audit(
        "report.pages.update", "report", r.report_no,
        category="report", before=before, after=r.to_row(),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"已保存 {len(clean)} 个报告附加页", "data": {"reportNo": r.report_no, "pages": clean}})


@bp.get("/<report_no>/authorized-people")
@require_auth
def authorized_report_people(report_no):
    """Return report personnel strictly from organization project-step grants."""
    user = g.current_user
    if not has_function_permission(user, "testing.data_entry.view"):
        return jsonify({
            "code": 403,
            "message": "无检测数据录入查看权限",
            "data": None,
        }), 200
    report = _scope_filter(Report.query, user).filter(
        Report.report_no == report_no
    ).first()
    if not report:
        return jsonify({
            "code": 1,
            "message": "报告不存在或不在当前账号的数据范围内",
            "data": None,
        }), 200
    grant_error = project_step_error(user, report, "data_entry", "检测数据录入")
    if grant_error:
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200

    project = project_for_report(report)
    if project is None:
        return jsonify({
            "code": 1,
            "message": "当前报告未关联检测项目，无法按组织机构项目权限选择人员",
            "data": None,
        }), 200

    personnel_by_account = {
        str(row.code or "").strip().lower(): row
        for row in Personnel.query.filter(Personnel.deleted_at.is_(None)).all()
        if str(row.code or "").strip()
    }

    def person_payload(account_user):
        personnel = personnel_by_account.get(account_user.account.lower())
        return {
            "id": account_user.id,
            "code": account_user.account,
            "name": account_user.name,
            "department": (
                account_user.department.name if account_user.department else ""
            ),
            "title": personnel.title if personnel else "",
            "position": personnel.position if personnel else "",
        }

    candidates = User.query.filter(User.enabled.is_(True)).order_by(
        User.name, User.account
    ).all()

    def rows_for(step_code):
        return [
            person_payload(candidate)
            for candidate in candidates
            if user_has_project_step(candidate, project, step_code)
        ]

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "project": {
                "id": project.id,
                "code": (
                    project.display_code or project.number_code or project.code or ""
                ),
                "name": project.name,
            },
            "testers": rows_for("data_entry"),
            "originalRecordReviewers": rows_for("record_review"),
            "reviewers": rows_for("report_review"),
            "approvers": rows_for("report_approval"),
        },
    })


@bp.get("/<report_no>/entry-references")
@require_auth
def entry_references(report_no):
    user = g.current_user
    report = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not report or (not set(user.permission_codes()).intersection({"testing.data_entry.view", "testing.data_change.view"})
                      and not can_correct_business_data(user)):
        return jsonify(code=403, message="无检测信息查看权限或报告不在数据范围内", data=None), 200
    error = project_step_error(user, report, "data_entry", "检测数据录入")
    if error and not can_correct_business_data(user):
        return jsonify(code=403, message=error, data=None), 200
    if report.status not in ('检测录入中', '退回待重传', '检测更改中'):
        return jsonify(code=0, message='只读历史快照', data={})
    from ..entry_references import current_entry_references
    try:
        values = current_entry_references((report.detail or {}).get('rawSample') or {}, user, report.department,
                                          correcting=can_correct_business_data(user))
    except ValueError as exc:
        return jsonify(code=1, message=str(exc), data=None), 200
    response = jsonify(code=0, message="ok", data=values)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get("/<report_no>/equipment-options")
@require_auth
def report_equipment_options(report_no):
    from ..equipment_authorization import usable_department_names, saved_equipment_ids
    user = g.current_user
    report = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not report:
        return jsonify(code=403, message="报告不存在或不在数据范围内", data=None), 200
    if not set(user.permission_codes()).intersection({
        "testing.data_entry.view", "testing.data_change.view", "report.review.view", "report.approval.view",
    }) and not can_correct_business_data(user):
        return jsonify(code=403, message="无检测信息查看权限", data=None), 200
    departments = usable_department_names(user)
    query = EquipmentItem.query.filter(EquipmentItem.deleted_at.is_(None))
    if departments is not None:
        query = query.filter(db.or_(EquipmentItem.dept.in_(departments),
                                   EquipmentItem.id.in_(saved_equipment_ids(report))))
    rows = query.order_by(EquipmentItem.archive_no, EquipmentItem.id).all()
    import json
    from ..equipment_eligibility import evaluate_intervals
    try:
        intervals = json.loads(request.args.get('intervals', '[]'))
        if not isinstance(intervals, list) or any(not isinstance(part, dict) for part in intervals):
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(code=1, message="试验区间格式无效", data=None), 200
    # The picker needs technical/display fields, not purchase prices or ledger attachments.
    def option(row):
        value = row.to_row(full=True)
        value["eligibility"] = evaluate_intervals(row, intervals, selecting=True)
        for key in ("buyDate", "buyPrice", "useRecord", "manual", "acceptDoc"):
            value.pop(key, None)
        return value
    return jsonify(code=0, message="ok", data={"rows": [option(row) for row in rows], "total": len(rows)})


@bp.put("/<report_no>/testinfo")
@require_auth
@audited_form("reports", "report_no")
def update_testinfo(report_no):
    """保存检测信息草稿；仅完成保存时执行完整业务及三库前置校验。"""
    user = g.current_user
    if not correcting("reports") and "testing.data_entry.view" not in user.permission_codes():
        return jsonify({"code": 403, "message": "无检测信息录入权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    from ..functions.esign_stages import content_blocker
    signing_error = content_blocker(r)
    if signing_error:
        return jsonify({'code': 1, 'message': signing_error, 'data': None}), 200
    grant_error = project_step_error(user, r, "data_entry", "数据录入")
    if grant_error and not correcting("reports"):
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200
    # 样品须完成出库领取（已领取）后方可录入检测数据；检测更改中（批准后更改）不受样品状态限制
    if not correcting("reports") and r.status != "检测更改中" and (r.sample_status or "待入库") != "已领取":
        return jsonify({"code": 1, "message": f"样品当前为「{r.sample_status or '待入库'}」，请先完成样品入库与出库领取后再录入检测数据", "data": None}), 200
    if not correcting("reports") and r.status not in ("检测录入中", "退回待重传", "检测更改中"):
        return jsonify({"code": 1, "message": f"报告当前为「{r.status}」，不在检测数据录入节点", "data": None}), 200
    body = request.get_json(silent=True) or {}
    conflict = require_test_form_version(r, body)
    if conflict:
        return conflict
    validate_for_completion = bool(body.get("validateForCompletion"))
    requested_standards = _standard_values(body.get("standards") or body.get("standard"))
    sample_standards = _sample_standard_values(r.detail or {})
    standards_differ = bool(sample_standards and requested_standards and {
        normalize_standard_code(code) for code in requested_standards
    } != {normalize_standard_code(code) for code in sample_standards})
    if validate_for_completion and standards_differ:
        return jsonify({
            "code": 1,
            "message": "登记标准：" + "、".join(sample_standards) + "；检测标准：" +
                       "、".join(requested_standards) + "。如需变更检测方法，请在样品登记中办理委托更改。",
            "data": None,
        }), 200
    standard_values = sample_standards or requested_standards
    standard = "；".join(standard_values)
    unauthorized = [
        code for code in standard_values
        if validate_for_completion and not standard_is_authorized(user, code, r.department or "")
    ]
    if unauthorized:
        return jsonify({
            "code": 403,
            "message": "以下检测标准未授权给当前账号：" + "、".join(unauthorized),
            "data": None,
        }), 200
    explicit_intervals = bool(body.get("testIntervals"))
    raw_intervals = body.get("testIntervals") or []
    if not explicit_intervals:
        test_start = str(body.get("testStartDate") or "").strip()
        test_end = str(body.get("testEndDate") or "").strip()
        raw_intervals = [{"start": test_start, "end": test_end}] if test_start and test_end else []
    intervals = []
    for index, item in enumerate(raw_intervals):
        if not isinstance(item, dict):
            return jsonify({"code": 1, "message": f"第 {index + 1} 个试验区间格式无效", "data": None}), 200
        start = str(item.get("start") or "").strip()
        end = str(item.get("end") or "").strip()
        if validate_for_completion and explicit_intervals and (
            not start or not end or parse_date(start) is None or parse_date(end) is None
        ):
            return jsonify({"code": 1, "message": f"第 {index + 1} 个试验区间起止时间必须完整", "data": None}), 200
        if (start and parse_date(start) is None) or (end and parse_date(end) is None):
            return jsonify({"code": 1, "message": f"第 {index + 1} 个试验区间日期无效", "data": None}), 200
        if start and end and end < start:
            return jsonify({"code": 1, "message": f"第 {index + 1} 个试验区间结束时间不能早于开始时间", "data": None}), 200
        intervals.append({"start": start, "end": end})
    if explicit_intervals:
        test_start = min((item["start"] for item in intervals if item["start"]), default="")
        test_end = max((item["end"] for item in intervals if item["end"]), default="")
    equipment_ids = []
    for value in body.get("equipmentIds") or []:
        try:
            equipment_ids.append(int(value))
        except (TypeError, ValueError):
            return jsonify({"code": 1, "message": "仪器设备选择数据无效", "data": None}), 200
    equipment_rows = EquipmentItem.query.filter(
        EquipmentItem.id.in_(equipment_ids), EquipmentItem.deleted_at.is_(None),
    ).all() if equipment_ids else []
    if len(equipment_rows) != len(set(equipment_ids)):
        return jsonify({"code": 1, "message": "所选仪器设备不存在或已停用", "data": None}), 200
    from ..equipment_authorization import unauthorized_new_equipment
    unauthorized_equipment = unauthorized_new_equipment(user, r, equipment_rows)
    if unauthorized_equipment and not correcting("reports"):
        return jsonify(code=403, message="以下仪器所属部门未授权使用，请联系管理员配置仪器授权：" +
                       "、".join(f"{row.archive_no} {row.name}（{row.dept or '未登记部门'}）" for row in unauthorized_equipment),
                       data=None), 200
    interval_start = parse_date(test_start)
    interval_end = parse_date(test_end)
    invalid_equipment = []
    for equipment in equipment_rows:
        from ..equipment_eligibility import evaluate_intervals
        verdict = evaluate_intervals(equipment, intervals)
        reason = verdict['message'] if verdict['level'] == 'block' else ''
        if reason:
            invalid_equipment.append(f"{equipment.archive_no} {equipment.name}（{reason}）")
    if invalid_equipment and (validate_for_completion or (intervals and all(
        part.get("start") and part.get("end") for part in intervals
    ))):
        return jsonify({"code": 1, "message": "以下设备不覆盖全部试验区间：" + "、".join(invalid_equipment), "data": None}), 200
    refresh_references = r.status in ("检测录入中", "退回待重传", "检测更改中")
    equipment_display = body.get("equipmentDisplay") or {}
    if refresh_references:
        equipment_by_id = {row.id: row for row in equipment_rows}
        equipment_rows = [equipment_by_id[eid] for eid in dict.fromkeys(equipment_ids)]
    equipment_snapshots = [{
        "id": row.id,
        "archiveNo": row.archive_no or "",
        "name": row.name or "",
        "spec": row.spec or "",
        "maker": row.maker or "",
        "factoryNo": row.factory_no or "",
        "range": row.meas_range or "",
        "accuracy": row.accuracy or "",
        "cert": row.cert or "",
        "certificateNo": row.certificate_no or "",
        "planCalDate": row.plan_cal_date or "",
        "calUnit": row.cal_unit or "",
        "period": row.period or "",
        "lastCalDate": row.actual_cal_date or row.last_cal_date or "",
        "validUntil": row.valid_until or row.plan_cal_date or "",
    } for row in equipment_rows]

    if not refresh_references:
        saved_equipment = {item['id']: item for item in ((r.detail or {}).get('checkInput') or {}).get('equipmentSnapshots') or []}
        equipment_snapshots = [saved_equipment.get(item['id'], item) for item in equipment_snapshots]

    def equipment_text(item):
        parts = [item["name"]]
        if equipment_display.get("archiveNo") and item["archiveNo"]:
            parts.append(f"档案号：{item['archiveNo']}")
        if equipment_display.get("spec") and item["spec"]:
            parts.append(f"型号：{item['spec']}")
        if equipment_display.get("maker") and item["maker"]:
            parts.append(f"厂商：{item['maker']}")
        if equipment_display.get("factoryNo") and item["factoryNo"]:
            parts.append(f"出厂编号：{item['factoryNo']}")
        return "；".join(parts)

    instrument = "、".join(equipment_text(item) for item in equipment_snapshots)
    if not instrument:
        instrument = (body.get("instrument") or "").strip()

    def authorized_person(code, permission, label):
        code = str(code or "").strip()
        if not code:
            return None, None
        person = Personnel.query.filter_by(code=code, deleted_at=None).first()
        if not person:
            return None, f"{label}人员不存在"
        permissions = [item for item in (person.permissions or "").split(";") if item]
        if permission not in permissions:
            return None, f"{person.name}未取得“{permission}”授权"
        allowed_departments = [person.dept] + [item for item in (person.assigned_depts or "").split(";") if item]
        if r.department and r.department not in allowed_departments:
            return None, f"{person.name}未授权到当前检测部门"
        account_user = User.query.filter(
            db.func.lower(User.account) == code.lower()
        ).first()
        step_code = {
            "数据录入": "data_entry",
            "审核": "report_review",
            "批准": "report_approval",
        }.get(permission)
        project = project_for_report(r)
        if project and (
            not account_user
            or not step_code
            or not user_has_project_step(account_user, project, step_code)
        ):
            return None, f"{person.name}未取得当前项目的“{permission}”任命授权"
        return {"id": person.id, "code": person.code, "name": person.name}, None

    def authorized_project_person(code, permission, label, step_code):
        """Use organization project-step grants as the source of truth."""
        code = str(code or "").strip()
        if not code:
            return None, None
        project = project_for_report(r)
        if project is None:
            # Historical records may not have a project identity. Retain the
            # legacy personnel check only for those old records.
            return authorized_person(code, permission, label)
        account_user = User.query.filter(
            db.func.lower(User.account) == code.lower()
        ).first()
        if not account_user or not account_user.enabled:
            return None, f"{label}账号不存在或已停用"
        if not user_has_project_step(account_user, project, step_code):
            return None, (
                f"{account_user.name}未取得当前项目"
                f"“{project.name}”的“{permission}”授权"
            )
        return {
            "id": account_user.id,
            "code": account_user.account,
            "name": account_user.name,
        }, None

    people = {}
    previous_people = ((r.detail or {}).get("checkInput") or {}).get("people") or {}
    for key, permission, label in (
        ("primaryTester1", "数据录入", "主检1"),
        ("primaryTester2", "数据录入", "主检2"),
        ("reviewer", "审核", "审核人"),
        ("approver", "批准", "批准人"),
    ):
        step_code = {
            "primaryTester1": "data_entry",
            "primaryTester2": "data_entry",
            "reviewer": "report_review",
            "approver": "report_approval",
        }[key]
        if correcting("reports") and f"{key}Code" not in body:
            if key in previous_people:
                people[key] = previous_people[key]
            continue
        if not refresh_references and key in previous_people and body.get(f"{key}Code") == previous_people[key].get("code"):
            people[key] = previous_people[key]
            continue
        person, error = authorized_project_person(
            body.get(f"{key}Code"), permission, label, step_code
        )
        if error and validate_for_completion:
            return jsonify({"code": 1, "message": error, "data": None}), 200
        if error:
            draft_code = str(body.get(f"{key}Code") or "").strip()
            draft_user = User.query.filter(
                db.func.lower(User.account) == draft_code.lower()
            ).first() if draft_code else None
            person = {
                "id": draft_user.id if draft_user else 0,
                "code": draft_code,
                "name": (draft_user.name if draft_user else draft_code),
            } if draft_code else None
        if person:
            people[key] = person

    owner = (people.get("primaryTester1") or {}).get("name") or (body.get("owner") or "").strip()
    if correcting("reports") and "primaryTester1Code" not in body and "owner" not in body:
        owner = r.owner
    conclusion = (body.get("conclusion") or "").strip()           # 结论
    # 普通保存允许暂不选择结论；不得用默认“判定合格”污染报告首页。
    # 保存并完成检测时再要求操作者明确选择，避免空白数据被误判合格。
    result_status = (body.get("resultStatus") or "").strip()
    result_status = {"合格": "判定合格", "不合格": "判定不合格"}.get(
        result_status, result_status,
    )
    unqualified = (body.get("unqualifiedParams") or "").strip()   # 不合格参数
    record_no = (body.get("recordNo") or "").strip()
    result = (body.get("result") or "").strip()                   # 实测值
    assigned_reviewer = (
        (people.get("reviewer") or {}).get("name")
        or str(body.get("assignedReviewer") or "").strip()
    )
    assigned_approver = (
        (people.get("approver") or {}).get("name")
        or str(body.get("assignedApprover") or "").strip()
    )
    remark = (body.get("remark") or "").strip()                        # 备注
    calibration_time = str(body.get("calibrationTime") or "").strip()
    # Older clients omit these keys. Preserve saved values; an explicit empty value clears them.
    previous_input = (r.detail or {}).get("checkInput") or {}
    calibration_place = str(body.get("calibrationPlace", previous_input.get("calibrationPlace")) or "").strip()
    temperature = str(body.get("temperature", previous_input.get("temperature")) or "").strip()
    humidity = str(body.get("humidity", previous_input.get("humidity")) or "").strip()
    pressure = str(body.get("pressure", previous_input.get("pressure")) or "").strip()
    from ..report_business_date import report_date as approved_report_date
    report_date = approved_report_date(r)
    standard_show_name = bool(body.get("standardShowName"))
    standard_separator_value = standard_separator(body.get("standardSeparator"))
    title_styles = body.get("standardTitleStyles", previous_input.get("standardTitleStyles", {}))
    if not isinstance(title_styles, dict) or any(value not in ("CN", "EN", "none") for value in title_styles.values()):
        return jsonify({"code": 1, "message": "请选择中文书名号、英文书名号或不加书名号", "data": None}), 200
    style_keys = [*standard_values, *['id:' + str(i) for i in ((r.detail or {}).get('rawSample') or {}).get('standardItemIds') or []]]
    title_styles = {key: title_styles[key] for key in style_keys if key in title_styles}
    try:
        separator_text = display_separator(body.get("standardSeparatorText", previous_input.get("standardSeparatorText")), SEPARATORS[standard_separator_value])
        equipment_separator = display_separator(body.get("equipmentSeparatorText", previous_input.get("equipmentSeparatorText")))
        from ..functions.report_standard_text import judgment_display_settings
        judgment_display = body.get("judgmentDisplay", previous_input.get("judgmentDisplay"))
        if judgment_display is not None:
            judgment_display = judgment_display_settings(judgment_display)
    except ValueError as exc:
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    raw_sample = dict((r.detail or {}).get("rawSample") or {})
    # Adopt the commission layout on an editable save so a renderer upgrade
    # alone cannot change the input projection of an already confirmed version.
    items_separator = raw_sample.get("itemsSeparator") if refresh_references else previous_input.get("itemsSeparator")
    if refresh_references:
        from ..entry_references import current_entry_references
        try:
            raw_sample.update(current_entry_references(raw_sample, user, r.department,
                completing=validate_for_completion, correcting=correcting("reports")))
        except ValueError as exc:
            return jsonify(code=1, message=str(exc), data=None), 200
    if standard_values:
        raw_sample["testBases"] = standard_values
        raw_sample["testBasis"] = standard
    report_format = " ".join(str(raw_sample.get(key) or "") for key in ("reportFormat", "reportType", "reportCategory"))
    is_calibration = "校准" in report_format
    if validate_for_completion and not result_status:
        return jsonify({"code": 1, "message": "请选择结论状态", "data": None}), 200
    if validate_for_completion and result_status not in ("判定合格", "判定不合格", "不判定"):
        return jsonify({"code": 1, "message": "结论状态只能选择判定合格、判定不合格或不判定", "data": None}), 200
    if validate_for_completion and result_status == "判定不合格" and not unqualified:
        return jsonify({"code": 1, "message": "判定不合格时必须填写不合格参数", "data": None}), 200
    if validate_for_completion and is_calibration and not calibration_time:
        return jsonify({"code": 1, "message": "校准报告必须填写校准时间", "data": None}), 200
    if validate_for_completion:
        _validated_start, _validated_end, date_error = _validated_test_dates(
            user, r, test_start, test_end,
        )
        if date_error:
            return jsonify({"code": 1, "message": date_error, "data": None}), 200

    if validate_for_completion and (not standard or not instrument or not test_start or not test_end):
        return jsonify({
            "code": 1,
            "message": "检测标准、试验设备、试验开始日期、试验结束日期为必填",
            "data": None,
        }), 200

    before = r.to_row()
    detail = dict(r.detail or {})
    from ..report_scope import report_seal
    seal = report_seal(detail)
    previous_entry_staff = (detail.get("checkInput") or {}).get("entryStaff")
    entry_staff = previous_entry_staff if previous_entry_staff is not None else (
        {} if correcting("reports") else {"id": user.id, "account": user.account, "name": user.name or user.account}
    )
    # 三库仪器校验使用完整试验区间；testDate保留为历史兼容的结束日期。
    standard_names = load_report_standard_names(standard_values, raw_sample.get("standardItemIds")) if standard_show_name else {}
    standard_records = load_report_standard_records(standard_values, raw_sample.get("standardItemIds"))
    if not refresh_references and (not correcting("reports") or standard_values == (previous_input.get("standards") or [])):
        standard_names = previous_input.get('standardNames', {})
        standard_records = previous_input.get('standardRecords', [])
    standard_display = format_report_standards(
        standard_values, standard_names, standard_show_name, standard_separator_value,
        styles=title_styles, separator_text=separator_text, records=standard_records,
    )
    detail["checkInput"] = {
        "standard": standard, "standards": standard_values,
        "instrument": instrument, "testDate": test_end,
        "testStartDate": test_start, "seal": seal, "project": r.project,
        "testIntervals": intervals,
        "equipmentIds": equipment_ids,
        "equipmentSnapshots": equipment_snapshots,
        "equipmentDisplay": equipment_display,
        "standardShowName": standard_show_name,
        "standardSeparator": standard_separator_value,
        "standardDisplay": standard_display,
        "standardTitleStyles": title_styles,
        "standardNames": standard_names,
        "standardRecords": standard_records,
        "standardSeparatorText": separator_text,
        "equipmentSeparatorText": equipment_separator,
        **({"itemsSeparator": items_separator} if isinstance(items_separator, str) and items_separator != "、" else {}),
        "calibrationTime": calibration_time,
        "calibrationPlace": calibration_place,
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        # Keep historical values immutable; incoming legacy date keys are ignored.
        **{key: previous_input[key] for key in ("specialReportDate", "reportDate") if key in previous_input},
        "resultStatus": result_status,
        "unqualifiedParams": unqualified,
        "conclusion": conclusion,
        "remark": remark,
        "recordNo": record_no,
        "result": result,
        "people": people,
        "entryStaff": entry_staff,
        # 普通保存会显式清除此标志；只有“保存并完成检测”的严格保存可置为真。
        "validatedForCompletion": validate_for_completion,
    }
    # 普通保存即表示检测数据录入已实际开始；完成检测仍由独立接口处理。
    if judgment_display is not None:
        detail["checkInput"]["judgmentDisplay"] = judgment_display
    detail["dataEntryStarted"] = True
    # 指定审核/批准人单独留存
    detail["assigned"] = {"reviewer": assigned_reviewer, "approver": assigned_approver, "people": people}
    # 检测录入完成 → 记录主检电子签名（取当前用户签名，缺省用姓名）
    if validate_for_completion and not correcting("reports"):
        sigs = dict(detail.get("signatures") or {})
        sigs["主检"] = (g.current_user.e_signature or g.current_user.name or "").strip()
        detail["signatures"] = sigs
    status_text = result_status or "—"
    conc_full = conclusion or result_status or "—"
    raw_sample["homepageRemark"] = remark
    detail["rawSample"] = raw_sample
    for sec in detail.get("summary", []):
        if sec.get("title") == "实验信息":
            sec["fields"] = [
                ["检测项目", r.project], ["执行标准", standard_display], ["试验设备", instrument],
                ["试验时间区间", "；".join(f"{item['start']} 至 {item['end']}" for item in intervals)],
                ["校准时间", calibration_time or "—"], ["报告日期", report_date or "—"],
                ["校准地点", calibration_place or "—"], ["温度", temperature or "—"],
                ["湿度", humidity or "—"], ["大气压力", pressure or "—"],
                ["数据录入人员", " / ".join(str(entry_staff.get(k) or "") for k in ("account", "name")).strip(" / ") or "—"],
                ["主检1", (people.get("primaryTester1") or {}).get("name") or "—"],
                ["主检2", (people.get("primaryTester2") or {}).get("name") or "—"],
                ["指定审核人", assigned_reviewer or "—"], ["指定批准人", assigned_approver or "—"],
            ]
        elif sec.get("title") == "项目信息":
            fields = [list(field) for field in sec.get("fields", [])]
            updated = False
            for field in fields:
                if field and field[0] == "报告首页备注":
                    field[1] = remark or "—"
                    updated = True
            if not updated:
                fields.append(["报告首页备注", remark or "—"])
            sec["fields"] = fields
        elif sec.get("title") == "原始记录":
            sec["fields"] = [
                ["记录编号", record_no or "—"], ["实测值", result or "—"],
                ["结论状态", status_text],
                ["不合格参数", unqualified or "—"],
                ["结论", conc_full], ["备注", remark or "—"], ["校核状态", "检测人员已录入"],
            ]
    result = save_test_draft(
        user,
        r.report_no,
        detail=detail,
        owner=owner,
        validate_for_completion=validate_for_completion,
        equipment_rows=equipment_rows,
        used_from=test_start,
        used_to=test_end,
        interval_end=interval_end,
        alignment_note=("已按样品单标准更新；原检测标准：" + "、".join(requested_standards) +
                        "；登记标准：" + "、".join(sample_standards)) if standards_differ else "",
    )
    if result.response_payload().get('code') == 0:
        from ..preview_cache import schedule_after_save
        schedule_after_save(r)
    payload = result.response_payload()
    return jsonify(payload), result.http_status


@bp.get("/<report_no>/testinfo-completion-state")
@require_auth
def testinfo_completion_state(report_no):
    """Read back the server state after a completion response was lost."""
    view = request.args.get("view")
    if view not in {"data_entry", "data_change"}:
        return jsonify(code=400, message="检测完成核对入口无效", data=None), 400
    user = g.current_user
    if f"testing.{view}.view" not in user.permission_codes():
        return jsonify(code=403, message="无当前检测模块查看权限", data=None), 403
    report = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not report:
        return jsonify(code=404, message="报告不存在或不在数据范围内", data=None), 404
    grant_error = report_data_entry_step_error(user, report)
    if grant_error:
        return jsonify(code=403, message=grant_error, data=None), 403
    from ..functions.esign_stages import current_flow
    if view == "data_entry":
        editable = report.status == "检测录入中" and report.sample_status == "已领取"
    else:
        editable = report.status == "检测更改中"
    flow = current_flow(report) if editable and not report.voided else None
    response = jsonify(code=0, message="ok", data={
        "status": "已作废" if report.voided else report.status,
        "esignPending": flow is not None,
        "stillEditable": editable and not report.voided and flow is None,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/<report_no>/testinfo-complete")
@require_auth
def complete_testinfo(report_no):
    """检测人员确认录入完成：检测录入中 → 待审核（不再经过报告校核）。"""
    user = g.current_user
    if "testing.data_entry.view" not in user.permission_codes():
        return jsonify({"code": 403, "message": "无检测信息录入权限", "data": None}), 200
    r = _scope_filter(Report.query, user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    grant_error = project_step_error(user, r, "data_entry", "数据录入")
    if grant_error:
        return jsonify({"code": 403, "message": grant_error, "data": None}), 200
    if r.status != "检测录入中" or (r.sample_status or "") != "已领取":
        return jsonify({
            "code": 1,
            "message": f"报告当前为「{r.status}」、样品为「{r.sample_status or '待入库'}」，不能完成检测录入",
            "data": None,
        }), 200
    check_input = (r.detail or {}).get("checkInput") or {}
    if not check_input.get("validatedForCompletion"):
        return jsonify({
            "code": 1,
            "message": "请点击“保存并完成检测”，完成必填项及三库校验后再提交",
            "data": None,
        }), 200
    missing = [name for name, key in (
        ("检测标准", "standard"),
        ("试验设备", "instrument"),
        ("试验开始日期", "testStartDate"),
        ("试验结束日期", "testDate"),
    ) if not check_input.get(key)]
    if missing:
        return jsonify({"code": 1, "message": "检测数据尚未完整：" + "、".join(missing), "data": None}), 200
    _test_start, _test_end, date_error = _validated_test_dates(
        user, r, check_input.get("testStartDate"), check_input.get("testDate"),
    )
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    eln_error = eln_completion_error(r)
    if eln_error:
        return jsonify({"code": 1, "message": eln_error, "data": None}), 200
    result = complete_test_data(
        user,
        r.report_no,
        completion_blocker=eln_error,
        signing_workflow=(request.get_json(silent=True) or {}).get("signingWorkflow"),
    )
    return jsonify(result.response_payload()), result.http_status


from ..list_reads import reuse_list_reads


@bp.post("/query")
@require_auth
@reuse_list_reads
def query():
    user = g.current_user
    body = request.get_json(silent=True) or {}
    view = str(body.get("view") or "query").strip()
    if view not in REPORT_LIST_VIEW_PERMISSIONS:
        return jsonify({"code": 1, "message": "报告列表模块无效", "data": None}), 200
    if not _report_list_view_allowed(user, view):
        return jsonify({"code": 403, "message": "无当前报告模块查看权限", "data": None}), 200
    # Correction users retain full query scope except the explicit pending
    # choice in the two entry pages. Reuse the ordinary view and its unchanged
    # project/state/recall predicates; the hint never grants an action.
    handling_view = body.get('handlingView')
    if (view == 'query' and body.get('presentation') == 'entry'
            and body.get('rowProjection') == 'active'
            and handling_view in ('data_entry', 'data_change')
            and can_correct_business_data(user)):
        view = handling_view
        body = dict(body, view=view)
    keyword = (body.get("keyword") or "").strip()
    status = (body.get("status") or "").strip()

    q = _scope_filter(Report.query, user)
    page_meta = None
    page_records = None
    if body.get('serverPage') and view != 'dashboard':
        from ..list_paging import load_report_page
        try:
            page_records, page_meta = load_report_page(q, user, view, body)
        except (ValueError, TypeError) as exc:
            return jsonify({'code': 1, 'message': str(exc), 'data': None}), 200
        keyword = status = ''
    from ..issuance_data_status import ISSUANCE_STATUSES, current_flows, flow_label
    display_status = status if status in ISSUANCE_STATUSES | {"报告已盖章，归档中，未发放", "报告已归档，发放中", "报告发放完成"} else str(body.get("dataStatus") or "")
    if page_meta is not None:
        display_status = ''
    if status and status != display_status:
        q = q.filter(Report.status == status)

    from ..list_projection import list_reports, list_entrusts
    if page_records is None:
        if view == 'query' and body.get('presentation') == 'report':
            from ..list_page_access import current_report_query
            q = current_report_query(q)
        from ..report_groups import apply_report_group
        try:
            q = apply_report_group(q, body.get('reportGroup'))
        except ValueError as exc:
            return jsonify({'code': 1, 'message': str(exc), 'data': None}), 200
        page_records = list_reports(q)
    report_pairs = records_by_edit_time(
        page_records,
        "report",
        lambda report: report.report_no,
    )
    reports = [report for report, _edited_at in report_pairs]
    if page_meta is not None:
        # records_by_edit_time primes batched audit reads; SQL owns page order.
        order = {r.report_no: i for i, r in enumerate(page_records)}
        report_pairs.sort(key=lambda pair: order[pair[0].report_no])
    signing_flows = current_flows(reports)
    from ..business_rows import paginate_rows, report_business_row, row_contains, row_in_date_range
    entrusts = {
        item.entrust_no: item for item in list_entrusts(Entrust.query.filter(
            Entrust.entrust_no.in_([r.entrust_no for r in reports if r.entrust_no])
        ))
    } if reports else {}
    from ..applications.report_lifecycle.dashboard import report_todo_view
    dashboard_actions = set(user.action_codes()) if view == "dashboard" else set()
    rows = []
    for report, edited_at in report_pairs:
        todo_view = report_todo_view(user, report, actions=dashboard_actions) if view == "dashboard" else None
        if view == "dashboard" and not todo_view:
            continue
        row = report_business_row(report, entrusts.get(report.entrust_no),
                                  issuance_label=flow_label(signing_flows.get(report.id)))
        row["editedAt"] = edit_time_text(edited_at)
        if todo_view:
            row["todoView"] = todo_view
            row["rowProjection"] = "active"
            rows.append(row)
            continue
        completion = latest_operation_audit(
            "report", report.report_no, "report.data_entry.complete",
        )
        row["dataEntryCompletionAccount"] = completion.account if completion else ""
        row["dataEntryCompletionUserName"] = completion.user_name if completion else ""
        row["allowedActions"] = _legacy_allowed_actions(user, report)
        projection = report_projection(row, view)
        if view == 'release' and body.get('rowProjection') and projection != body['rowProjection']:
            continue
        if projection:
            if projection == "active" and report_processing_step_error(
                user, report, view
            ):
                continue
            row["rowProjection"] = projection
            rows.append(row)
    if view in {'query','review','approval','print','archive','release'} or body.get('presentation') in {'entry','registration-sample'}:
        from ..applications.report_lifecycle.query_details import query_details
        visible = {row['reportNo'] for row in rows}
        details = query_details((r for r in reports if r.report_no in visible),
                                stage_keys=('dataSaved','dataCompleted') if body.get('presentation') == 'entry' else ('contractReviewed',) if body.get('presentation') == 'registration-sample' else None)
        for row in rows:
            row.update(details[row['reportNo']])
    if display_status:
        rows = [row for row in rows if row["dataStatus"] == display_status]
    if keyword:
        rows = [row for row in rows if row_contains(row, keyword)]
    rows = [row for row in rows if row_in_date_range(
        row, body.get("startDate"), body.get("endDate"),
        ("sampleRegisteredAt", "sendDate", "samplingTime", "reviewedAt"),
    )]
    return jsonify({"code": 0, "message": "ok", "data": {
        **({'rows': rows, **page_meta} if page_meta is not None else paginate_rows(rows, body)),
    }})


@bp.get("/<report_no>/compliance-preflight")
@require_auth
def compliance_preflight(report_no):
    from ..compliance import build_compliance_preflight

    stage = str(request.args.get("stage") or "").strip()
    if stage not in {"contract_review", "report_review", "report_approval"}:
        return jsonify({"code": 1, "message": "合规核查阶段无效", "data": None}), 200
    permissions, _step_code, label = COMPLIANCE_STAGE_ACCESS[stage]
    if not has_function_permission(g.current_user, *permissions):
        return jsonify({
            "code": 403, "message": f"无{label}查看权限", "data": None,
        }), 200
    r = _scope_filter(Report.query, g.current_user).filter(Report.report_no == report_no).first()
    if not r:
        return jsonify({"code": 1, "message": "报告不存在或不在数据范围内", "data": None}), 200
    access_error = compliance_stage_access_error(g.current_user, r, stage)
    if access_error:
        return jsonify({"code": 403, "message": access_error, "data": None}), 200
    try:
        data = build_compliance_preflight(r, stage)
    except ValueError as exc:
        return jsonify({"code": 1, "message": str(exc), "data": None}), 200
    return jsonify({"code": 0, "message": "ok", "data": data})


@bp.post("/<report_no>/standard-resolution")
@require_auth
def resolve_report_standards(report_no):
    from ..standard_resolution import resolve_identities
    from ..compliance import build_compliance_preflight
    body = request.get_json(silent=True) or {}
    stage = body.get('stage')
    if stage not in COMPLIANCE_STAGE_ACCESS:
        return jsonify(code=1, message='合规核查阶段无效', data=None), 200
    permissions, _, label = COMPLIANCE_STAGE_ACCESS[stage]
    if not has_function_permission(g.current_user, *permissions):
        return jsonify(code=403, message='无' + label + '权限', data=None), 200
    report = _scope_filter(Report.query, g.current_user).filter_by(report_no=report_no).with_for_update().first()
    if not report:
        return jsonify(code=403, message='报告不存在或不在数据范围内', data=None), 200
    error = compliance_stage_access_error(g.current_user, report, stage)
    if error:
        return jsonify(code=403, message=error, data=None), 200
    action, expected = {'contract_review': ('report.contract_review.pass', '待合同评审'),
                        'report_review': ('report.review.pass', '待审核'),
                        'report_approval': ('report.approval.pass', '待批准')}[stage]
    if report.voided or report.status != expected or not (can_correct_business_data(g.current_user) or action in g.current_user.action_codes()):
        return jsonify(code=403, message='当前状态或权限不允许确认标准关联', data=None), 200
    preflight = build_compliance_preflight(report, stage)
    if body.get('preflightVersion') != preflight['preflightVersion']:
        return jsonify(code=1, message='校核结果已变化，请重新校核后选择', data=None), 200
    try:
        resolve_identities(report, g.current_user, body.get('selections'), body.get('reason'))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(code=1, message=str(exc), data=None), 200
    return jsonify(code=0, message='标准关联已保存，请重新校核资质和报告内容', data=build_compliance_preflight(report, stage)), 200


@bp.get("/<report_no>/records")
@require_auth
def report_workflow_records(report_no):
    view = str(request.args.get("view") or "").strip()
    report, _projection, error = get_authorized_report_for_view(g.current_user, report_no, view)
    if error:
        return jsonify({"code": 403, "message": error, "data": None}), 200
    kind = request.args.get("kind", "commission")
    try:
        page, size = int(request.args.get("page", 1)), int(request.args.get("pageSize", 10))
        if kind not in {"commission", "testing", "issues", "workflow"} or page < 1 or size not in {10, 20, 50}:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"code": 1, "message": "记录查询参数无效", "data": None}), 200
    from ..applications.report_lifecycle.records import report_records
    response = jsonify({"code": 0, "message": "ok", "data": report_records(report.report_no, kind, page, size)})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/<report_no>")
@require_auth
def detail(report_no):
    user = g.current_user
    view = str(request.args.get("view") or "").strip()
    r, _projection, access_error = get_authorized_report_for_view(
        user, report_no, view
    )
    if access_error:
        code = 1 if access_error in {"报告详情入口无效", "报告不存在或不在数据范围内"} else 403
        return jsonify({"code": code, "message": access_error, "data": None}), 200
    projection = request.args.get("projection")
    if projection == "sample_form_image":
        # Same authorization as text/full detail. Never store a public image URL.
        image = ((r.detail or {}).get("rawSample") or {}).get("trademarkImage") or ""
        revision = hashlib.sha256(image.encode("utf-8")).hexdigest()
        if request.args.get("image_revision") != revision:
            return jsonify({"code": 1, "message": "商标图样已变化，请关闭后重新打开样品单", "data": None}), 200
        response = jsonify({"code": 0, "message": "ok", "data": {"reportNo": r.report_no, "trademarkImage": image}})
        response.headers["Cache-Control"] = "no-store"
        return response
    data = r.to_row()
    data.update(r.detail or {})
    from ..sample_identity import sample_number
    data["sampleNo"] = sample_number(r)
    data["reportNo"] = r.report_no
    from ..seal_requirements import requested_seal
    data["requestedSeal"] = requested_seal(r.detail)
    data["editVersion"] = r.edit_version
    data["testEditVersion"] = test_form_version(r)
    from ..scope_summary import project_standard_scope
    data = project_standard_scope(r, data)
    data["projectName"] = r.project_name
    from ..list_reads import erp_contract_number
    data["erpContractNo"] = erp_contract_number(r.report_no)
    if projection in {"sample_form", "sample_form_text"}:
        # Same feature/state/data authorization above; a form read must not
        # execute report checks or signature assembly. Completion still uses
        # the existing authoritative validation endpoints.
        keys = ("editVersion", "reportNo", "sampleNo", "sampleRegState", "rawSample",
                "summary", "entrustSnapshot", "projectName", "erpContractNo", "requestedSeal",
                "reportCategory", "derivedFrom", "mainReportNo", "department")
        data.update(reportNo=r.report_no, sampleRegState=r.sample_reg_state, mainReportNo=r.main_report_no, department=r.department)
        if r.report_kind in {"english", "supplement", "itemized"}:
            data["reportCategory"] = {"english": "英文", "supplement": "补充", "itemized": "分项"}[r.report_kind]
        form = {key: data.get(key) for key in keys}
        if projection == "sample_form_text":
            raw = dict(form.get("rawSample") or {})
            image = raw.get("trademarkImage") or ""
            form["trademarkImageDeferred"] = bool(image)
            if image:
                form["trademarkImageRevision"] = hashlib.sha256(image.encode("utf-8")).hexdigest()
                raw["trademarkImage"] = ""
                form["rawSample"] = raw
        response = jsonify({"code": 0, "message": "ok", "data": form})
        response.headers["Cache-Control"] = "no-store"
        return response
    # 检测录入草稿不执行三库校验；完成校验后及后续环节才展示校验结果。
    check_input = (r.detail or {}).get("checkInput") or {}
    if check_input.get("validatedForCompletion") or r.status not in ("检测录入中", "退回待重传", "检测更改中"):
        checks, _danger, _note = compute_report_checks(r)
        data["checks"] = checks
        data["outOfScope"] = _danger
        data["outOfScopeNote"] = _note
    else:
        data["checks"] = []
    # 签名状态（主检/审核/批准）+ 样品流转状态实时回填
    data["signatures"] = signature_state(r)
    # 补齐成完整结构（查看完整信息）
    data["summary"] = augment_report_summary(data.get("summary", []))
    for sec in data["summary"]:
        sec["fields"] = [
            [k, (data["dataStatus"] if k == "流转状态" else v)] for k, v in sec.get("fields", [])
        ]
    return jsonify({"code": 0, "message": "ok", "data": data})


@bp.post("/<report_no>/action")
@require_auth
def action(report_no):
    """Thin HTTP adapter for the canonical report lifecycle Command."""

    body = request.get_json(silent=True) or {}
    result = execute_report_action(
        g.current_user,
        report_no,
        body.get("action"),
        body,
    )
    return jsonify(result.response_payload()), result.http_status


@bp.route('/<report_no>/scope-review', methods=['GET', 'POST'])
@require_auth
def scope_review(report_no):
    from ..report_scope import assess_scope
    from ..platform.identity.access import has_action_permission
    from ..platform.audit import add_operation_audit
    user = g.current_user
    view = str(request.args.get('view') or '').strip()
    report, _projection, error = get_authorized_report_for_view(user, report_no, view)
    if error:
        return jsonify({'code': 403, 'message': error, 'data': None}), 403
    permitted = has_action_permission(user, 'report.scope.review')
    if request.method == 'GET':
        data = assess_scope(report); data['canReview'] = permitted
        return jsonify({'code': 0, 'message': 'ok', 'data': data})
    if not permitted:
        return jsonify({'code': 403, 'message': '无范围复核权限', 'data': None}), 403
    from .report_publication import writable
    if not writable():
        return jsonify({'code': 403, 'message': '平台处于只读状态', 'data': None}), 403
    report = Report.query.filter_by(id=report.id).populate_existing().with_for_update().one()
    current = assess_scope(report)
    body = request.get_json(silent=True) or {}
    if body.get('fingerprint') != current['fingerprint']:
        return jsonify({'code': 409, 'message': '报告或能力依据已变化，请刷新后复核', 'data': None}), 409
    decision, reason = body.get('decision'), str(body.get('reason') or '').strip()
    if decision not in ('in_scope', 'out_of_scope', 'reset') or not 5 <= len(reason) <= 1000:
        return jsonify({'code': 1, 'message': '请选择复核结论，并填写5至1000字的依据或原因', 'data': None}), 400
    before = current.get('review')
    from datetime import datetime
    review = {'decision': decision, 'reason': reason, 'fingerprint': current['fingerprint'],
            'actor': user.account, 'actorName': user.name or user.account, 'at': datetime.utcnow().isoformat() + 'Z',
            'computedState': current['computedState']}
    # Immutable audit owns the classification. Never alter signed report source detail.
    add_operation_audit('report.scope.review', 'report', report_no, category='report',
        before=before, after=review, message='范围分类复核：' + reason)
    db.session.flush()
    after = assess_scope(report)
    report.out_of_scope = after['outOfScope']; report.out_of_scope_note = after['note'][:200] if after['outOfScope'] else ''
    db.session.commit()
    after['canReview'] = True
    return jsonify({'code': 0, 'message': '范围分类已更新，未变更资质授权和签署状态', 'data': after})

@bp.post('/issuance-record/export')
@require_auth
def export_issuance_record():
    from io import BytesIO
    from flask import send_file
    from ..document_module import render_issuance_record
    from ..report_issuance_records import issuance_row
    if not _report_list_view_allowed(g.current_user, 'release'):
        return jsonify(code=403, message='无报告发放模块查看权限', data=None), 403
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(code=1, message='导出参数格式错误', data=None), 400
    numbers = body.get('reportNos')
    kind = body.get('kind')
    if (kind not in ('product', 'engineering') or not isinstance(numbers, list)
            or not 1 <= len(numbers) <= 200
            or any(not isinstance(n, str) or not n.strip() or len(n) > 160 for n in numbers)):
        return jsonify(code=1, message='请选择产品类或工程类，并勾选1至200份报告', data=None), 400
    reports_to_export = []
    for number in dict.fromkeys(numbers):
        report, _, error = get_authorized_report_for_view(g.current_user, number, 'release')
        if error:
            return jsonify(code=403, message='所选报告已不可访问，请刷新列表后重新选择', data=None), 403
        reports_to_export.append(report)
    try:
        blob, _ = render_issuance_record(kind, [issuance_row(r) for r in reports_to_export])
    except ValueError as exc:
        return jsonify(code=1, message=str(exc), data=None), 400
    label = '工程类' if kind == 'engineering' else '产品类'
    response = send_file(BytesIO(blob), as_attachment=True,
        download_name=f'报告发放登记表（{label}）.docx',
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response.headers['Cache-Control'] = 'private, no-store'
    return response
