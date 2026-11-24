"""版本化报告文档服务。

首个正式版式为 LAB-2026JF 热湿报告：报告首页、检验结果、样品照片三页。
其他报告继续使用已有中心/报告类型封面首页模板，后续按模板配置逐步迁移。
"""
import hashlib
import json
import re
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from io import BytesIO

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from sqlalchemy import func

from .platform.audit import add_operation_audit
from .cover_render import (
    _set_cell_image,
    _trademark_image,
    build_cover_parts,
    build_cover_from_template,
    cover_templates_are_combined,
    template_release_snapshot,
)
from .docx_pdf import (
    add_top_right_page_numbers, docx_to_pdf, docx_to_pdf_wps, image_to_pdf,
    merge_pdf_bytes, office_to_pdf, office_to_pdf_wps,
)
from .covers import is_system_cover_attachment
from .extensions import db
from .functions.report_instrument_text import report_instrument_text
from .platform.file_vault import persist_bytes, read_file_bytes
from .models import (
    Report,
    ReportAttachment,
    ReportDocumentContent,
    ReportDocumentVersion,
    ReportRenderJob,
    ReportTemplateProfile,
    User,
)

NCSA_PROFILE = {
    "code": "LAB-2026JF",
    "name": "空调中心热湿检验报告",
    "report_no_pattern": r"^LAB-\d{4}JF-\d+$",
    "center_prefix": "NCSA",
    "report_type": "检验报告",
    "composition": ["report_home", "result_table", "sample_photos"],
    "required_fields": ["sampleNo", "productName", "client", "testBasis", "testItems", "resultGroups"],
    "requires_version": True,
}
NCSA_TEMPLATE_RELEASE = "LAB-2026JF-v2-trademark-dates-cn-20261014"

FALLBACK_PROFILE = {
    "code": "STANDARD-COVER-HOME",
    "name": "中心封面与首页标准模板",
    "report_no_pattern": r".*",
    "center_prefix": "",
    "report_type": "检测报告",
    "composition": ["cover", "report_home"],
    "required_fields": ["sampleNo", "client", "testBasis"],
    "requires_version": False,
}


def seed_default_profiles():
    """幂等写入系统内置模板配置，不覆盖管理员后续调整。"""
    for item in (NCSA_PROFILE, FALLBACK_PROFILE):
        if ReportTemplateProfile.query.filter_by(code=item["code"]).first():
            continue
        db.session.add(ReportTemplateProfile(**item))
    db.session.commit()


def select_profile(report):
    from .blueprints.technical_subprojects import configured_profile
    configured = configured_profile(report)
    if configured:
        return configured
    rows = ReportTemplateProfile.query.filter_by(active=True).order_by(ReportTemplateProfile.id).all()
    for profile in rows:
        if profile.code == FALLBACK_PROFILE["code"]:
            continue
        try:
            if re.search(profile.report_no_pattern or r"$^", report.report_no or ""):
                return profile
        except re.error:
            continue
    return next((p for p in rows if p.code == FALLBACK_PROFILE["code"]), None)


def _summary_sections(report):
    out = {}
    for section in (report.detail or {}).get("summary") or []:
        fields = {}
        for item in section.get("fields") or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                fields[str(item[0]).strip()] = "" if item[1] is None else str(item[1]).strip()
        out[str(section.get("title") or "").strip()] = fields
    return out


def _pick(sections, *aliases):
    for section_name, field_name in aliases:
        value = (sections.get(section_name) or {}).get(field_name)
        if value and value != "—":
            return value
    return ""


def report_values(report):
    from .sample_identity import sample_number
    from .report_date_display import format_report_dates, report_date, production_date_text
    from .document_field_projection import judgment_basis, test_items as project_items, test_dates
    from .functions.report_standard_text import format_standard_titles
    sections = _summary_sections(report)
    check_input = (report.detail or {}).get("checkInput") or {}
    instrument_text = report_instrument_text(
        check_input.get("equipmentSnapshots") if isinstance(check_input, dict) else None,
        _pick(sections, ("实验信息", "检测用仪器、装置"), ("实验信息", "试验设备"), ("实验信息", "检测设备")),
        display=check_input.get("equipmentDisplay") if isinstance(check_input, dict) else None,
        separator=check_input.get("equipmentSeparatorText") if isinstance(check_input, dict) else None,
    )
    signatures = dict((report.detail or {}).get("signatures") or {})
    product_name = _pick(
        sections,
        ("送样信息", "样品名称"), ("样品信息", "样品名称"),
        ("送样信息", "样品/工程名称"), ("委托信息", "工程名称"),
    ) or report.project_name or ""
    test_basis = _pick(
        sections,
        ("实验信息", "检测依据"), ("实验信息", "执行标准"),
        ("送样信息", "检测依据"), ("送样信息", "评定标准"),
    )
    # Use the saved display projection, not the sample's code-only summary.
    # Legacy reports without this field keep their existing fallback behavior.
    if isinstance(check_input, dict) and check_input.get("standardDisplay"):
        test_basis = check_input["standardDisplay"]
    test_items = _pick(sections, ("实验信息", "检测项目")) or report.project or ""
    test_items = project_items(report.detail, test_items, separator=check_input.get("itemsSeparator"))
    _, _, test_date = test_dates(
        report.detail,
        _pick(sections, ("实验信息", "试验开始日期"), ("实验信息", "检测开始日期")),
        _pick(sections, ("实验信息", "试验结束日期"), ("实验信息", "检测结束日期"),
              ("实验信息", "检测日期"), ("送样信息", "检测日期")),
        _pick(sections, ("实验信息", "试验时间区间")),
    )
    return format_report_dates({
        "reportNo": report.report_no or "",
        "sampleNo": sample_number(report) or _pick(sections, ("送样信息", "样品编号"), ("样品信息", "样品编号")),
        "productName": product_name,
        "specification": _pick(sections, ("送样信息", "规格型号"), ("样品信息", "规格型号")),
        "trademark": _pick(sections, ("送样信息", "商标"), ("样品信息", "商标")) or "/",
        "trademarkImage": _trademark_image(report.detail or {}),
        "client": report.client or _pick(sections, ("委托信息", "委托单位")),
        "factoryNo": _pick(sections, ("送样信息", "出厂编号"), ("样品信息", "出厂编号")) or "/",
        "productionDate": production_date_text(report.detail),
        "manufacturer": _pick(
            sections, ("送样信息", "生产单位"), ("送样信息", "生产厂家"),
            ("样品信息", "生产单位"), ("样品信息", "生产厂家"),
        ),
        "quantity": _pick(sections, ("送样信息", "样品数量"), ("样品信息", "样品数量")),
        "sampleDate": _pick(sections, ("送样信息", "送样日期"), ("样品信息", "送样日期")),
        "testCategory": _pick(sections, ("送样信息", "检测类别"), ("样品信息", "检测类别")) or "委托",
        "testDate": test_date,
        "clientAddress": _pick(sections, ("委托信息", "委托单位地址"), ("委托信息", "通讯地址")),
        "testBasis": test_basis if (check_input.get("standardTitleStyles") or check_input.get("standardRecords")) and check_input.get("standardDisplay") else format_standard_titles(test_basis),
        "judgmentBasis": judgment_basis(report.detail, _pick(
            sections, ("实验信息", "判定依据"), ("实验信息", "判定标准"),
            ("送样信息", "评定标准"),
        ), report=True) or "/",
        "testLocation": _pick(sections, ("实验信息", "检测地点"), ("送样信息", "检测地点")),
        "instruments": instrument_text,
        "testItems": test_items,
        "description": _pick(
            sections, ("项目信息", "报告首页备注"), ("原始记录", "备注"),
            ("原始记录", "结论"),
        ),
        "issueDate": __import__(__package__ + ".report_final_fields", fromlist=["approval_date"]).approval_date(report),
        "signatures": {
            "主检": signatures.get("主检") or _pick(sections, ("实验信息", "主检人"), ("实验信息", "试验员/主检")) or report.owner or "",
            "审核": signatures.get("审核") or "",
            "批准": signatures.get("批准") or "",
        },
    })


def _default_result_groups(report):
    sections = _summary_sections(report)
    result = _pick(sections, ("原始记录", "实测值"), ("原始记录", "检测结果"), ("原始记录", "结论"))
    if not result:
        return []
    return [{
        "name": report.project or "检测项目",
        "items": [{"name": report.project or "检测项目", "condition": "", "unit": "", "value": result}],
    }]


def composition_options(report):
    raw = (report.detail or {}).get("reportComposition") or {}
    values = raw.get("includedOtherAttachmentIds") if isinstance(raw, dict) else []
    ordered = []
    for value in values if isinstance(values, list) else []:
        try:
            attachment_id = int(value)
        except (TypeError, ValueError):
            continue
        if attachment_id > 0 and attachment_id not in ordered:
            ordered.append(attachment_id)
    result = {"includedOtherAttachmentIds": ordered}
    if isinstance(raw, dict) and "noSupplementBody" in raw:
        result["noSupplementBody"] = raw["noSupplementBody"] is True
    if isinstance(raw, dict):
        if 'preserveUploadedReport' in raw:
            result['preserveUploadedReport'] = raw['preserveUploadedReport'] is True
        for key in ('reportLanguage', 'reportTemplateVariant'):
            if key in raw:
                result[key] = raw[key]
    return result


def content_dict(report, row=None):
    if row is None:
        row = ReportDocumentContent.query.filter_by(report_no=report.report_no).first()
    profile = select_profile(report)
    if row:
        content = row.to_dict()
    else:
        content = {
            "profileCode": profile.code if profile else FALLBACK_PROFILE["code"],
            "resultGroups": _default_result_groups(report),
            "remarks": "",
            "photos": [],
            "extraPages": deepcopy((report.detail or {}).get("reportPages") or []),
            "updatedBy": "",
            "updatedAt": "",
        }
    content["compositionOptions"] = composition_options(report)
    return content


def attachment_role(attachment):
    """Classify an uploaded report file without requiring a schema migration.

    New uploads carry an explicit Chinese source label.  The conservative
    filename/source fallback keeps older files usable while ensuring raw
    records are never appended to the customer-facing report.
    """
    marker = f"{attachment.source or ''} {attachment.name or ''}".lower()
    if "原始记录" in marker or "raw record" in marker or "raw_record" in marker:
        return "raw_record"
    if "完整报告正文" in marker or "completed report" in marker or "completed_report" in marker:
        return "completed_report"
    if (
        "报告后续页" in marker
        or "报告正文" in marker
        or "report page" in marker
        or "report_page" in marker
    ):
        return "report_page"
    return "other"


def attachment_is_active(attachment):
    return not attachment.deleted_at and str(attachment.status or "") != "已替代"


def attachment_merge_eligible(attachment):
    if is_system_cover_attachment(attachment):
        return False
    lower = str(attachment.name or "").lower()
    content_type = str(attachment.content_type or "").lower()
    return (
        lower.endswith((".pdf", ".docx", ".png", ".jpg", ".jpeg"))
        or "pdf" in content_type
        or "wordprocessingml" in content_type
        or content_type in {"image/png", "image/jpeg"}
    )


def attachment_meta(attachment, included_ids=()):
    data = attachment.meta()
    role = attachment_role(attachment)
    data.update({
        "category": role,
        "active": attachment_is_active(attachment),
        "mergeEligible": role == "other" and attachment_merge_eligible(attachment),
        "selectedForOfficial": attachment.id in set(included_ids),
        "superseded": str(attachment.status or "") == "已替代",
    })
    return data


def report_composition(report, profile=None):
    base = list((profile.composition if profile else FALLBACK_PROFILE["composition"]) or [])
    selected = composition_options(report)["includedOtherAttachmentIds"]
    return [*base, "completed_report", *[f"other_attachment:{value}" for value in selected],
            "page_numbers:after_cover"]


def _attachment_fingerprints(report_no, content, output_kind, include_conclusion=False):
    ids = {int(p.get("attachmentId")) for p in content.get("photos") or [] if p.get("attachmentId")}
    ids.update(int(value) for value in (
        (content.get("compositionOptions") or {}).get("includedOtherAttachmentIds") or []
    ))
    q = ReportAttachment.query.filter_by(report_no=report_no, deleted_at=None)
    if output_kind == "audit":
        rows = q.order_by(ReportAttachment.id).all()
    else:
        from .document_module import is_conclusion
        rows = [
            row for row in q.order_by(ReportAttachment.id).all()
            if row.id in ids or (
                attachment_role(row) in {"report_page", "completed_report"}
                and attachment_is_active(row)
            ) or (
                include_conclusion and attachment_role(row) == "other"
                and attachment_is_active(row) and is_conclusion(row.name)
            )
        ]
    return [{
        "id": row.id,
        "name": row.name,
        "contentType": row.content_type,
        "sha256": row.stored_file.sha256 if row.stored_file else hashlib.sha256(row.data or b"").hexdigest(),
    } for row in rows if not is_system_cover_attachment(row)]


def source_snapshot(report, content=None, profile=None, output_kind="official", *, verify_template=True):
    content = content or content_dict(report)
    profile = profile or select_profile(report)
    from . import docparser_field_only
    uses_original_package = docparser_field_only.applies_to(report)
    if uses_original_package:
        template = (docparser_field_only.template_snapshot(report) if verify_template
                    else docparser_field_only.template_snapshot(report, verify_package=False))
    elif profile and profile.code == NCSA_PROFILE["code"]:
        template = {
            "release": NCSA_TEMPLATE_RELEASE,
            "effectiveDate": "2026-07-09",
            "files": [],
        }
    else:
        template = template_release_snapshot(report)
    attachments = _attachment_fingerprints(
        report.report_no, content, output_kind, include_conclusion=uses_original_package,
    )
    if uses_original_package:
        from .document_module import is_conclusion
        from .document_module import CONCLUSION_POLICY as conclusion_policy
        for attachment in attachments:
            if is_conclusion(attachment['name']):
                attachment['renderingPolicy'] = conclusion_policy
    return {
        "report": {
            "reportNo": report.report_no,
            "sampleNo": report.sample_no,
            "project": report.project,
            "projectName": report.project_name,
            "client": report.client,
            "department": report.department,
            "owner": report.owner,
            "detail": report.detail or {},
        },
        "profile": profile.to_dict() if profile else FALLBACK_PROFILE,
        "template": template,
        "content": content,
        "attachments": attachments,
        "outputKind": output_kind,
        "pdfDecorationPolicy": (__import__(__package__ + ".pdf_report_qr", fromlist=["POLICY"]).POLICY
                                if uses_original_package else None),
        "approvalDate": __import__(__package__ + ".report_final_fields", fromlist=["approval_date"]).approval_date(report),
    }


def snapshot_hash(snapshot):
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def supports_no_supplement(report):
    from . import docparser_field_only
    # Engineering/inspection fixed portions contain only cover and notice.
    # Their uploaded body must retain results and signing anchors.
    return (docparser_field_only.applies_to(report)
            and docparser_field_only.profile_for(report)['kind'] in {'product', 'sampling', 'calibration'})


def document_preflight(report, output_kind="official", *, render_template=True):
    profile = select_profile(report)
    content = content_dict(report)
    values = report_values(report)
    missing = []
    from . import docparser_field_only
    uses_original_package = docparser_field_only.applies_to(report)
    required = [] if uses_original_package else ((profile.required_fields if profile else []) or [])
    for key in required:
        value = content.get("resultGroups") if key == "resultGroups" else values.get(key)
        if not value:
            missing.append(key)
    warnings = []
    template_selection = None
    if uses_original_package:
        try:
            if composition_options(report).get('preserveUploadedReport') is True:
                template_selection = docparser_field_only.profile_for(report)
                warnings.append('保留上传完整报告的封面和首页；DocParser 仍处理背景、页码和已选附件')
            else:
                template_selection = docparser_field_only.profile_for(report)
                # Read-only inspection verifies source/template fingerprints below.
                # Rendering remains mandatory in generation/workflow commands.
                if render_template:
                    _blob, audit = docparser_field_only.render_preview(report)
                    template_selection = audit['templateSelection']
        except ValueError as exc:
            missing.append('原包模板：' + str(exc))
        has_body = any(
            attachment_role(row) in {'report_page', 'completed_report'} and attachment_is_active(row)
            for row in ReportAttachment.query.filter_by(
                report_no=report.report_no, deleted_at=None,
            ).all()
        )
        no_supplement = composition_options(report).get('noSupplementBody') is True
        if no_supplement and composition_options(report).get('preserveUploadedReport') is True:
            missing.append('保留上传完整报告模式不能同时确认无补充正文')
        if composition_options(report).get('preserveUploadedReport') is True:
            from .document_module import is_conclusion
            if any(attachment_role(row) == 'other' and attachment_is_active(row) and is_conclusion(row.name)
                   for row in ReportAttachment.query.filter_by(report_no=report.report_no, deleted_at=None).all()):
                missing.append('保留上传模式请将自定义结论写入完整报告，并移除独立 Conclusion.docx')
        if no_supplement and not supports_no_supplement(report):
            missing.append('当前模板的结果和签字页需要通过完整报告上传，不能确认无补充正文')
        if no_supplement and has_body:
            missing.append('已确认无补充正文，但仍有有效完整报告，请取消无补充确认或移除已上传正文')
        if output_kind == 'official' and not has_body and not no_supplement:
            missing.append('填写完成的报告正文模板')
        elif not has_body and not no_supplement:
            warnings.append('尚未上传填写完成的报告正文模板')
    if profile and profile.code == NCSA_PROFILE["code"] and not content.get("photos"):
        warnings.append("样品照片尚未关联，照片页将显示待上传占位")
    if not values["signatures"].get("审核") or not values["signatures"].get("批准"):
        warnings.append("审核/批准签名将随流程完成后写入新版本")
    snapshot = source_snapshot(report, content, profile, output_kind)
    current_hash = snapshot_hash(snapshot)
    current = (
        db.session.get(ReportDocumentVersion, report.current_document_version_id)
        if report.current_document_version_id
        else None
    )
    current_stale = bool(current and current.source_hash != current_hash)
    if uses_original_package and current and report.status in {'待校核', '待审核', '待批准', '待打印'}:
        from .report_version_consistency import confirmed_input_snapshot, require_reviewed_document
        current_stale = confirmed_input_snapshot(current.snapshot) != confirmed_input_snapshot(snapshot)
        if report.status in {'待批准', '待打印'}:
            try:
                require_reviewed_document(report, current)
                current_stale = False
            except ValueError:
                current_stale = True
    return {
        "profile": profile.to_dict() if profile else FALLBACK_PROFILE,
        "values": values,
        "content": content,
        "missing": missing,
        "warnings": warnings,
        "ready": not missing,
        "sourceHash": current_hash,
        "currentVersionStale": current_stale,
        "templateSelection": template_selection,
        "preserveUploadedReport": composition_options(report).get('preserveUploadedReport') is True,
        "noSupplementBody": uses_original_package and composition_options(report).get('noSupplementBody') is True,
        "noSupplementSupported": supports_no_supplement(report),
        "hasCompletedReport": has_body if uses_original_package else any(
            attachment_role(row) in {'report_page', 'completed_report'} and attachment_is_active(row)
            for row in ReportAttachment.query.filter_by(
                report_no=report.report_no, deleted_at=None,
            ).all()
        ),
    }


def _set_run_font(run, size=9, bold=False, name="宋体"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold


def _set_cell_text(cell, text, size=9, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(str(text or ""))
    _set_run_font(run, size=size, bold=bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _shade(cell, fill="E7E6E6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _set_cell_margins(cell, top=80, start=100, bottom=80, end=100):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _prepare_table(table, widths=None):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            _set_cell_margins(cell)
            if widths and index < len(widths):
                cell.width = widths[index]


def _apply_table_grid(table):
    """Use the built-in grid style when present; imported templates may omit it."""
    try:
        table.style = "Table Grid"
        return
    except KeyError:
        pass
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), "606866")


def _title(doc, text, size=16):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    _set_run_font(r, size=size, bold=True, name="黑体")
    return p


def _add_page_field(paragraph, field_name):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field_name
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    for node in (fld_begin, instr, fld_sep, text, fld_end):
        run._r.append(node)


def _configure_document(doc, values):
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.35)
    section.bottom_margin = Cm(1.35)
    section.left_margin = Cm(1.55)
    section.right_margin = Cm(1.55)
    section.header_distance = Cm(0.55)
    section.footer_distance = Cm(0.55)
    normal = doc.styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(9)
    header = section.header
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.text = ""
    r = p.add_run(f"样品编号：{values.get('sampleNo') or ''}")
    _set_run_font(r, size=8.5, bold=True)
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("第 ")
    _set_run_font(r, size=8)
    _add_page_field(p, "PAGE")
    r = p.add_run(" 页  共 ")
    _set_run_font(r, size=8)
    _add_page_field(p, "NUMPAGES")
    r = p.add_run(" 页")
    _set_run_font(r, size=8)


def _add_home_page(doc, values):
    _title(doc, "检 验 检 测 报 告", 17)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(5)
    run = p.add_run(values.get("reportNo") or "")
    _set_run_font(run, size=10, bold=True)
    rows = [
        ("产品名称", values["productName"], "型号规格", values["specification"]),
        ("商标", values["trademark"], "出厂编号", values["factoryNo"]),
        ("委托单位", values["client"], "生产日期", values["productionDate"]),
        ("生产单位", values["manufacturer"], "送样数量", values["quantity"]),
        ("检测类别", values["testCategory"], "送样日期", values["sampleDate"]),
        ("检测日期", values["testDate"], "", ""),
    ]
    table = doc.add_table(rows=0, cols=4)
    _apply_table_grid(table)
    _prepare_table(table, [Cm(2.7), Cm(7.1), Cm(2.7), Cm(5.0)])
    for left_label, left_value, right_label, right_value in rows:
        cells = table.add_row().cells
        _set_cell_text(cells[0], left_label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(cells[1], left_value)
        if left_label == "商标" and values.get("trademarkImage"):
            if not _set_cell_image(cells[1], values["trademarkImage"]):
                _set_cell_text(cells[1], left_value)
        if right_label:
            _set_cell_text(cells[2], right_label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(cells[3], right_value)
        else:
            merged = cells[1].merge(cells[3])
            _set_cell_text(cells[0], left_label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(merged, left_value)
    for label, value in [
        ("委托单位地址", values["clientAddress"]),
        ("检测依据", values["testBasis"]),
        ("判定依据", values["judgmentBasis"]),
        ("检测地点", values["testLocation"]),
        ("检测用仪器、装置", values["instruments"]),
        ("检测项目", values["testItems"]),
        ("说明", values["description"]),
    ]:
        cells = table.add_row().cells
        label_cell = cells[0].merge(cells[1])
        value_cell = cells[2].merge(cells[3])
        _set_cell_text(label_cell, label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(value_cell, value)
    cells = table.add_row().cells
    label_cell = cells[0].merge(cells[1])
    value_cell = cells[2].merge(cells[3])
    _set_cell_text(label_cell, "签发", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(value_cell, f"检验检测专用章\n签发日期：{values['issueDate'] or '------'}", align=WD_ALIGN_PARAGRAPH.CENTER)
    sig = doc.add_table(rows=1, cols=6)
    _apply_table_grid(sig)
    _prepare_table(sig, [Cm(2.1), Cm(3.6), Cm(2.1), Cm(3.6), Cm(2.1), Cm(3.6)])
    signatures = values["signatures"]
    for index, (label, key) in enumerate((("批 准", "批准"), ("审 核", "审核"), ("主 检", "主检"))):
        _set_cell_text(sig.cell(0, index * 2), label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_cell_text(sig.cell(0, index * 2 + 1), signatures.get(key) or "------", align=WD_ALIGN_PARAGRAPH.CENTER)


def _add_results_page(doc, content):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _title(doc, "检   验   结   果", 15)
    table = doc.add_table(rows=1, cols=5)
    _apply_table_grid(table)
    _prepare_table(table, [Cm(1.2), Cm(5.0), Cm(4.5), Cm(2.0), Cm(5.0)])
    for cell, label in zip(
        table.rows[0].cells,
        ("序号", "检验项目", "检验条件", "单位", "检验结果"),
        strict=True,
    ):
        _shade(cell)
        _set_cell_text(cell, label, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    sequence = 1
    for group in content.get("resultGroups") or []:
        items = [i for i in (group.get("items") or []) if isinstance(i, dict)] or [{}]
        start_row = len(table.rows)
        for item in items:
            cells = table.add_row().cells
            _set_cell_text(cells[0], sequence, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(cells[1], item.get("name") or group.get("name") or "")
            _set_cell_text(cells[2], item.get("condition") or "")
            _set_cell_text(cells[3], item.get("unit") or "", align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(cells[4], item.get("value") or "", align=WD_ALIGN_PARAGRAPH.CENTER)
        if len(items) > 1:
            table.cell(start_row, 0).merge(table.cell(start_row + len(items) - 1, 0))
            table.cell(start_row, 1).merge(table.cell(start_row + len(items) - 1, 1))
            _set_cell_text(table.cell(start_row, 0), sequence, align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(table.cell(start_row, 1), group.get("name") or items[0].get("name") or "")
        sequence += 1
    cells = table.add_row().cells
    label = cells[0].merge(cells[1])
    value = cells[2].merge(cells[4])
    _set_cell_text(label, "备 注", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(value, content.get("remarks") or "/")
    p = doc.add_paragraph("本页以下空白。")
    p.paragraph_format.space_before = Pt(8)
    for run in p.runs:
        _set_run_font(run, size=8)


def _photo_attachment(report_no, attachment_id):
    try:
        aid = int(attachment_id)
    except (TypeError, ValueError):
        return None
    return ReportAttachment.query.filter_by(
        id=aid,
        report_no=report_no,
        deleted_at=None,
    ).first()


def _add_photos_page(doc, report, content):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _title(doc, "样 品 照 片", 15)
    photos = [p for p in content.get("photos") or [] if isinstance(p, dict)][:6]
    while len(photos) < 3:
        photos.append({"caption": ("机组照片", "铭牌照片", "过滤器照片")[len(photos)]})
    table = doc.add_table(rows=0, cols=2)
    _apply_table_grid(table)
    _prepare_table(table, [Cm(8.7), Cm(8.7)])
    for offset in range(0, len(photos), 2):
        image_cells = table.add_row().cells
        caption_cells = table.add_row().cells
        for column in range(2):
            photo = photos[offset + column] if offset + column < len(photos) else {}
            attachment = _photo_attachment(report.report_no, photo.get("attachmentId"))
            image_cells[column].text = ""
            paragraph = image_cells[column].paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            image_bytes = read_file_bytes(attachment.stored_file, attachment.data) if attachment else b""
            if attachment and (attachment.content_type or "").lower().startswith("image/") and image_bytes:
                try:
                    paragraph.add_run().add_picture(BytesIO(image_bytes), width=Cm(7.8))
                except Exception:
                    _set_cell_text(image_cells[column], "图片格式无法读取", align=WD_ALIGN_PARAGRAPH.CENTER)
            else:
                _set_cell_text(image_cells[column], "待上传照片", align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell_text(caption_cells[column], photo.get("caption") or "样品照片", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        table.rows[-2].height = Cm(5.4)
    cells = table.add_row().cells
    label = cells[0]
    value = cells[1]
    _set_cell_text(label, "备注", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _set_cell_text(value, content.get("photoRemark") or "/")
    p = doc.add_paragraph("本页以下空白。")
    for run in p.runs:
        _set_run_font(run, size=8)


def build_ncsa_document(report, content):
    values = report_values(report)
    doc = Document()
    _configure_document(doc, values)
    _add_home_page(doc, values)
    _add_results_page(doc, content)
    _add_photos_page(doc, report, content)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def build_document(report, content, profile, output_kind="official"):
    from . import docparser_field_only
    if docparser_field_only.applies_to(report):
        blob, _audit = docparser_field_only.render_preview(report)
    elif profile and profile.code == NCSA_PROFILE["code"]:
        blob = build_ncsa_document(report, content)
    else:
        blob = build_cover_from_template(report)
        if not blob:
            blob = build_ncsa_document(report, content)
        elif content.get("resultGroups"):
            doc = Document(BytesIO(blob))
            _add_results_page(doc, content)
            bio = BytesIO()
            doc.save(bio)
            blob = bio.getvalue()
    return blob


def _raw_record_pdfs(report_no):
    rows = ReportAttachment.query.filter_by(
        report_no=report_no,
        deleted_at=None,
    ).order_by(ReportAttachment.id).all()
    pdfs, warnings = [], []
    for row in rows:
        if attachment_role(row) != "raw_record":
            continue
        raw = read_file_bytes(row.stored_file, row.data)
        if not raw:
            warnings.append(f"{row.name} 内容为空，未并入审核包")
            continue
        if row.name.lower().endswith(".pdf") or "pdf" in (row.content_type or "").lower():
            pdfs.append(raw)
            continue
        suffix = ".docx" if row.name.lower().endswith(".docx") else ".doc"
        converted = office_to_pdf(raw, suffix)
        if converted:
            pdfs.append(converted)
        else:
            warnings.append(f"{row.name} 转 PDF 失败，保留为独立附件")
    return pdfs, warnings


def _report_page_pdfs(report_no, strict_wps=False):
    """Return uploaded report continuation pages in upload order.

    PDF files are used directly. Word files are converted through the same
    WPS/Office conversion chain used elsewhere in report generation.
    """
    rows = ReportAttachment.query.filter_by(
        report_no=report_no,
        deleted_at=None,
    ).order_by(ReportAttachment.id).all()
    completed = [row for row in rows
                 if attachment_role(row) == "completed_report" and attachment_is_active(row)]
    selected_rows = completed[-1:] if completed else [
        row for row in rows
        if attachment_role(row) == "report_page" and attachment_is_active(row)
    ]
    pdfs, warnings = [], []
    for row in selected_rows:
        raw = read_file_bytes(row.stored_file, row.data)
        if not raw:
            if strict_wps:
                raise RuntimeError(f"{row.name} 内容为空，不能生成正式报告")
            warnings.append(f"{row.name} 内容为空，未并入完整报告")
            continue
        lower_name = (row.name or "").lower()
        content_type = (row.content_type or "").lower()
        if lower_name.endswith(".pdf") or "pdf" in content_type:
            pdfs.append(raw)
            continue
        if lower_name.endswith((".doc", ".docx")) or "word" in content_type:
            suffix = ".docx" if lower_name.endswith(".docx") else ".doc"
            converted = (office_to_pdf_wps if strict_wps else office_to_pdf)(raw, suffix)
            if converted:
                pdfs.append(converted)
            else:
                if strict_wps:
                    raise RuntimeError(f"{row.name} 未通过企业 WPS 转换，不能生成正式报告")
                warnings.append(f"{row.name} 转 PDF 失败，未并入完整报告")
            continue
        if strict_wps:
            raise RuntimeError(f"{row.name} 不是受支持的系统模板 DOCX/PDF")
        warnings.append(f"{row.name} 不是 Word/PDF，未并入完整报告")
    return pdfs, warnings


def _selected_other_attachment_pdfs(report, strict_wps=True):
    selected_ids = composition_options(report)["includedOtherAttachmentIds"]
    if not selected_ids:
        return []
    rows = ReportAttachment.query.filter(
        ReportAttachment.report_no == report.report_no,
        ReportAttachment.deleted_at.is_(None),
        ReportAttachment.id.in_(selected_ids),
    ).all()
    by_id = {row.id: row for row in rows}
    pdfs = []
    for attachment_id in selected_ids:
        row = by_id.get(attachment_id)
        if row and is_system_cover_attachment(row):
            continue
        if not row or attachment_role(row) != "other" or not attachment_is_active(row):
            raise RuntimeError(f"选入附件 {attachment_id} 不存在或已失效")
        from .document_module import is_conclusion
        from . import docparser_field_only
        if docparser_field_only.applies_to(report) and is_conclusion(row.name):
            continue  # Conclusion is a subdocument, not an appendix.
        if not attachment_merge_eligible(row):
            raise RuntimeError(f"{row.name} 不支持并入正式报告")
        raw = read_file_bytes(row.stored_file, row.data)
        if not raw:
            raise RuntimeError(f"{row.name} 内容为空，不能并入正式报告")
        lower = str(row.name or "").lower()
        content_type = str(row.content_type or "").lower()
        if lower.endswith(".pdf") or "pdf" in content_type:
            converted = raw
        elif lower.endswith(".docx") or "wordprocessingml" in content_type:
            converted = (office_to_pdf_wps if strict_wps else office_to_pdf)(raw, ".docx")
        elif lower.endswith((".png", ".jpg", ".jpeg")) or content_type in {"image/png", "image/jpeg"}:
            try:
                converted = image_to_pdf(raw)
            except Exception as exc:
                raise RuntimeError(f"{row.name} 图片转 PDF 失败") from exc
        else:
            converted = None
        if not converted:
            raise RuntimeError(f"{row.name} 转 PDF 失败，完整报告未生成")
        pdfs.append(converted)
    return pdfs


def _first_pdf_pages(blob, count):
    """Keep at most ``count`` leading pages from a converted PDF."""
    if not blob or count <= 0:
        return None
    try:
        import fitz

        source = fitz.open(stream=blob, filetype="pdf")
        try:
            if source.page_count <= count:
                return blob
            target = fitz.open()
            try:
                target.insert_pdf(source, from_page=0, to_page=count - 1)
                return target.tobytes(garbage=4, deflate=True)
            finally:
                target.close()
        finally:
            source.close()
    except Exception:
        # Invalid conversion output must not be silently accepted as front matter.
        return None


def _profile_code(profile):
    return profile.code if profile is not None else ""


def _generated_front_matter_pdf(report, profile):
    """Render only the system cover/home pages before uploaded continuation pages.

    Uploaded report pages are the authoritative body.  Rendering the complete
    system document as the prefix duplicates its generated result page.
    """
    if _profile_code(profile) == NCSA_PROFILE["code"]:
        content = content_dict(report)
        return _first_pdf_pages(docx_to_pdf(build_document(report, content, profile)), 1)

    parts = build_cover_parts(report)
    if not parts:
        return None
    if cover_templates_are_combined(report):
        return _first_pdf_pages(docx_to_pdf(parts[0]), 2)

    rendered = []
    for part in parts[:2]:
        page = _first_pdf_pages(docx_to_pdf(part), 1)
        if not page:
            return None
        rendered.append(page)
    return merge_pdf_bytes(rendered) if rendered else None


def build_complete_report_pdf(report):
    """Build a live customer-facing preview: generated report + uploaded pages."""
    raw, warnings = _compose_complete_report_pdf(report)
    from . import docparser_field_only
    if docparser_field_only.applies_to(report):
        from .pdf_report_qr import add_interior_report_qr
        raw, _ = add_interior_report_qr(raw, category=docparser_field_only.profile_for(report)['kind'])
    return raw, warnings


def _compose_complete_report_pdf(report):
    """Compose first, so continuation pages and selected appendices get the QR."""
    profile = select_profile(report)
    from . import docparser_field_only
    if docparser_field_only.applies_to(report):
        from . import document_module
        page_pdfs, warnings = _report_page_pdfs(report.report_no, strict_wps=True)
        no_supplement = composition_options(report).get('noSupplementBody') is True
        if no_supplement and not supports_no_supplement(report):
            raise ValueError('当前模板的结果和签字页需要通过完整报告上传，不能确认无补充正文')
        if no_supplement and page_pdfs:
            raise ValueError('已确认无补充正文，但仍有有效完整报告，请取消无补充确认或移除已上传正文')
        if not page_pdfs and not no_supplement:
            raise RuntimeError('尚未上传填写完成的报告正文模板')
        rows = ReportAttachment.query.filter_by(
            report_no=report.report_no, deleted_at=None,
        ).order_by(ReportAttachment.id).all()
        conclusions = [row for row in rows if attachment_role(row) == 'other'
                       and attachment_is_active(row) and document_module.is_conclusion(row.name)]
        if len(conclusions) > 1:
            raise ValueError('存在多个有效 Conclusion.docx，请只保留一个检测结论文件')
        conclusion = None
        if conclusions:
            row = conclusions[0]
            conclusion = read_file_bytes(row.stored_file, row.data)
            document_module.validate_docx(conclusion)
        selection = docparser_field_only.profile_for(report)
        if composition_options(report).get('preserveUploadedReport') is True:
            if no_supplement:
                raise ValueError('保留上传完整报告模式不能同时确认无补充正文')
            if len(page_pdfs) != 1:
                raise ValueError('保留上传模式需要一份有效完整报告，请合并后上传')
            if conclusions:
                raise ValueError('保留上传模式请将自定义结论写入完整报告，并移除独立 Conclusion.docx')
            docparser_field_only.validate_completed_template_source(
                page_pdfs[0], 'completed.pdf', report.report_no, preserve_uploaded=True,
            )
            complete = document_module.compose_uploaded_pdf(
                page_pdfs[0], _selected_other_attachment_pdfs(report, strict_wps=True),
                category=selection['kind'].title(), language=selection['language'],
                extended=selection['variant'] == 'Extended',
            )
            # Mode information is already exposed by document_preflight. These
            # warnings describe incomplete conversion and block cached previews;
            # a successfully preserved cover must not be classified as a failure.
            return complete, warnings
        module_context = docparser_field_only.report_context(report)
        docparser_field_only._validate_module_report_context(module_context)
        base_docx, _audit = document_module.render_report(selection, module_context, conclusion)
        from .report_generation_notices import notices_from_audit
        warnings.extend(notices_from_audit(_audit))
        base_docx, _symbol_audit = docparser_field_only._replace_legacy_symbol_font(base_docx)
        base_pdf = docx_to_pdf_wps(base_docx)
        if not base_pdf:
            raise RuntimeError('企业 WPS 转换不可用，未生成原包模板 PDF')
        # Keep identity/signature checks. Only unchanged guide pages may be
        # discarded; an explicitly confirmed empty body uses PdfMaker's empty slot.
        validated_uploaded_pdf, _composition = docparser_field_only.compose_completed_pdf(
            base_pdf, page_pdfs, report.report_no, allow_guide_pages=True,
        )
        if no_supplement:
            validated_uploaded_pdf = None
        selected_pdfs = _selected_other_attachment_pdfs(report, strict_wps=True)
        complete = document_module.compose_pdf(
            base_pdf, validated_uploaded_pdf, selected_pdfs, category=selection['kind'].title(),
            language=selection['language'], extended=selection['variant'] == 'Extended',
        )
        return complete, warnings
    page_pdfs, warnings = _report_page_pdfs(report.report_no)
    if page_pdfs:
        pdf_blob = _generated_front_matter_pdf(report, profile)
        if not pdf_blob:
            raise RuntimeError("WPS/LibreOffice 转换不可用，未生成报告封面/首页 PDF")
        selected_pdfs = _selected_other_attachment_pdfs(report, strict_wps=True)
        pdf_blob = merge_pdf_bytes([pdf_blob, *page_pdfs, *selected_pdfs])
        return add_top_right_page_numbers(
            pdf_blob,
            skip_first_page=_profile_code(profile) != NCSA_PROFILE["code"],
            report_no=report.report_no,
        ), warnings

    content = content_dict(report)
    docx_blob = build_document(report, content, profile)
    pdf_blob = docx_to_pdf(docx_blob)
    if not pdf_blob:
        raise RuntimeError("WPS/LibreOffice 转换不可用，未生成报告首页 PDF")
    selected_pdfs = _selected_other_attachment_pdfs(report, strict_wps=True)
    if selected_pdfs:
        pdf_blob = merge_pdf_bytes([pdf_blob, *selected_pdfs])
    return add_top_right_page_numbers(
        pdf_blob,
        skip_first_page=_profile_code(profile) != NCSA_PROFILE["code"],
        report_no=report.report_no,
    ), warnings


def materialize_approved_report_pdf(report, actor=None):
    """Create a new immutable approved Word/PDF version for e-signing.

    Historical reports can have an approved Word-only version.  Never overwrite
    that version: rebuild the complete locked report (front matter plus uploaded
    continuation pages), convert it through the normal WPS chain, and point the
    report at a new approved version containing both artifacts.
    """
    preflight = document_preflight(report, "official")
    if preflight["missing"]:
        raise RuntimeError("报告缺少必填内容：" + "、".join(preflight["missing"]))
    profile = select_profile(report)
    content = preflight["content"]
    snapshot = source_snapshot(report, content, profile, "official")
    source_hash = snapshot_hash(snapshot)
    docx_blob = (None if composition_options(report).get('preserveUploadedReport') is True
                 else build_document(report, content, profile, "official"))
    pdf_blob, complete_warnings = build_complete_report_pdf(report)
    if not pdf_blob or not pdf_blob.lstrip().startswith(b"%PDF"):
        raise RuntimeError("完整报告转换结果不是有效 PDF")

    max_version = db.session.query(func.max(ReportDocumentVersion.version_no)).filter_by(
        report_no=report.report_no,
        output_kind="official",
    ).scalar() or 0
    version_no = max_version + 1
    created_by = getattr(actor, "account", None) or "esign-system"
    from . import docparser_field_only
    docx_file = None
    if not docparser_field_only.applies_to(report):
        docx_file = persist_bytes(
            docx_blob,
            category="report_document",
            original_name=f"{report.report_no}-V{version_no}.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            created_by=created_by,
        )
    pdf_file = persist_bytes(
        pdf_blob,
        category="report_document",
        original_name=f"{report.report_no}-V{version_no}.pdf",
        content_type="application/pdf",
        created_by=created_by,
    )
    warnings = list(preflight["warnings"])
    warnings.extend(complete_warnings)
    if docparser_field_only.applies_to(report):
        warnings.append("原包模板和上传正文已按哈希快照留存；正式件仅固化合成 PDF")
    warnings.append("电子签发前已自动生成并锁定完整 PDF")
    version = ReportDocumentVersion(
        report_no=report.report_no,
        output_kind="official",
        version_no=version_no,
        status="approved",
        profile_code=profile.code if profile else FALLBACK_PROFILE["code"],
        composition=report_composition(report, profile),
        snapshot=snapshot,
        warnings=warnings,
        source_hash=source_hash,
        sha256=hashlib.sha256(pdf_blob).hexdigest(),
        docx_file=docx_file,
        pdf_file=pdf_file,
        created_by=created_by,
    )
    db.session.add(version)
    db.session.flush()
    previous_version_id = report.approved_document_version_id
    report.current_document_version_id = version.id
    report.approved_document_version_id = version.id
    report.version = f"V{version.version_no}"
    add_operation_audit(
        "report.esign.pdf.materialize",
        "report",
        report.report_no,
        category="report",
        before={"approvedVersionId": previous_version_id},
        after={"approvedVersionId": version.id, "sha256": version.sha256},
        message="电子签发前自动生成并锁定完整 PDF",
        actor=actor,
    )
    return version


def _execute_render_job(app, job_id):
    with app.app_context():
        job = db.session.get(ReportRenderJob, job_id)
        if not job:
            return
        try:
            job.status = "running"
            job.progress = 10
            job.message = "正在检查模板字段"
            db.session.commit()
            report = Report.query.filter_by(report_no=job.report_no).first()
            if not report:
                raise RuntimeError("报告不存在")
            from .applications.report_lifecycle.queries import report_content_editable
            if not report_content_editable(report):
                raise ValueError('报告已离开可编辑阶段，旧生成任务已停止')
            profile = select_profile(report)
            preflight = document_preflight(report, job.output_kind)
            if preflight["missing"]:
                raise RuntimeError("缺少必填字段：" + "、".join(preflight["missing"]))
            content = preflight["content"]
            snapshot = source_snapshot(report, content, profile, job.output_kind)
            source_hash = snapshot_hash(snapshot)
            job.progress = 35
            job.message = "正在生成 Word 报告"
            db.session.commit()
            docx_blob = (None if composition_options(report).get('preserveUploadedReport') is True
                         else build_document(report, content, profile, job.output_kind))
            job.progress = 60
            job.message = "正在通过 WPS 转换 PDF"
            db.session.commit()
            warnings = list(preflight["warnings"])
            from . import docparser_field_only
            pdf_blob, complete_warnings = build_complete_report_pdf(report)
            warnings.extend(complete_warnings)
            if job.output_kind == "audit":
                raw_pdfs, raw_warnings = _raw_record_pdfs(report.report_no)
                warnings.extend(raw_warnings)
                if raw_pdfs:
                    pdf_blob = merge_pdf_bytes([pdf_blob, *raw_pdfs])
            job.progress = 82
            job.message = "正在固化报告版本"
            db.session.commit()
            # WPS conversion is slow and runs outside a report lock. Re-read
            # inputs under the aggregate lock before publishing any pointer.
            report = Report.query.filter_by(report_no=job.report_no).with_for_update().populate_existing().one()
            db.session.expire_all()
            if (not report_content_editable(report)
                    or snapshot_hash(source_snapshot(report, output_kind=job.output_kind)) != source_hash):
                raise ValueError('报告内容或流程已变化，旧生成结果未采用；请生成并确认当前报告')
            max_version = db.session.query(func.max(ReportDocumentVersion.version_no)).filter_by(
                report_no=report.report_no, output_kind=job.output_kind,
            ).scalar() or 0
            version_no = max_version + 1
            docx_file = None
            if not docparser_field_only.applies_to(report):
                docx_file = persist_bytes(
                    docx_blob,
                    category="report_document",
                    original_name=f"{report.report_no}-V{version_no}.docx",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    created_by=job.requested_by,
                )
            else:
                warnings.append("原包模板和上传正文已按哈希快照留存；正式件仅固化合成 PDF")
            pdf_file = persist_bytes(
                pdf_blob,
                category="report_document",
                original_name=f"{report.report_no}-V{version_no}.pdf",
                content_type="application/pdf",
                created_by=job.requested_by,
            )
            version = ReportDocumentVersion(
                report_no=report.report_no,
                output_kind=job.output_kind,
                version_no=version_no,
                profile_code=profile.code if profile else FALLBACK_PROFILE["code"],
                composition=report_composition(report, profile),
                snapshot=snapshot,
                warnings=warnings,
                source_hash=source_hash,
                sha256=hashlib.sha256(pdf_blob).hexdigest(),
                docx_file=docx_file,
                pdf_file=pdf_file,
                docx_data=None,
                pdf_data=None,
                created_by=job.requested_by,
            )
            db.session.add(version)
            db.session.flush()
            if job.output_kind == "official":
                report.current_document_version_id = version.id
                report.version = f"V{version.version_no}"
            job.status = "completed"
            job.progress = 100
            job.message = "报告生成完成"
            job.version_id = version.id
            job.completed_at = datetime.utcnow()
            actor = User.query.filter_by(account=job.requested_by).first()
            add_operation_audit(
                "report.document.generate",
                "report",
                report.report_no,
                category="report",
                after=version.meta(source_hash),
                message=f"生成{job.output_kind}报告 V{version.version_no}",
                actor=actor,
            )
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            job = db.session.get(ReportRenderJob, job_id)
            if job:
                job.status = "failed"
                job.message = str(exc)
                job.completed_at = datetime.utcnow()
                actor = User.query.filter_by(account=job.requested_by).first()
                add_operation_audit(
                    "report.document.generate",
                    "report",
                    job.report_no,
                    category="report",
                    success=False,
                    message=job.message,
                    actor=actor,
                )
                db.session.commit()


def create_render_job(app, report, output_kind, user):
    job = ReportRenderJob(
        id=str(uuid.uuid4()),
        report_no=report.report_no,
        output_kind=output_kind,
        requested_by=user.account,
        status="queued",
        progress=0,
        message="已进入生成队列",
    )
    db.session.add(job)
    db.session.commit()
    if app.config.get("REPORT_RENDER_SYNC"):
        _execute_render_job(app, job.id)
    else:
        thread = threading.Thread(target=_execute_render_job, args=(app, job.id), daemon=True)
        thread.start()
    return job


def mark_interrupted_jobs():
    rows = ReportRenderJob.query.filter(ReportRenderJob.status.in_(["queued", "running"])).all()
    for row in rows:
        row.status = "failed"
        row.message = "服务重启导致生成任务中断，请重新生成"
        row.completed_at = datetime.utcnow()
    if rows:
        db.session.commit()
