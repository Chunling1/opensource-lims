from ..edit_concurrency import require_edit_version
from app.organization_privileges import has_full_platform_authority
from ..admin_corrections import can_correct_business_data
"""委托单接口：检测人员选已认领外部ERP合同 → 填委托单提交（一单多样品，样品归属委托单）。"""
import hashlib

from flask import Blueprint, Response, current_app, g, jsonify, request

from ..platform.audit import (
    add_operation_audit,
    completion_owned_by,
    edit_time_text,
    latest_operation_audit,
    records_by_edit_time,
)
from ..platform.identity import has_org_wide_business_scope
from ..business_rows import entrust_business_row, paginate_rows, row_contains, row_in_date_range
from ..extensions import db
from ..models import Entrust, Report
from ..security import require_auth
from ..workflow_dates import (
    business_date,
    business_today,
    latest_workflow_date,
    parse_date,
)

bp = Blueprint("entrust", __name__, url_prefix="/api/entrust")


def _has_registration_access(user):
    return "entrust.registration.view" in user.permission_codes()


def _has_entrust_read_access(user):
    permissions = set(user.permission_codes())
    return bool(
        can_correct_business_data(user)
        or has_full_platform_authority(user)
        or permissions.intersection(
            {
                "entrust.registration.view",
                "entrust.query.view",
                "entrust.sample_register.view",
                "entrust.contract_review.view",
            }
        )
    )


def _scope(query, user):
    st = user.data_scope_type
    if has_org_wide_business_scope(user):
        return query
    if st == "self":
        return query.filter(Entrust.owner == user.name)
    # department / authorization：按授权部门集合过滤（委托单无审批态，authorization 等同部门）
    names = user.data_department_names()
    if st == "department_project":
        from ..platform.identity.department_project_scope import visible_department_names
        names = visible_department_names(user)
    return query.filter(Entrust.department.in_(names)) if names else query.filter(db.false())


def _next_no():
    from ..platform.numbering import allocate_entrust_number
    return allocate_entrust_number(business_today().year)


@bp.get("/next-no")
@require_auth
def next_no():
    if not _has_registration_access(g.current_user):
        return jsonify({"code": 403, "message": "无委托登记权限", "data": None}), 200
    from ..platform.numbering import peek_entrust_number
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {"entrustNo": peek_entrust_number(business_today().year)},
    })


def _entrust_completed_date(entrust):
    return parse_date((entrust.info or {}).get("entrustDate"))


def _stored_entrust_date(entrust):
    if entrust is None:
        return None
    return parse_date((entrust.info or {}).get("entrustDate"))


def _validated_entrust_info(user, contract_no, raw_info, existing=None):
    info = dict(raw_info) if isinstance(raw_info, dict) else {}
    stored_date = _stored_entrust_date(existing)
    current_date = business_today() if existing is None else stored_date
    if current_date is None:
        return None, "历史委托缺少可核对的原委托日期，请联系系统管理员处理"
    info["entrustDate"] = current_date.isoformat()
    return info, None


def _completion_missing_fields(entrust, info):
    required = (
        (entrust.client, "委托单位"),
        (entrust.project_name, "项目名称"),
        (info.get("entrustDate"), "委托日期"),
        (info.get("handleDept") or entrust.department, "经办部门"),
        (info.get("handler") or entrust.owner, "经办人"),
    )
    return [label for value, label in required if not str(value or "").strip()]


@bp.post("/create")
@require_auth
def create():
    user = g.current_user
    if not _has_registration_access(user):
        return jsonify({"code": 403, "message": "无委托登记权限", "data": None}), 200
    body = request.get_json(silent=True) or {}
    # 委托编号由后端唯一生成。生产环境忽略客户端传值，防止新增、复制或
    # 接口调用篡号；测试环境保留隔离编号注入能力，避免测试夹具相互串号。
    requested_no = (body.get("entrustNo") or "").strip()
    no = (
        requested_no
        if current_app.config.get("TESTING") and requested_no
        else _next_no()
    )
    if Entrust.query.filter_by(entrust_no=no).first():
        return jsonify({"code": 1, "message": f"委托编号 {no} 已存在", "data": None}), 200
    contract_no = ""
    info, date_error = _validated_entrust_info(user, contract_no, body.get("info"))
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    client_value = str(body.get("client") or "").strip()
    info["entrustNo"] = no
    dept = (
        body.get("department")
        or info.get("handleDept")
        or info.get("handleDepartment")
        or ""
    ).strip()
    if not dept:
        dept = user.department.name if user.department else ""
    info["handleDept"] = dept
    e = Entrust(
        entrust_no=no,
        contract_no=contract_no,
        client=client_value,
        project_name=(body.get("projectName") or "").strip(),
        project_type=(body.get("projectType") or "").strip(),
        amount=(body.get("amount") or "").strip(),
        department=dept,
        owner=(body.get("owner") or user.name or "").strip(),
        info=info,
        status="委托中",
    )
    db.session.add(e)
    db.session.flush()
    add_operation_audit(
        "entrust.register.create", "entrust", e.entrust_no,
        category="workflow", after=entrust_business_row(e),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"委托单 {no} 已保存（委托登记中）", "data": e.to_row()})


@bp.post("/<int:eid>/complete")
@require_auth
def complete(eid):
    """完成委托：委托中 → 委托完成（手动）。"""
    user = g.current_user
    if (
        not _has_registration_access(user)
        and "entrust.register.complete" not in user.action_codes()
    ):
        return jsonify({"code": 403, "message": "无完成委托登记权限", "data": None}), 200
    e = _scope(Entrust.query, user).filter(Entrust.id == eid).first()
    if not e:
        return jsonify({"code": 1, "message": "委托单不存在或不在数据范围内", "data": None}), 200
    if e.status == "委托完成":
        return jsonify({"code": 1, "message": "委托单已是「委托完成」", "data": None}), 200
    normalized_info, date_error = _validated_entrust_info(
        user, "", e.info, existing=e,
    )
    if date_error:
        return jsonify({"code": 1, "message": date_error, "data": None}), 200
    e.client = str(e.client or "").strip()
    missing = _completion_missing_fields(e, normalized_info)
    if missing:
        return jsonify({
            "code": 1,
            "message": f"以下信息未维护：{'、'.join(missing)}，无法完成登记",
            "data": None,
        }), 200
    before = e.to_row()
    e.info = normalized_info
    e.status = "委托完成"
    from ..finance_service import ensure_finance_bill
    ensure_finance_bill(e, user.name)
    add_operation_audit(
        "entrust.register.complete", "entrust", e.entrust_no, category="workflow",
        before=before, after=e.to_row(),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"委托单 {e.entrust_no} 已完成委托", "data": e.to_row()})


@bp.post("/<int:eid>/uncomplete")
@require_auth
def uncomplete(eid):
    """R6 撤销委托登记完成：委托完成 → 委托中。下游已有样品单则拦截（Q8 禁止撤销已流转）。"""
    from ..models import Report
    from ..platform.workflow import entrust_undo_blocker

    user = g.current_user
    if not _has_registration_access(user):
        return jsonify({"code": 403, "message": "无撤销委托登记权限", "data": None}), 200
    e = _scope(Entrust.query, user).filter(Entrust.id == eid).first()
    if not e:
        return jsonify({"code": 1, "message": "委托单不存在或不在数据范围内", "data": None}), 200
    if e.status != "委托完成":
        return jsonify({"code": 1, "message": f"委托单当前「{e.status}」，无需撤销", "data": None}), 200
    is_admin = has_full_platform_authority(user)
    owned, completion = completion_owned_by(
        user, "entrust", e.entrust_no, "entrust.register.complete",
    )
    if not (owned or is_admin):
        completer = completion.user_name or completion.account if completion else ""
        message = "仅完成该委托登记的用户可以撤销完成"
        if completer:
            message += f"（完成人：{completer}）"
        return jsonify({"code": 403, "message": message, "data": None}), 200
    blocker = entrust_undo_blocker(e, Report.query.filter_by(voided=False))
    if blocker:
        return jsonify({"code": 1, "message": blocker, "data": None}), 200
    before = e.to_row()
    e.status = "委托中"
    add_operation_audit(
        "entrust.register.undo", "entrust", e.entrust_no, category="workflow",
        before=before, after=e.to_row(),
    )
    db.session.commit()
    return jsonify({"code": 0, "message": f"委托单 {e.entrust_no} 已撤销完成，可继续修改", "data": e.to_row()})


@bp.put("/<int:eid>")
@require_auth
def update(eid):
    """就地修改委托单：直接更新登记信息（不影响已生成报告各自的 detail）。"""
    user = g.current_user
    if not _has_registration_access(user):
        return jsonify({"code": 403, "message": "无委托登记权限", "data": None}), 200
    e = _scope(Entrust.query, user).filter(Entrust.id == eid).first()
    if not e:
        return jsonify({"code": 1, "message": "委托单不存在或不在数据范围内", "data": None}), 200
    if e.status == "委托完成":
        return jsonify({"code": 1, "message": "委托单已完成，请先撤销完成后再修改", "data": None}), 200
    before = entrust_business_row(e)
    body = request.get_json(silent=True) or {}
    conflict = require_edit_version(e, body)
    if conflict:
        return conflict
    if "client" in body or isinstance(body.get("info"), dict):
        candidate_info = body.get("info") if isinstance(body.get("info"), dict) else (e.info or {})
        normalized_info, date_error = _validated_entrust_info(
            user, "", candidate_info, existing=e,
        )
        if date_error:
            return jsonify({"code": 1, "message": date_error, "data": None}), 200
    else:
        normalized_info = None
    if normalized_info is not None:
        candidate_client = (body.get("client") if "client" in body else e.client) or ""
        e.client = str(candidate_client).strip()
    if "projectName" in body:
        e.project_name = (body.get("projectName") or "").strip()
    if "projectType" in body:
        e.project_type = (body.get("projectType") or "").strip()
    if "amount" in body:
        e.amount = (body.get("amount") or "").strip()
    candidate_department = (
        body.get("department")
        or (normalized_info or {}).get("handleDept")
        or (normalized_info or {}).get("handleDepartment")
        or ""
    ).strip()
    if candidate_department:
        e.department = candidate_department
    if normalized_info is not None:
        normalized_info["handleDept"] = e.department or candidate_department
        normalized_info["entrustNo"] = e.entrust_no
        e.info = normalized_info
    add_operation_audit(
        "entrust.register.update", "entrust", e.entrust_no,
        category="workflow", before=before, after=entrust_business_row(e),
    )
    db.session.flush()
    saved_row = e.to_row()
    db.session.commit()
    return jsonify({"code": 0, "message": f"委托单 {e.entrust_no} 已保存", "data": saved_row})


@bp.get("/<int:eid>/print")
@require_auth
def print_entrust(eid):
    """按用户选择的产品类或工程类模板打印委托合同单。"""
    if not _has_entrust_read_access(g.current_user):
        return jsonify({"code": 403, "message": "无委托单查看权限", "data": None}), 200
    from urllib.parse import quote

    from ..entrust_render import (
        EXPECTED_PAGES,
        _document_kind,
        build_entrust_doc,
    )
    e = _scope(Entrust.query, g.current_user).filter(Entrust.id == eid).first()
    if not e:
        return jsonify({"code": 1, "message": "委托单不存在或不在数据范围内", "data": None}), 200
    template_kind = (request.args.get("templateKind") or "").strip().lower()
    if template_kind not in ("", "product", "engineering", "product-extended", "engineering-extended"):
        return jsonify({"code": 1, "message": "模板类型无效，请选择产品类或工程类模板", "data": None}), 200
    report_no = (request.args.get("reportNo") or "").strip()
    reports = Report.query.filter_by(entrust_no=e.entrust_no)
    if report_no:
        from ..applications.report_lifecycle import scoped_report_query
        report = scoped_report_query(reports, g.current_user).filter_by(report_no=report_no).first()
        if not report:
            return jsonify({"code": 1, "message": "报告未关联此委托单或不在数据范围内", "data": None}), 200
        from ..sample_entrust import sample_entrust_object
        e = sample_entrust_object(report, e)
    else:
        from ..applications.report_lifecycle import scoped_report_query
        candidates = scoped_report_query(reports, g.current_user).filter(
            Report.voided.is_not(True),
            db.or_(Report.report_kind == 'main', Report.report_kind.is_(None)),
            db.or_(Report.main_report_no == '', Report.main_report_no.is_(None)),
        ).order_by(Report.id).limit(2).all()
        if len(candidates) > 1:
            return jsonify({"code": 1, "message": "该委托包含多个样品，请选择具体样品查看或下载带评审签字的委托单", "data": None}), 200
        report = candidates[0] if candidates else None
        if report:
            from ..sample_entrust import sample_entrust_object
            e = sample_entrust_object(report, e)
    actual_kind = template_kind or _document_kind(e, report)
    try:
        docx = build_entrust_doc(e, report, actual_kind, "")
    except ValueError as error:
        return jsonify({"code": 1, "message": str(error), "data": None}), 200
    if not docx:
        return jsonify({"code": 1, "message": "未匹配到委托单模板", "data": None}), 200
    source_hash = hashlib.sha256(docx).hexdigest()
    source_headers = {
        "Cache-Control": "no-store",
        "X-Source-Document-SHA256": source_hash,
        "X-Template-Kind": actual_kind,
        "X-Expected-Pages": str(EXPECTED_PAGES[actual_kind]),
    }
    fmt = (request.args.get("format") or "pdf").lower()
    if fmt not in ("pdf", "docx"):
        return jsonify({"code": 1, "message": "仅支持 pdf 或 docx 格式", "data": None}), 200
    if fmt == "docx":
        # DOCX 直接返回已生成的原文件，不额外调用 WPS PDF 转换。
        disp = f"attachment; filename={e.entrust_no}-wt.docx; filename*=UTF-8''{quote(e.entrust_no + '-委托单.docx')}"
        return Response(docx, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={**source_headers, "Content-Disposition": disp})
    try:
        from ..entrust_preview_cache import render_pdf
        pdf, actual_pages = render_pdf(docx, actual_kind)
    except ValueError as error:
        return jsonify({
            "code": 1,
            "message": f"委托单分页校验失败：{error}",
            "data": None,
        }), 200
    source_headers["X-Expected-Pages"] = str(actual_pages)
    etag = hashlib.sha256(pdf).hexdigest()
    source_headers.update({'ETag': f'"{etag}"', 'Cache-Control': 'private, no-store'})
    if request.if_none_match.contains(etag):
        return Response(status=304, headers=source_headers)
    return Response(pdf, mimetype="application/pdf",
                    headers={**source_headers, "X-Preview-Engine": "wps",
                             "Content-Disposition": f"inline; filename={e.entrust_no}-wt.pdf"})


from ..list_reads import reuse_list_reads


@bp.get("/<int:eid>")
@require_auth
def detail(eid):
    if not _has_entrust_read_access(g.current_user):
        return jsonify({"code": 403, "message": "无委托单查看权限", "data": None}), 200
    row = _scope(Entrust.query, g.current_user).filter(Entrust.id == eid).first()
    if row is None:
        return jsonify({"code": 403, "message": "委托单不存在或不在数据范围内", "data": None}), 200
    return jsonify({"code": 0, "message": "ok", "data": entrust_business_row(row)})


@bp.post("/query")
@require_auth
@reuse_list_reads
def query():
    if not _has_entrust_read_access(g.current_user):
        return jsonify({"code": 403, "message": "无委托单查看权限", "data": None}), 200
    body = request.get_json(silent=True) or {}
    keyword = (body.get("keyword") or "").strip()
    status = (body.get("status") or "").strip()
    from ..list_projection import list_entrusts
    scoped = _scope(Entrust.query, g.current_user)
    page_meta = None
    page_records = None
    if body.get('serverPage') and body.get('view') == 'contract_review':
        from ..applications.report_lifecycle import scoped_report_query
        from ..list_page_access import report_access
        visible_reports = report_access(scoped_report_query(Report.query, g.current_user).filter(
            db.func.coalesce(Report.voided, False).is_(False)), g.current_user, 'contract_review')
        scoped = scoped.filter(Entrust.entrust_no.in_(visible_reports.with_entities(Report.entrust_no)))
    if body.get('serverPage'):
        from ..list_paging import load_entrust_page
        try:
            page_records, page_meta = load_entrust_page(scoped, body)
        except (ValueError, TypeError) as exc:
            return jsonify({'code': 1, 'message': str(exc), 'data': None}), 200
        keyword = status = ''
    if page_records is None:
        page_records = list_entrusts(scoped) if body.get('projection') == 'list' else scoped.all()
    entrusts = records_by_edit_time(
        page_records,
        "entrust",
        lambda entrust: entrust.entrust_no,
        lambda entrust: entrust.created_at,
    )
    if page_meta is not None:
        order = {r.id: i for i, r in enumerate(page_records)}
        entrusts.sort(key=lambda pair: order[pair[0].id])
    rows = []
    for entrust, edited_at in entrusts:
        row = entrust_business_row(entrust)
        completion = latest_operation_audit(
            "entrust", entrust.entrust_no, "entrust.register.complete",
        )
        row["completionAccount"] = completion.account if completion else ""
        row["completionUserName"] = completion.user_name if completion else ""
        row["editedAt"] = edit_time_text(edited_at)
        rows.append(row)
    if status:
        rows = [r for r in rows if r["status"] == status]
    if keyword:
        rows = [r for r in rows if row_contains(r, keyword)]
    rows = [r for r in rows if row_in_date_range(
        r, body.get("startDate"), body.get("endDate"), ("entrustDate", "date"),
    )]
    return jsonify({"code": 0, "message": "ok", "data": {'rows': rows, **page_meta} if page_meta is not None else paginate_rows(rows, body)})


@bp.get("/handle-departments")
@require_auth
def handle_departments():
    """经办部门候选：当前操作用户所在部门 + 其下属子部门（流程图/表单汇总）。"""
    user = g.current_user
    dept = user.department
    out = []
    if dept:
        stack = [dept]
        seen = set()
        while stack:
            d = stack.pop()
            if d.id in seen:
                continue
            seen.add(d.id)
            out.append({"id": d.id, "name": d.name})
            stack.extend(d.children or [])
    return jsonify({"code": 0, "message": "ok", "data": {"rows": out, "current": dept.name if dept else ""}})


@bp.get("/options")
@require_auth
@reuse_list_reads
def options():
    """委托单下拉选项（添加样品时选择）。

    样品登记是跨委托受理人的后续环节：具备样品登记页面权限的人员可从
    全院各部门选择已完成委托。其他调用方仍沿用自身数据范围，避免扩大
    普通委托查询权限。
    """
    rows = []
    user = g.current_user
    can_register_sample = (
        has_full_platform_authority(user)
        or "entrust.sample_register.view" in user.permission_codes()
    )
    scoped_query = Entrust.query if can_register_sample else _scope(Entrust.query, user)
    query = scoped_query.filter_by(status="委托完成")
    entrusts = records_by_edit_time(
        query.all(),
        "entrust",
        lambda entrust: entrust.entrust_no,
        lambda entrust: entrust.created_at,
    )
    for e, edited_at in entrusts:
        form_date = parse_date((e.info or {}).get("entrustDate")) or business_date(e.created_at)
        completed_date = _entrust_completed_date(e)
        completion = latest_operation_audit(
            "entrust", e.entrust_no, "entrust.register.complete",
        )
        info = e.info or {}
        project_no = (
            info.get("erpProjectNo")
            or info.get("projectCode")
            or info.get("projectRecordNo")
            or info.get("projectTradeCode")
            or ""
        )
        rows.append({
            "id": e.id,
            "entrustNo": e.entrust_no,
            "client": e.client,
            "projectName": e.project_name,
            "contractNo": e.contract_no,
            "projectType": e.project_type or "",
            "erpProjectNo": project_no,
            "amount": e.amount or "",
            "department": e.department or "",
            "owner": e.owner or "",
            "info": {**info, "erpProjectNo": project_no},
            "sampleCount": e.sample_count(),
            "entrustDate": form_date.isoformat() if form_date else "",
            "workflowDates": {
                "entrustAt": completed_date.isoformat() if completed_date else "",
            },
            "editedAt": edit_time_text(edited_at),
            "completionAccount": completion.account if completion else "",
            "completionUserName": completion.user_name if completion else "",
        })
    return jsonify({"code": 0, "message": "ok", "data": {"rows": rows}})
