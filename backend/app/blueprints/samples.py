from app.organization_privileges import has_full_platform_authority
from ..admin_corrections import can_correct_business_data
"""样品流转查询：从报告派生样品入库/出库状态（按数据授权过滤）。"""
import hashlib
from types import SimpleNamespace
from urllib.parse import quote

from flask import Blueprint, Response, current_app, g, jsonify, request

from ..applications.report_lifecycle import scoped_report_query
from ..applications.sample_logistics import (
    execute_sample_dispose,
    execute_sample_inbound,
    execute_sample_inbound_undo,
    execute_sample_outbound_return,
    execute_sample_pickup,
    execute_sample_return_stock,
    execute_sample_void,
)
from ..platform.audit import (
    add_operation_audit,
    edit_time_text,
    latest_operation_audit,
    records_by_edit_time,
)
from ..business_rows import paginate_rows, report_business_row, row_contains, row_in_date_range
from ..extensions import db
from ..models import Entrust, Report, OperationAudit
from ..security import require_auth
from ..platform.identity import project_step_error
from ..platform.workflow import (
    SAMPLE_LIST_VIEW_PERMISSIONS,
    report_data_status,
    sample_matches_view,
)
from ..workflow_dates import business_today, latest_workflow_date, parse_date, validate_after_previous

bp = Blueprint("samples", __name__, url_prefix="/api/samples")


def _can_read_sample_form(user):
    permissions = set(user.permission_codes())
    return bool(has_full_platform_authority(user) or permissions.intersection({
        'entrust.registration.view', 'entrust.sample_register.view',
        'entrust.query.view', 'entrust.contract_review.view',
    }) or any(code.startswith(('sample.', 'report.')) for code in permissions))


def _sample_form_filename(sample_no, extension):
    safe_no = "".join(char for char in str(sample_no or "") if char.isalnum() or char in "-_")
    return f"{safe_no or 'sample'}-WT.{extension}"


def _content_disposition(disposition, sample_no, extension):
    filename = _sample_form_filename(sample_no, extension)
    return f"{disposition}; filename={filename}; filename*=UTF-8''{quote(filename)}"


def _outbound_data_entry_started(report):
    from ..data_entry_state import report_data_entry_started
    return report_data_entry_started(report)


def _business_form_page_count(pdf, template_kind):
    """Require the exact official template page count."""
    from ..entrust_render import require_business_form_page_count

    return require_business_form_page_count(pdf, template_kind)


def _preview_objects(body):
    snapshot = body.get("entrustSnapshot") or {}
    info = snapshot.get("info") or {}
    from ..contract_review_output import authoritative_review
    detail = authoritative_review(body, g.current_user)
    if 'rawSample' not in detail and isinstance(body.get('rawSample'), dict):
        detail['rawSample'] = dict(body['rawSample'])
    from ..sample_form_merge import normalize_judgment_entries
    normalize_judgment_entries(detail)
    raw = detail.get("rawSample") or body.get("rawSample") or {}
    entrust = SimpleNamespace(
        entrust_no=str(snapshot.get("entrustNo") or ""),
        contract_no=str(snapshot.get("contractNo") or ""),
        client=str(snapshot.get("client") or ""),
        project_name=str(snapshot.get("projectName") or ""),
        project_type=str(snapshot.get("projectType") or ""),
        amount=str(snapshot.get("amount") or ""),
        department=str(snapshot.get("department") or ""),
        owner=str(snapshot.get("owner") or ""),
        info=info if isinstance(info, dict) else {},
        created_at=None,
    )
    report = SimpleNamespace(
        detail=detail if isinstance(detail, dict) else {"rawSample": raw},
        report_no=str(body.get("reportNo") or ""),
        sample_no=str(body.get("sampleNo") or raw.get("sampleNo") or ""),
        project=str(body.get("project") or raw.get("project") or ""),
        department=str(body.get("department") or raw.get("testDept") or ""),
        owner=str(body.get("owner") or ""),
        project_name=str(body.get("projectName") or raw.get("sampleName") or ""),
        client=str(body.get("client") or snapshot.get("client") or ""),
        entrust_no=str(snapshot.get("entrustNo") or ""),
        report_kind=str(body.get("reportKind") or "main"),
        main_report_no=str(body.get("mainReportNo") or ""),
        deadline=str(body.get("deadline") or raw.get("deadline") or ""),
        sample_pickup={},
        sample_status="",
    )
    return entrust, report


def _preview_project_no(body, entrust, report):
    """Resolve the engineering project number without mutating stored data.

    Unsaved sample previews have no Agreement query to fall back to, so accept
    the same canonical field and historical aliases used by persisted forms.
    """
    snapshot = body.get("entrustSnapshot") or {}
    info = getattr(entrust, "info", None) or {}
    raw = (getattr(report, "detail", None) or {}).get("rawSample") or {}
    candidates = (
        body.get("erpProjectNo"), body.get("projectNo"),
        snapshot.get("erpProjectNo"), snapshot.get("projectNo"),
        raw.get("erpProjectNo"), raw.get("projectCode"),
        info.get("erpProjectNo"), info.get("projectCode"),
        info.get("projectRecordNo"), info.get("projectTradeCode"),
    )
    return next((str(value).strip() for value in candidates if str(value or "").strip()), "")


@bp.post("/entrust-preview")
@require_auth
def preview_sample_entrust():
    """Preview the current, possibly unsaved, sample-owned entrust snapshot."""
    if not _can_read_sample_form(g.current_user):
        return jsonify({"code": 403, "message": "无样品委托单预览权限", "data": None}), 200
    body = request.get_json(silent=True) or {}
    template_kind = str(body.get("templateKind") or "product").strip().lower()
    if template_kind not in ("product", "engineering", "product-extended", "engineering-extended"):
        return jsonify({"code": 1, "message": "模板类型无效，请选择产品类或工程类模板", "data": None}), 200
    language = body.get('outputLanguage', 'CN')
    if language not in ('CN', 'EN', 'BI'):
        return jsonify({"code": 1, "message": "请选择中文、英文或中英文", "data": None}), 200
    try:
        from .. import docparser_field_only
        from ..entrust_render import build_entrust_doc

        entrust, report = _preview_objects(body)
        project_no = _preview_project_no(body, entrust, report)
        if docparser_field_only.enabled():
            from ..entrust_source_cache import render as renderer
            docx, audit = renderer(
                entrust, report, template_kind, project_no, language,
            )
            template_name = audit["templateSelection"]["filename"]
        else:
            docx = build_entrust_doc(entrust, report, template_kind, project_no, language)
            template_name = template_kind
        if not docx:
            raise ValueError("未匹配到产品类或工程类委托单模板")
        if body.get('asyncPreview') is True:
            from ..entrust_preview_cache import prepare
            return prepare(docx, template_kind, g.current_user, {'headers': {
                'Content-Disposition': _content_disposition('inline', report.sample_no or report.report_no, 'pdf'),
                'X-Source-Document-SHA256': hashlib.sha256(docx).hexdigest(),
                'X-Template-Kind': template_kind,
            }}, retry=body.get('retryPreview') is True)
        from ..entrust_preview_cache import render_pdf
        pdf, actual_pages = render_pdf(docx, template_kind, page_counter=_business_form_page_count)
    except ValueError as error:
        return jsonify({"code": 1, "message": str(error), "data": None}), 200
    except RuntimeError as error:
        return jsonify({"code": 1, "message": str(error), "data": None}), 200
    except Exception:
        current_app.logger.exception("unsaved entrust preview failed")
        return jsonify({
            "code": 1,
            "message": "委托单预览生成失败，请检查报告编号、出具部门和模板要求",
            "data": None,
        }), 200
    preview_sample_no = report.sample_no or report.report_no
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "X-Source-Document-SHA256": hashlib.sha256(docx).hexdigest(),
            "X-Template-Kind": template_kind,
            "X-Template-Selection": template_name,
            "X-Expected-Pages": str(actual_pages),
            "X-Preview-Engine": "wps",
            "Content-Disposition": _content_disposition("inline", preview_sample_no, "pdf"),
        },
    )


@bp.post("/<report_no>/void")
@require_auth
def void_sample(report_no):
    result = execute_sample_void(g.current_user, report_no)
    data = result.report.to_row() if result.report is not None else None
    return jsonify(result.response_payload(data=data)), result.http_status


def _copy_source_permission(user):
    # Copying is a form read, never permission to operate an old workflow node.
    return has_full_platform_authority(user) or bool(
        {"entrust.sample_register.view", "sample.change.view"} & set(user.permission_codes())
    )


@bp.post("/copy-sources/query")
@require_auth
def query_copy_sources():
    if not _copy_source_permission(g.current_user):
        return jsonify({"code": 403, "message": "无样品复制权限", "data": None})
    body = request.get_json(silent=True) or {}
    try:
        page = max(1, int(body.get("page") or 1))
        size = min(100, max(1, int(body.get("pageSize") or 50)))
    except (TypeError, ValueError):
        return jsonify({"code": 1, "message": "分页参数无效", "data": None})
    keyword = str(body.get("keyword") or "").strip().casefold()
    pairs = records_by_edit_time(
        scoped_report_query(Report.query, g.current_user).all(),
        "report", lambda report: report.report_no,
    )
    rows = []
    for report, edited_at in pairs:
        # All saved lifecycle states, including explicitly labelled voided rows.
        row = {"reportNo": report.report_no, "sampleNo": report.sample_no,
               "client": report.client, "project": report.project,
               "projectName": report.project_name, "department": report.department,
               "status": report.status, "sampleStatus": report.sample_status,
               "archiveState": report.archive_state, "voided": bool(report.voided),
               "editedAt": edit_time_text(edited_at)}
        if not keyword or any(keyword in str(row.get(key) or "").casefold()
                              for key in ("reportNo", "sampleNo", "client", "project", "projectName")):
            rows.append(row)
    return jsonify({"code": 0, "message": "ok", "data": paginate_rows(rows, {"page": page, "pageSize": size})})


@bp.get("/copy-sources/<report_no>")
@require_auth
def get_copy_source(report_no):
    if not _copy_source_permission(g.current_user):
        return jsonify({"code": 403, "message": "无样品复制权限", "data": None})
    report = scoped_report_query(Report.query, g.current_user).filter_by(report_no=report_no).first()
    if report is None:
        return jsonify({"code": 1, "message": "样品不存在或不在数据范围内", "data": None})
    detail = report.detail or {}
    from ..seal_requirements import requested_seal
    from ..sample_identity import sample_number
    from ..sample_entrust import report_entrust_snapshot
    entrust = Entrust.query.filter_by(entrust_no=report.entrust_no).first() if report.entrust_no else None
    snapshot = report_entrust_snapshot(report, entrust) if entrust else detail.get("entrustSnapshot")
    # No full-detail assembly, checks, generation, signatures, audit or writes.
    return jsonify({"code": 0, "message": "ok", "data": {
        "reportNo": report.report_no, "sampleNo": sample_number(report),
        "department": report.department, "entrustSnapshot": snapshot,
        "rawSample": detail.get("rawSample"), "summary": detail.get("summary") or [],
        "requestedSeal": requested_seal(detail),
    }})


from ..list_reads import reuse_list_reads


@bp.post("/plan-counts")
@require_auth
def plan_counts():
    """Group authorized identities in SQL; never build sample business rows."""
    user = g.current_user
    if not (has_full_platform_authority(user) or can_correct_business_data(user)
            or 'sample.flow_query.view' in user.permission_codes()):
        return jsonify({'code': 403, 'message': '无样品流转查询权限', 'data': None})
    from sqlalchemy import func, case, and_
    from ..list_paging import j, first, scheme_fields, summary
    r = Report
    code, _name = scheme_fields()
    department = first(j(r.detail, 'rawSample.testDept'), summary('检测部门','检测科室'), r.department)
    early = ['待合同评审','待样品入库','待样品领取','检测录入中','退回待重传','委托更改中','检测更改中']
    predicates = {
        'flowSampleCount': db.true(),
        'disposalSampleCount': db.or_(r.sample_status == '已处置', and_(r.sample_status.in_(['已领取','已出库']), r.status.notin_(early))),
        'taskQuerySampleCount': r.sample_status.in_(['已领取','已出库']),
        'dataEntrySampleCount': r.status.in_(['检测录入中','退回待重传','待审核']),
        'dataChangeSampleCount': r.status == '检测更改中',
        'inboundSampleCount': r.status == '待样品入库',
        'outboundSampleCount': r.sample_status == '已入库',
    }
    query = scoped_report_query(r.query, user).filter(func.coalesce(r.voided, False).is_(False))
    values = query.with_entities(r.department.label('department'), department.label('test_department'),
        code.label('scheme_code'), *(case((predicate, 1), else_=0).label(key) for key, predicate in predicates.items())
    ).subquery()
    rows = db.session.query(values.c.department, values.c.test_department, values.c.scheme_code,
        *(func.sum(values.c[key]) for key in predicates)
    ).group_by(values.c.department, values.c.test_department, values.c.scheme_code).all()
    return jsonify({'code': 0, 'message': 'ok', 'data': {'rows': [
        dict(department=row[0], testDepartment=row[1], schemeCode=row[2], **dict(zip(predicates, map(int, row[3:]))))
        for row in rows]}})


@bp.post("/query")
@require_auth
@reuse_list_reads
def query():
    from ..platform.workflow import sample_return_stock_blocker

    user = g.current_user
    body = request.get_json(silent=True) or {}
    view = str(body.get("view") or "flow_query").strip()
    permission = SAMPLE_LIST_VIEW_PERMISSIONS.get(view)
    if not permission:
        return jsonify({"code": 1, "message": "样品列表模块无效", "data": None}), 200
    if not (
        has_full_platform_authority(user)
        or can_correct_business_data(user)
        or permission in user.permission_codes()
    ):
        return jsonify({"code": 403, "message": "无当前样品模块查看权限", "data": None}), 200
    keyword = (body.get("keyword") or "").strip()
    q = scoped_report_query(Report.query, g.current_user)
    page_meta = None
    page_records = None
    if body.get('serverPage'):
        from ..list_paging import load_report_page
        try:
            page_records, page_meta = load_report_page(q, user, view, body, samples=True)
        except (ValueError, TypeError) as exc:
            return jsonify({'code': 1, 'message': str(exc), 'data': None}), 200
        keyword = ''
    from ..list_projection import list_reports, list_entrusts
    if page_records is None:
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
    rows = [report for report, _edited_at in report_pairs]
    if page_meta is not None:
        order = {r.report_no: i for i, r in enumerate(page_records)}
        rows.sort(key=lambda row: order[row.report_no])
    include_voided = bool(body.get("includeVoided"))
    entrusts = {
        item.entrust_no: item for item in list_entrusts(Entrust.query.filter(
            Entrust.entrust_no.in_([r.entrust_no for r in rows if r.entrust_no])
        ))
    } if rows else {}
    out = []
    edited_times = {report.report_no: edited_at for report, edited_at in report_pairs}
    inbound_actors = {}
    if view == "flow_query" and rows:
        # Batch display columns only, not the large audit before/after payloads.
        records = db.session.query(OperationAudit.object_id, OperationAudit.user_name,
                                   OperationAudit.account).filter(
            OperationAudit.object_type == "report", OperationAudit.success.is_(True),
            OperationAudit.object_id.in_([r.report_no for r in rows]),
            OperationAudit.action.in_(("sample.inbound.confirm", "sample.mobile.inbound.confirm")),
        ).order_by(OperationAudit.id.desc()).all()
        for number, name, account in records:
            inbound_actors.setdefault(number, name or account or "")
    from ..issuance_data_status import current_flows, flow_label
    signing_flows = current_flows(rows)
    from ..applications.sample_logistics.flow_projection import sample_event_dates
    event_dates=sample_event_dates(rows)
    if body.get('presentation') == 'registration-sample':
        from ..applications.report_lifecycle.query_details import query_details
        for number, values in query_details(rows, stage_keys=('contractReviewed',)).items():
            event_dates[number]['contractReviewedAt'] = values['contractReviewedAt']
    for r in rows:
        if r.voided and not include_voided:
            continue  # Q4 默认：作废样品单从有效流程剔除，列表默认过滤、可勾选显示
        row = report_business_row(r, entrusts.get(r.entrust_no),
                                  issuance_label=flow_label(signing_flows.get(r.id)))
        from ..applications.sample_logistics.flow_projection import sample_flow_fields
        row.update(sample_flow_fields(r, inbound_actors.get(r.report_no, "")))
        row.update(event_dates.get(r.report_no,{}))
        data_entry_started = _outbound_data_entry_started(r)
        row["dataEntryStarted"] = data_entry_started
        row["dataStatus"] = report_data_status(
            r.status,
            r.sample_status,
            r.sample_reg_state,
            r.archive_state,
            r.voided,
            data_entry_started,
            row.get("dataStatus") if r.status == "待打印" else None,
            row.get("distributionComplete", False),
        )
        row["editedAt"] = edit_time_text(edited_times.get(r.report_no))
        completion = latest_operation_audit(
            "report", r.report_no, "sample.register.complete",
        )
        row["sampleRegistrationCompletionAccount"] = completion.account if completion else ""
        row["sampleRegistrationCompletionUserName"] = completion.user_name if completion else ""
        row["canRecallSampleRegistration"] = bool(
            r.status == "待合同评审"
            and (r.sample_reg_state or "") == "登记完成"
            and (
                has_full_platform_authority(user)
                or "sample.register.undo" in user.action_codes()
            )
        )
        from ..platform.workflow import sample_inbound_undo_blocker
        row["canUndoSampleInbound"] = bool(
            sample_inbound_undo_blocker(r) is None
            and "sample.inbound.confirm" in user.action_codes()
            and not project_step_error(user, r, "sample_inbound", "撤销入库")
        ) if view == "inbound" else False
        return_stock_blocker = sample_return_stock_blocker(r, data_entry_started)
        row["canReturnStock"] = return_stock_blocker is None
        row["returnStockBlockedReason"] = return_stock_blocker or ""
        row["canRecallSampleOutbound"] = bool(
            return_stock_blocker is None
            and (
                has_full_platform_authority(user)
                or "sample.return_stock" in user.action_codes()
            )
        )
        row["sampleOutboundRecallReason"] = return_stock_blocker or ""
        if not (view == "register" and can_correct_business_data(user)) and not sample_matches_view(r, row, view):
            continue
        step_rule = {
            "inbound": ("sample_inbound", "样品入库"),
            "outbound": ("sample_outbound", "样品出库并领取"),
        }.get(view)
        if step_rule and project_step_error(user, r, *step_rule):
            # 办理列表本身就是授权边界：无项目步骤权限的同部门人员
            # 不应先看到任务、再到动作阶段才被拒绝。查询模块仍按数据
            # 范围展示完整生命周期，不受这条办理步骤过滤影响。
            continue
        row["rowProjection"] = (
            "recall"
            if view == "outbound" and r.status == "检测录入中"
            else "active"
        )
        if keyword and not row_contains(row, keyword):
            continue
        if not row_in_date_range(row, body.get("startDate"), body.get("endDate"),
                                 ("sampleRegisteredAt", "sendDate", "samplingTime")):
            continue
        out.append(row)
    return jsonify({"code": 0, "message": "ok", "data": {'rows': out, **page_meta} if page_meta is not None else paginate_rows(out, body)})


def _parse_pdf_pages(raw_value, max_pages):
    value = str(raw_value or "").strip()
    if not value:
        return []
    tokens = [token.strip() for token in value.split(",")]
    if not tokens or any(not token.isdigit() for token in tokens):
        raise ValueError("导出页码格式无效，请使用逗号分隔的页码")
    pages = [int(token) for token in tokens]
    if len(set(pages)) != len(pages):
        raise ValueError("导出页码不能重复")
    if any(page < 1 or page > max_pages for page in pages):
        raise ValueError(f"导出页码超出范围，可选页码为 1-{max_pages}")
    return sorted(pages)


def _select_pdf_pages(pdf, pages):
    import fitz

    with fitz.open(stream=pdf, filetype="pdf") as source:
        selected = fitz.open()
        try:
            for page in pages:
                selected.insert_pdf(source, from_page=page - 1, to_page=page - 1)
            return selected.tobytes()
        finally:
            selected.close()


@bp.get('/entrust-preview-jobs/<ticket>')
@require_auth
def entrust_preview_job(ticket):
    from ..entrust_preview_cache import read
    return read(ticket, g.current_user)


@bp.get("/<report_no>/print")
@require_auth
def print_sample_form(report_no):
    """按用户选择的产品类或工程类正式模板打印样品单。"""
    from ..entrust_render import EXPECTED_PAGES, _document_kind, build_entrust_doc
    user = g.current_user
    if not _can_read_sample_form(user):
        return jsonify({"code": 403, "message": "无样品打印权限", "data": None}), 200
    report = scoped_report_query(Report.query, user).filter(Report.report_no == report_no).first()
    if not report:
        return jsonify({"code": 1, "message": "样品不存在或不在数据范围内", "data": None}), 200
    entrust = Entrust.query.filter(Entrust.entrust_no == report.entrust_no).first()
    if not entrust:
        return jsonify({"code": 1, "message": "样品未关联委托单，无法生成正式样品单", "data": None}), 200
    from ..sample_entrust import sample_entrust_object
    entrust = sample_entrust_object(report, entrust)
    template_kind = (request.args.get("templateKind") or "").strip().lower()
    if template_kind not in ("", "product", "engineering", "product-extended", "engineering-extended"):
        return jsonify({"code": 1, "message": "模板类型无效，请选择产品类或工程类模板", "data": None}), 200
    actual_kind = template_kind or _document_kind(entrust, report)
    try:
        from .. import docparser_field_only
        if docparser_field_only.applies_to_entrust(entrust):
            from ..entrust_source_cache import render as renderer
            docx, audit = renderer(
                entrust, report, actual_kind, "",
            )
            template_selection = audit["templateSelection"]["filename"]
        else:
            docx = build_entrust_doc(
                entrust, report, actual_kind, "",
            )
            template_selection = actual_kind
    except ValueError as error:
        return jsonify({"code": 1, "message": str(error), "data": None}), 200
    except Exception:
        current_app.logger.exception("persisted sample entrust print failed")
        return jsonify({"code": 1, "message": "委托单生成失败，请稍后重试", "data": None}), 200
    if not docx:
        return jsonify({"code": 1, "message": "未匹配到产品类或工程类正式模板", "data": None}), 200

    sample_no = report.sample_no or report.report_no
    source_hash = hashlib.sha256(docx).hexdigest()
    source_headers = {
        "Cache-Control": "no-store",
        "X-Source-Document-SHA256": source_hash,
        "X-Template-Kind": actual_kind,
        "X-Template-Selection": template_selection,
        "X-Expected-Pages": str(EXPECTED_PAGES[actual_kind]),
    }
    fmt = (request.args.get("format") or "pdf").lower()
    if fmt not in ("pdf", "docx"):
        return jsonify({"code": 1, "message": "仅支持 pdf 或 docx 格式", "data": None}), 200
    raw_pages = (request.args.get("pages") or "").strip()
    if raw_pages and fmt != "pdf":
        return jsonify({"code": 1, "message": "页码选择仅支持 PDF 导出", "data": None}), 200
    if fmt == "docx":
        # Word 源文件已在上方生成，下载时不应再经过 WPS PDF 转换。
        # 这也避免工程类模板在导出 Word 时因转换排队表现为“无反应”。
        disposition = _content_disposition("attachment", sample_no, "docx")
        return Response(
            docx,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={**source_headers, "Content-Disposition": disposition},
        )
    if request.args.get('asyncPreview') == '1':
        from ..entrust_preview_cache import prepare
        try:
            selected_pages = _parse_pdf_pages(raw_pages, EXPECTED_PAGES[actual_kind])
        except ValueError as error:
            return jsonify({'code': 1, 'message': str(error), 'data': None}), 200
        disposition = _content_disposition('attachment', sample_no, 'pdf')
        if selected_pages:
            page_text = '-'.join(str(page) for page in selected_pages)
            filename = f'{sample_no}-WT-第{page_text}页.pdf'
            disposition = (
                f'attachment; filename={report.report_no}-entrust-pages.pdf; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        return prepare(docx, actual_kind, user, {
            'persistedReportNo': report.report_no, 'pages': raw_pages,
            'headers': {**source_headers, 'Content-Disposition': disposition},
        }, retry=request.args.get('retryPreview') == '1')
    try:
        from ..entrust_preview_cache import render_pdf
        pdf, actual_pages = render_pdf(docx, actual_kind, page_counter=_business_form_page_count)
    except ValueError as error:
        return jsonify({
            "code": 1,
            "message": f"样品单分页校验失败：{error}",
            "data": None,
        }), 200
    source_headers["X-Expected-Pages"] = str(actual_pages)
    try:
        selected_pages = _parse_pdf_pages(raw_pages, actual_pages)
    except ValueError as error:
        return jsonify({"code": 1, "message": str(error), "data": None}), 200
    if selected_pages:
        try:
            pdf = _select_pdf_pages(pdf, selected_pages)
        except Exception:
            return jsonify({"code": 1, "message": "委托单 PDF 页码提取失败", "data": None}), 200
        page_text = "-".join(str(page) for page in selected_pages)
        filename = f"{sample_no}-WT-第{page_text}页.pdf"
        disposition = (
            f"attachment; filename={report.report_no}-entrust-pages.pdf; "
            f"filename*=UTF-8''{quote(filename)}"
        )
        return Response(
            pdf,
            mimetype="application/pdf",
            headers={**source_headers, "X-Preview-Engine": "wps",
                     "X-Selected-Pages": ",".join(str(page) for page in selected_pages),
                     "Content-Disposition": disposition},
        )
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={**source_headers, "X-Preview-Engine": "wps",
                 "Content-Disposition": _content_disposition("inline", sample_no, "pdf")},
    )


@bp.post("/<report_no>/inbound")
@require_auth
def inbound(report_no):
    """样品入库：完成样品登记 + 合同评审（待入库）后手动点一下入库 → 已入库（表单汇总/流程图 #6）。"""
    body = request.get_json(silent=True) or {}
    inbound_date = body.get("inboundDate") if "inboundDate" in body else None
    if "inboundDate" in body and not isinstance(inbound_date, str):
        return jsonify({"code": 1, "message": "入库日期必须为有效日期", "data": None}), 200
    result = execute_sample_inbound(g.current_user, report_no, channel="desktop", inbound_date=inbound_date)
    data = result.report.to_row() if result.report is not None else None
    return jsonify(result.response_payload(data=data)), result.http_status


@bp.post("/<report_no>/inbound-undo")
@require_auth
def inbound_undo(report_no):
    result = execute_sample_inbound_undo(g.current_user, report_no)
    data = result.report.to_row() if result.report is not None else None
    return jsonify(result.response_payload(data=data)), result.http_status


@bp.post("/<report_no>/pickup")
@require_auth
def pickup(report_no):
    """样品出库并领取：填写出库领取单 + 签字领取 → 样品已领取；或退回（待委托更改）。"""
    from ..platform.identity import project_step_error
    user = g.current_user
    body = request.get_json(silent=True) or {}
    action = body.get("action")  # sign / return
    if action not in {"sign", "return"}:
        return jsonify({"code": 1, "message": "样品出库操作无效", "data": None}), 200

    if action == "sign":
        result = execute_sample_pickup(
            user,
            report_no,
            channel="desktop",
            manager_id=body.get("managerId") or "",
            manager_name=body.get("managerName") or "",
            out_time=body.get("outTime") or "",
            receiver_name=body.get("receiverName") or "",
            pickup_time=body.get("pickupTime") or "",
        )
        data = result.report.to_row() if result.report is not None else None
        return jsonify(result.response_payload(data=data)), result.http_status

    result = execute_sample_outbound_return(
        user, report_no, note=body.get("returnNote") or ""
    )
    data = None
    if result.report is not None:
        data = {
            "reportNo": result.report.report_no,
            "status": result.report.status,
            "sampleStatus": result.report.sample_status,
        }
    return jsonify(result.response_payload(data=data)), result.http_status


@bp.post("/<report_no>/return-stock")
@require_auth
def return_stock(report_no):
    """样品撤回入库：已领取且尚未保存检测数据时恢复为已入库。"""
    result = execute_sample_return_stock(g.current_user, report_no)
    data = result.report.to_row() if result.report is not None else None
    return jsonify(result.response_payload(data=data)), result.http_status


@bp.post("/<report_no>/dispose")
@require_auth
def dispose(report_no):
    """R6 样品处置：检测完成后处置样品（已领取/已出库 → 已处置，终态）。"""
    result = execute_sample_dispose(g.current_user, report_no)
    data = None
    if result.report is not None:
        data = {"reportNo": result.report.report_no, "sampleStatus": result.report.sample_status}
    return jsonify(result.response_payload(data=data)), result.http_status
