"""Render the official 4204d/4204g business forms without rebuilding their layout."""

import json
import os
import re
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile

from lxml import etree

TPL_DIR = os.path.join(os.path.dirname(__file__), "entrust_templates")
PRODUCT_TEMPLATE = "委托单-产品类.docx"
ENGINEERING_TEMPLATE = "委托单-工程类.docx"
FIELD_DICTIONARY = "field_dictionary.json"
EXPECTED_PAGES = {"product": 4, "engineering": 3, "product-extended": 8, "engineering-extended": 6}


def require_business_form_page_count(pdf, template_kind):
    """Validate the exact official business-form template page count."""

    actual = business_form_pdf_pages(pdf)
    expected = EXPECTED_PAGES[template_kind]
    if actual != expected:
        raise ValueError(f"{template_kind} 模板应严格为 {expected} 页，实际为 {actual} 页")
    return actual

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

_EMPTY_VALUES = {
    "", "-", "—", "待录入", "待检测人员录入", "待检测人员录入并上传", "（请填写）",
}


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = "、".join(_clean(item) for item in value if _clean(item))
    if isinstance(value, dict):
        return ""
    text = str(value).strip()
    return "" if text in _EMPTY_VALUES else text


def _first(*values):
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _report_copy_count(value):
    """Return only the numeric copy count expected by the original template.

    The template already contains the fixed word ``份``.  Historical forms may
    contain values such as ``3份`` or ``份数 3 份``; passing those strings through
    would duplicate the template's fixed wording.
    """
    match = re.search(r"\d+", _clean(value))
    return match.group(0) if match else ""


def _standard_display(value, department="", record_ids=None):
    """Expand controlled standard codes to ``编号 中文名称`` for the form.

    This is a read-only adapter lookup.  If the controlled library is not
    available (for example in an isolated renderer test), the saved text is
    retained verbatim rather than blocking document generation.
    """
    source = _clean(value)
    if not source:
        return ""
    try:
        from .standard_control import find_controlled_standard, split_standard_codes
        parts = split_standard_codes(source)
        rendered = []
        from .standard_control import selected_controlled_standards
        for item, _result in selected_controlled_standards(parts, record_ids, department):
            part = _result["code"]
            code = _clean(getattr(item, "code", "")) if item is not None else ""
            name = _clean(getattr(item, "name", "")) if item is not None else ""
            rendered.append(" ".join(piece for piece in (code, name) if piece) or part)
        return "；".join(rendered) if rendered else source
    except Exception:
        return source


def _detail_field(detail, section, *keys):
    wanted = set(keys)
    for item in (detail or {}).get("summary", []):
        if item.get("title") != section:
            continue
        for field in item.get("fields", []):
            if len(field) >= 2 and field[0] in wanted:
                value = _clean(field[1])
                if value:
                    return value
    return ""


def _cn_date(value):
    from .report_date_display import report_date
    return report_date(_clean(value))


def _money_number(value):
    text = re.sub(r"[^0-9.\-]", "", _clean(value).replace(",", ""))
    if not text:
        return None
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _four_digit_upper(number):
    digits = "零壹贰叁肆伍陆柒捌玖"
    units = ("仟", "佰", "拾", "")
    result = []
    pending_zero = False
    for index, divisor in enumerate((1000, 100, 10, 1)):
        digit = (number // divisor) % 10
        if digit:
            if pending_zero and result:
                result.append("零")
            result.extend((digits[digit], units[index]))
            pending_zero = False
        elif result:
            pending_zero = True
    return "".join(result)


def _upper_money(value):
    amount = _money_number(value)
    if amount is None:
        return ""
    negative = amount < 0
    amount = abs(amount)
    integer = int(amount)
    fraction = int((amount - integer) * 100)
    group_units = ("", "万", "亿", "兆")
    groups = []
    index = 0
    while integer:
        groups.append((integer % 10000, index))
        integer //= 10000
        index += 1
    if not groups:
        integer_text = "零"
    else:
        parts = []
        previous_group = None
        for group, group_index in reversed(groups):
            if not group:
                previous_group = group
                continue
            if parts and (group < 1000 or previous_group == 0):
                parts.append("零")
            parts.append(_four_digit_upper(group) + group_units[group_index])
            previous_group = group
        integer_text = "".join(parts)
    digits = "零壹贰叁肆伍陆柒捌玖"
    jiao, fen = divmod(fraction, 10)
    fraction_text = ""
    if jiao:
        fraction_text += digits[jiao] + "角"
    elif fen:
        fraction_text += "零"
    if fen:
        fraction_text += digits[fen] + "分"
    if not fraction_text:
        fraction_text = "整"
    return ("负" if negative else "") + integer_text + "元" + fraction_text


def _document_kind(entrust, report=None):
    detail = (getattr(report, "detail", None) or {}) if report is not None else {}
    raw = detail.get("rawSample") or {}
    info = getattr(entrust, "info", None) or {}
    candidates = (
        raw.get("reportType"),
        _detail_field(detail, "送样信息", "报告类型"),
        getattr(entrust, "project_type", ""),
        info.get("erpType"),
        info.get("erpProjectType"),
    )
    selected = next((_clean(item) for item in candidates if _clean(item)), "")
    if selected:
        return "engineering" if "工程" in selected else "product"
    return "engineering" if "工程" in _clean(getattr(entrust, "project_name", "")) else "product"


def _select_template(kind):
    name = ENGINEERING_TEMPLATE if kind == "engineering" else PRODUCT_TEMPLATE
    path = os.path.join(TPL_DIR, name)
    return path if os.path.exists(path) else None


def _business_category(*values):
    for value in values:
        text = _clean(value)
        if text in ("委托", "委托（有见证送检）", "型式检验", "型式试验", "抽样检测", "抽样型式检验", "委托型式检验"):
            return text
        normalized = re.sub(r"[\s_-]+", "", text).lower()
        if "抽样" in text or "sampling" in normalized:
            return "抽样"
        if "校准" in text or "calibrat" in normalized:
            return "校准"
        if "委托" in text or "entrust" in normalized or "commission" in normalized:
            return "委托"
    return ""


def _business_values(entrust, report=None, project_no="", language="CN"):
    from .report_date_display import production_date_text, report_date
    from .document_field_projection import judgment_basis, test_items, test_dates
    from .contract_review_output import review_flags, effective_review
    info = getattr(entrust, "info", None) or {}
    detail = (getattr(report, "detail", None) or {}) if report is not None else {}
    raw = detail.get("rawSample") or {}
    review = effective_review(report)
    if review.get("result") != "通过":
        review = {}
    pickup = (getattr(report, "sample_pickup", None) or {}) if report is not None else {}

    def d(section, *keys):
        return _detail_field(detail, section, *keys)

    amount = _first(raw.get("stdPrice"), getattr(entrust, "amount", ""))
    production = " / ".join(filter(None, (
        report_date(production_date_text(detail)),
        _first(raw.get("factoryNo"), d("送样信息", "出厂编号")),
    )))
    quantity = _first(raw.get("sampleAmount"), info.get("sampleAmount"), info.get("quantity"),
                      d("送样信息", "样品数量"))
    unit = _first(raw.get("unit"), info.get("quantityUnit"),
                  d("送样信息", "数量单位"))
    if quantity and unit and not quantity.endswith(unit):
        quantity = f"{quantity} {unit}"
    project_identifier = _first(
        project_no,
        raw.get("erpProjectNo"),
        raw.get("projectCode"),
        info.get("erpProjectNo"),
        info.get("projectCode"),
        info.get("projectRecordNo"),
        info.get("projectTradeCode"),
        d("项目信息", "项目编号", "工程备案编号", "工程编码(交易中心)"),
    )
    from .sample_identity import sample_number
    sample_identifier = _first(
        sample_number(report),
        raw.get("sampleNo"),
        d("送样信息", "样品编号"),
        d("样品信息", "样品编号"),
    )
    test_start, test_end, _ = test_dates(
        detail, d("实验信息", "试验开始日期", "检测开始日期"),
        d("实验信息", "试验结束日期", "检测日期", "检测结束日期"),
    )
    owner = _first(d("实验信息", "试验员/主检", "主检"), getattr(report, "owner", ""))
    deliver_way = _first(raw.get("deliverWay"), info.get("reportDeliveryMethod"),
                         d("报告发送", "报告交付方式"))
    sample_handle = _first(raw.get("sampleHandle"), info.get("sampleHandlingMethod"),
                           d("报告发送", "样品处理方式"))

    standard_department = _first(
        raw.get("testDept"), raw.get("testRoom"), d("送样信息", "检测部门", "检测室"),
        getattr(report, "department", "") if report else "",
    )
    basis_source = _first(
        raw.get("testBases"), raw.get("testBasis"), d("实验信息", "检测依据", "执行标准"),
    )
    commission_text = raw.get("commissionText") or {}
    if not isinstance(commission_text, dict):
        commission_text = {}
    judgment_source = judgment_basis(detail, d("实验信息", "判定依据", "判定标准", "标准/判定"))
    values = {
        "project_identifier": project_identifier,
        "sample_identifier": sample_identifier,
        "entrust_date": _first(info.get("entrustDate"),
                               getattr(entrust, "created_at", None).strftime("%Y-%m-%d")
                               if getattr(entrust, "created_at", None) else ""),
        "client": _first(getattr(entrust, "client", ""), d("委托信息", "委托单位")),
        "project_name": _first(raw.get("sampleName"), info.get("projectName"),
                                info.get("sampleName"), d("送样信息", "样品/工程名称")),
        "sample_name": _first(raw.get("sampleName"), info.get("sampleName"),
                               d("送样信息", "样品名称", "样品/工程名称")),
        "spec": _first(raw.get("spec"), info.get("specification"),
                        d("送样信息", "规格型号")),
        # The commission form is owned by the entrust-information form.  Prefer
        # its persisted manufacturer over a later sample snapshot, which may
        # contain a temporary code while the sample is still being registered.
        "manufacturer": _first(info.get("manufacturer"), raw.get("manufacturer"),
                               d("送样信息", "生产厂家", "生产单位")),
        "production": production,
        "send_date": _first(raw.get("sendDate"), d("送样信息", "送样日期")),
        "category": _business_category(
            raw.get("testCategory"),
            raw.get("testType"),
            d("送样信息", "检测类别", "检验类别"),
            d("样品信息", "检测类别", "检验类别"),
        ),
        "quantity": quantity,
        "trademark": _first(raw.get("trademark"), d("送样信息", "商标")),
        "trademark_image": _clean(raw.get("trademarkImage")),
        "basis": commission_text["basis"] if isinstance(commission_text.get("basis"), str) else _standard_display(basis_source, standard_department, raw.get("standardItemIds")),
        "judgment": judgment_source,
        "test_project": commission_text["items"] if isinstance(commission_text.get("items"), str) else test_items(detail, _first(raw.get("project"), getattr(report, "project", "") if report else "",
                               d("实验信息", "检测项目"))),
        "remark": _first(raw.get("remark"), info.get("notes"), info.get("remark"),
                          d("项目信息", "委托单备注")),
        "consignor": _clean(info.get("consignor")),
        "consignor_phone": _clean(info.get("consignorPhone")),
        "client_address": _first(info.get("clientAddr"), info.get("clientAddress")),
        "contract_party_a": _first(info.get("contractPartyA"), getattr(entrust, "client", "")),
        "other_party_a": _clean(info.get("otherPartyA")),
        "handler": _first(info.get("handler"), getattr(entrust, "owner", "")),
        "handler_phone": _clean(info.get("handlerPhone")),
        "review_items": review.get("items") or {},
        "review_flags": review_flags(report),
        "reviewer": _clean(review.get("reviewer")),
        "cma": bool(review.get("cma")),
        "cnas": bool(review.get("cnas")),
        "appearance": _first(raw.get("appearance"), d("送样信息", "外观")),
        "nameplate": _first(raw.get("nameplate"), d("送样信息", "铭牌")),
        "sample_other": _first(raw.get("sealStatus"), d("抽样信息", "封样状态")),
        "sample_handle": sample_handle,
        "deliver_way": deliver_way,
        "deliver_count": _report_copy_count(_first(
            raw.get("deliverStd"), info.get("reportCopies"), d("报告发送", "报告交付份数"),
        )),
        "deliver_date": _first(raw.get("sendOutTime"), info.get("expectedDate"),
                                d("报告发送", "报告承诺时间(外部)")),
        "amount": amount,
        "amount_upper": _first(info.get("amountUpper"), _upper_money(amount)),
        "pay_status": _first(raw.get("payStatus"), d("结算信息", "缴费情况")),
        "paid": _first(raw.get("paid"), d("结算信息", "已缴费")),
        "other_payment": _first(raw.get("otherSettle"), d("结算信息", "其他")),
        "laboratory": standard_department,
        "owner": owner,
        "participants": _first(raw.get("participants"), d("实验信息", "参加试验人员", "参加检验人员")),
        "writer": _first(d("实验信息", "报告编写人"), owner),
        "test_location": _first(raw.get("testLocation"), d("送样信息", "检测地点")),
        "plan_complete": _first(getattr(report, "deadline", "") if report else "",
                                raw.get("sendInTime"), d("报告发送", "报告承诺时间(内部)")),
        "approval_date": _first(d("实验信息", "报告批准日期", "实际完成日期")),
        "pickup_person": _clean(pickup.get("receiverName")),
        "pickup_date": _clean(pickup.get("pickupTime")),
        "return_person": _clean(pickup.get("managerName")) if "回库" in _clean(getattr(report, "sample_status", "")) else "",
        "return_date": _clean(pickup.get("returnTime")),
        "test_start": test_start,
        "test_end": test_end,
        "before_status": _first(raw.get("appearance"), d("送样信息", "外观")),
        "after_status": _clean(getattr(report, "sample_status", "") if report else ""),
        "inspector": owner,
    }
    for key in ('entrust_date', 'send_date', 'deliver_date', 'plan_complete',
                'approval_date', 'pickup_date', 'return_date', 'test_start', 'test_end'):
        values[key] = _cn_date(values[key])
    localized = {}
    if language != 'CN':
        from .entrust_output_fields import localized_entrust_fields
        fields = localized_entrust_fields(detail, values['category'], values['send_date'], language)
        localized = {'testCategory': fields['Category'], 'produceDate': fields['ManufacturingDate'],
                     'sendDate': fields['SubmissionDate']}
        values['category_display'] = fields['Category']
        values['send_date'] = fields['SubmissionDate']
        values['production'] = ' / '.join(filter(None, (
            fields['ManufacturingDate'], _first(raw.get('factoryNo'), d('送样信息', '出厂编号')),
        )))
    values["template_fields"] = _template_field_values(entrust, report, values, localized)
    return values


def _dictionary_fields():
    path = os.path.join(TPL_DIR, FIELD_DICTIONARY)
    try:
        with open(path, encoding="utf-8") as handle:
            return (json.load(handle) or {}).get("fields") or []
    except (OSError, TypeError, ValueError):
        return []


def _nested_list_value(value, leaf):
    if not isinstance(value, list):
        return ""
    results = []
    for item in value:
        if isinstance(item, dict):
            candidate = _clean(item.get(leaf))
        else:
            candidate = _clean(item)
        if candidate and candidate not in results:
            results.append(candidate)
    return "、".join(results)


def _template_field_values(entrust, report, values, localized):
    """Resolve the stable WT/YP dictionary paths against the current business snapshot."""
    info = getattr(entrust, "info", None) or {}
    detail = (getattr(report, "detail", None) or {}) if report is not None else {}
    raw = detail.get("rawSample") or {}
    top_level = {
        "contractNo": getattr(entrust, "contract_no", ""),
        "erpContractNo": getattr(entrust, "contract_no", ""),
        "projectType": getattr(entrust, "project_type", ""),
        "projectName": getattr(entrust, "project_name", ""),
        "entrustNo": getattr(entrust, "entrust_no", ""),
        "client": getattr(entrust, "client", ""),
        "handleDept": getattr(entrust, "department", ""),
        "handler": getattr(entrust, "owner", ""),
    }
    from .sample_identity import sample_number
    report_level = {
        "sampleNo": sample_number(report),
        "reportNo": getattr(report, "report_no", "") if report is not None else "",
        "project": getattr(report, "project", "") if report is not None else "",
        "testDept": getattr(report, "department", "") if report is not None else "",
        "deadline": getattr(report, "deadline", "") if report is not None else "",
    }
    resolved = {}
    for field in _dictionary_fields():
        code = field.get("code") or ""
        path = field.get("path") or ""
        value = ""
        if path.endswith("[].display"):
            value = _nested_list_value(raw.get(path[:-10]), "display")
        elif path.endswith("[].dept"):
            value = _nested_list_value(raw.get(path[:-7]), "dept")
        elif path.endswith("[].amount"):
            value = _nested_list_value(raw.get(path[:-9]), "amount")
        elif path.endswith("[]"):
            value = _nested_list_value(raw.get(path[:-2]), "value")
        else:
            value = _first(info.get(path), raw.get(path), report_level.get(path), top_level.get(path))
        if path == "entrustDate" and not value:
            created = getattr(entrust, "created_at", None)
            value = created.strftime("%Y-%m-%d") if created else ""
        elif path == "testRoom" and not value:
            value = report_level.get("testDept") or ""
        elif path == "stdPrice" and not value:
            value = _clean(getattr(entrust, "amount", ""))
        if path == 'produceDate':
            from .report_date_display import production_date_text
            value = production_date_text(detail)
        if path in {'entrustDate', 'produceDate', 'sendDate', 'sendOutTime', 'sendInTime',
                    'deadline', 'samplingTime', 'sampleTime', 'sampleArrivalDate',
                    'innerStdDate', 'testStartDate', 'testEndDate'}:
            value = _cn_date(value)
        resolved[code] = _clean(localized.get(path, value))

    # Special non-business placeholders are deliberately separate from the stable
    # dictionary. They are derived values, not editable form fields.
    resolved["SYS_AMOUNT_UPPER"] = values.get("amount_upper", "")
    resolved["SYS_REVIEW_SIGNATURE"] = values.get("reviewer", "")
    return resolved


def _normalize(text):
    return re.sub(r"\s+", "", text or "").replace("：", ":")


def _text_nodes(element):
    return element.xpath(".//w:t[not(ancestor::w:txbxContent)]", namespaces=NS)


def _element_text(element):
    return "".join(node.text or "" for node in _text_nodes(element))


def _direct_paragraphs(cell):
    return cell.xpath("./w:p", namespaces=NS)


def _containing_cell(element):
    cells = element.xpath("ancestor::w:tc[1]", namespaces=NS)
    return cells[0] if cells else None


def _weighted_length(value):
    total = 0.0
    for char in _clean(value):
        if char.isspace():
            total += 0.35
        elif ord(char) < 128:
            total += 0.55
        else:
            total += 1.0
    return total


def _existing_half_points(paragraph):
    for run in reversed(paragraph.xpath("./w:r", namespaces=NS)):
        sizes = run.xpath("./w:rPr/w:sz", namespaces=NS)
        if sizes:
            try:
                return int(sizes[0].get(W + "val"))
            except (TypeError, ValueError):
                pass
    return 18


def _adaptive_half_points(paragraph, value):
    """Fit inserted text to the original cell without changing table geometry."""
    cell = _containing_cell(paragraph)
    base = min(_existing_half_points(paragraph), 20)
    if cell is None:
        return base
    widths = cell.xpath("./w:tcPr/w:tcW", namespaces=NS)
    rows = cell.xpath("ancestor::w:tr[1]", namespaces=NS)
    heights = rows[0].xpath("./w:trPr/w:trHeight", namespaces=NS) if rows else []
    try:
        width_points = int(widths[0].get(W + "w")) / 20 if widths else 120
    except (TypeError, ValueError):
        width_points = 120
    try:
        height_points = max(int(item.get(W + "val")) for item in heights) / 20 if heights else 24
    except (TypeError, ValueError):
        height_points = 24
    text_length = _weighted_length(value)
    for half_points in range(base, 11, -1):
        font_points = half_points / 2
        line_capacity = max(1.0, width_points / max(font_points, 1))
        if height_points < 30:
            lines = 1
        else:
            usable_height = max(font_points, height_points - 6)
            lines = max(1, int(usable_height / max(font_points * 1.35, 1)))
        if text_length <= line_capacity * lines * 0.82:
            return half_points
    return 12


def _set_run_size(run, half_points):
    properties = run.find(W + "rPr")
    if properties is None:
        properties = etree.Element(W + "rPr")
        run.insert(0, properties)
    for tag in ("sz", "szCs"):
        node = properties.find(W + tag)
        if node is None:
            node = etree.SubElement(properties, W + tag)
        node.set(W + "val", str(half_points))


def _cap_paragraph_size(paragraph, half_points):
    for run in paragraph.xpath("./w:r", namespaces=NS):
        _set_run_size(run, min(_existing_half_points(paragraph), half_points))


def _mark_dynamic_row(paragraph):
    rows = paragraph.xpath("ancestor::w:tr[1]", namespaces=NS)
    if rows:
        rows[0].set("data-rendered", "1")


def _append_run(paragraph, value):
    text = _clean(value)
    if not text:
        return
    run = etree.Element(W + "r")
    existing_runs = paragraph.xpath("./w:r", namespaces=NS)
    for existing in reversed(existing_runs):
        properties = existing.find(W + "rPr")
        if properties is not None:
            run.append(deepcopy(properties))
            break
    node = etree.SubElement(run, W + "t")
    if text[:1].isspace() or text[-1:].isspace():
        node.set(XML_SPACE, "preserve")
    node.text = text
    _set_run_size(run, _adaptive_half_points(paragraph, _element_text(paragraph) + text))
    paragraph.append(run)
    _mark_dynamic_row(paragraph)


def _append_cell_value(cell, value):
    text = _clean(value)
    if not text:
        return False
    paragraphs = _direct_paragraphs(cell)
    if not paragraphs:
        paragraphs = [etree.SubElement(cell, W + "p")]
    _append_run(paragraphs[0], text)
    return True


def _set_paragraph_text(paragraph, value):
    nodes = _text_nodes(paragraph)
    if not nodes:
        _append_run(paragraph, value)
        return
    nodes[0].text = str(value)
    if str(value)[:1].isspace() or str(value)[-1:].isspace():
        nodes[0].set(XML_SPACE, "preserve")
    for node in nodes[1:]:
        node.text = ""
    run = nodes[0].getparent()
    if run is not None and run.tag == W + "r":
        _set_run_size(run, _adaptive_half_points(paragraph, value))
    _mark_dynamic_row(paragraph)


def _set_cell_text(cell, value):
    paragraphs = _direct_paragraphs(cell)
    if not paragraphs:
        paragraphs = [etree.SubElement(cell, W + "p")]
    _set_paragraph_text(paragraphs[0], value)
    for paragraph in paragraphs[1:]:
        for node in _text_nodes(paragraph):
            node.text = ""


def _transform_same_length(paragraph, transform):
    nodes = _text_nodes(paragraph)
    old = "".join(node.text or "" for node in nodes)
    new = transform(old)
    if not old or new == old:
        return
    if len(new) != len(old):
        _set_paragraph_text(paragraph, new)
        return
    offset = 0
    for node in nodes:
        length = len(node.text or "")
        node.text = new[offset:offset + length]
        offset += length


_TEMPLATE_TOKEN = re.compile(r"\{\{\s*((?:WT|YP)\d{3}|SYS_[A-Z0-9_]+)\s*\}\}")


def _distribute_original_text(text, start, end, spans, outputs):
    for index, node_start, node_end in spans:
        left = max(start, node_start)
        right = min(end, node_end)
        if left < right:
            outputs[index] += text[left:right]


def _replace_paragraph_template_tokens(paragraph, field_values):
    """Replace split-run template tokens while retaining surrounding run formatting."""
    nodes = _text_nodes(paragraph)
    original_nodes = [node.text or "" for node in nodes]
    text = "".join(original_nodes)
    matches = list(_TEMPLATE_TOKEN.finditer(text))
    if not matches:
        return 0
    spans = []
    offset = 0
    for index, value in enumerate(original_nodes):
        spans.append((index, offset, offset + len(value)))
        offset += len(value)
    outputs = ["" for _ in nodes]
    owners = set()
    cursor = 0
    for match in matches:
        _distribute_original_text(text, cursor, match.start(), spans, outputs)
        owner = next(
            (index for index, start, end in spans if start <= match.start() < end),
            spans[-1][0],
        )
        outputs[owner] += _clean(field_values.get(match.group(1), ""))
        owners.add(owner)
        cursor = match.end()
    _distribute_original_text(text, cursor, len(text), spans, outputs)
    for index, (node, value) in enumerate(zip(nodes, outputs, strict=True)):
        node.text = value
        if value[:1].isspace() or value[-1:].isspace():
            node.set(XML_SPACE, "preserve")
        else:
            node.attrib.pop(XML_SPACE, None)
        if index in owners:
            run = node.getparent()
            if run is not None and run.tag == W + "r":
                _set_run_size(run, _adaptive_half_points(paragraph, value))
    return len(matches)


def _has_numbered_template_tokens(root):
    return any(
        _TEMPLATE_TOKEN.search(_element_text(paragraph))
        for paragraph in root.xpath(".//w:p", namespaces=NS)
    )


def _apply_numbered_template_fields(root, values):
    field_values = values.get("template_fields") or {}
    replaced = sum(
        _replace_paragraph_template_tokens(paragraph, field_values)
        for paragraph in root.xpath(".//w:p", namespaces=NS)
    )
    remaining = [
        match.group(0)
        for paragraph in root.xpath(".//w:p", namespaces=NS)
        for match in _TEMPLATE_TOKEN.finditer(_element_text(paragraph))
    ]
    if remaining:
        raise ValueError(f"委托单模板存在未替换字段：{', '.join(sorted(set(remaining)))}")
    return replaced


def _table_rows(root):
    for table in root.xpath(".//w:tbl", namespaces=NS):
        for row in table.xpath("./w:tr", namespaces=NS):
            yield table, row, row.xpath("./w:tc", namespaces=NS)


def _matching_cells(root, label):
    wanted = _normalize(label)
    for _, _, cells in _table_rows(root):
        for cell in cells:
            if _normalize(_element_text(cell)) == wanted:
                yield cell


def _following_cells(root, label):
    wanted = _normalize(label)
    for _, _, cells in _table_rows(root):
        for index, cell in enumerate(cells[:-1]):
            if _normalize(_element_text(cell)) == wanted:
                yield cells[index + 1]


def _fill_adjacent(root, label, value, blank_only=False):
    if not _clean(value):
        return
    for cell in _following_cells(root, label):
        if blank_only and _clean(_element_text(cell)):
            continue
        _append_cell_value(cell, value)


def _fill_inline(root, label, value):
    if not _clean(value):
        return
    for cell in _matching_cells(root, label):
        paragraphs = _direct_paragraphs(cell)
        if paragraphs:
            _append_run(paragraphs[-1], value)


def _mark(text, label, checked):
    if not checked:
        return text
    return re.sub(r"□(?=\s*" + re.escape(label) + r")", "☑", text)


def _apply_headers(root, kind, values):
    label = "项目编号" if kind == "engineering" else "样品编号"
    identifier = values["sample_identifier"]
    line = f"{label}：{identifier}    委托日期：{_cn_date(values['entrust_date'])}"
    for paragraph in root.xpath("/w:document/w:body/w:p", namespaces=NS):
        if _normalize(_element_text(paragraph)).startswith(_normalize(label + ":")):
            _set_paragraph_text(paragraph, line)


def _apply_contract_review(root, values):
    from .contract_review_output import mark_review_text
    for cell in _following_cells(root, "合同评审"):
        paragraphs = _direct_paragraphs(cell)
        for paragraph in paragraphs:
            _transform_same_length(paragraph, lambda text: mark_review_text(text, values["review_flags"]))
            _cap_paragraph_size(paragraph, 18)
        if values["reviewer"] and paragraphs:
            target = next((p for p in paragraphs if "签字" in _element_text(p)), paragraphs[-1])
            if values["reviewer"] not in _element_text(target):
                _append_run(target, values["reviewer"])
            _cap_paragraph_size(target, 18)


def _apply_checkboxes(root, values):
    appearance = values["appearance"]
    nameplate = values["nameplate"]
    for cell in (c for _, _, cells in _table_rows(root) for c in cells if "外观" in _element_text(c) and "铭牌" in _element_text(c)):
        for paragraph in _direct_paragraphs(cell):
            def transform(text):
                if "不正常" in appearance:
                    text = _mark(text, "不正常", True)
                elif "正常" in appearance:
                    text = _mark(text, "正常", True)
                if nameplate == "无" or "无" in nameplate:
                    text = _mark(text, "无", True)
                elif nameplate == "有" or "有" in nameplate:
                    text = _mark(text, "有", True)
                return text
            _transform_same_length(paragraph, transform)
            _cap_paragraph_size(paragraph, 18)
        if values["sample_other"] and values["sample_other"] not in _element_text(cell):
            paragraphs = _direct_paragraphs(cell)
            if paragraphs:
                _append_run(paragraphs[-1], values["sample_other"])

    treatment = values["sample_handle"]
    for _, _, cells in _table_rows(root):
        for cell in cells:
            text = _element_text(cell)
            if "取回" not in text or "中心处理" not in text:
                continue
            for paragraph in _direct_paragraphs(cell):
                def transform(line):
                    line = _mark(line, "取回", "取回" in treatment)
                    line = _mark(line, "中心处理", "中心处理" in treatment)
                    line = _mark(line, "委托中心托运", "托运" in treatment)
                    return line
                _transform_same_length(paragraph, transform)
                _cap_paragraph_size(paragraph, 18)


def _apply_delivery(root, values):
    way = values["deliver_way"]
    for cell in _following_cells(root, "提交报告方式及时间"):
        paragraphs = _direct_paragraphs(cell)
        if not paragraphs:
            continue
        old = _element_text(paragraphs[0])
        if not old:
            continue
        text = _mark(old, "自取", "自取" in way)
        text = _mark(text, "邮寄", "邮寄" in way)
        if values["deliver_count"]:
            count = re.sub(r"\s*份\s*$", "", values["deliver_count"])
            text = re.sub(r"份数\s*份", f"份数 {count} 份", text)
        if values["deliver_date"]:
            text = re.sub(r"时间：.*$", f"时间：{_cn_date(values['deliver_date'])}", text)
        _set_paragraph_text(paragraphs[0], text)


def _apply_fees(root, values):
    amount = values["amount"]
    amount_upper = values["amount_upper"]
    if amount:
        for _, _, cells in _table_rows(root):
            for cell in cells:
                normalized = _normalize(_element_text(cell))
                if normalized.startswith("检验费用:") and "大写:" in normalized:
                    _set_cell_text(cell, f"检验费用：{amount}元    大写：{amount_upper}")
        for cell in _matching_cells(root, "大写："):
            _fill_inline_cell(cell, amount_upper)
        for cell in _matching_cells(root, "小写："):
            _fill_inline_cell(cell, f"{amount}元")

    payment = values["pay_status"]
    paid = values["paid"]
    other = values["other_payment"]
    for _, _, cells in _table_rows(root):
        for cell in cells:
            text = _element_text(cell)
            product_value_cell = text.startswith("交费情况") and ("□" in text or "其它" in text)
            engineering_value_cell = "委托时预交合同额" in text
            if not (product_value_cell or engineering_value_cell):
                continue
            paid_text = f" 已缴费{paid}元" if paid else ""
            other_text = f"；其它：{other}" if other else ""
            mark = "☑" if (payment and "委托" in payment) or paid else "□"
            prefix = "" if engineering_value_cell else "交费情况："
            _set_cell_text(cell, f"{prefix}{mark} 委托时交{paid_text}{other_text}")


def _fill_inline_cell(cell, value):
    paragraphs = _direct_paragraphs(cell)
    if paragraphs and _clean(value):
        _append_run(paragraphs[-1], value)


def _apply_product_category(root, values):
    category = values["category"]
    if not category:
        return
    for _, _, cells in _table_rows(root):
        for cell in cells:
            text = _element_text(cell)
            if "委托检验□" in text and "委托" in category:
                for paragraph in _direct_paragraphs(cell):
                    _transform_same_length(paragraph, lambda line: line.replace("委托检验□", "委托检验☑"))
            elif _normalize(text) == "其他:" and ("委托" not in category or "category_display" in values):
                _fill_inline_cell(cell, values.get("category_display", category))


def _apply_sample_registry(root, values):
    registry = None
    header_row = None
    for table, row, cells in _table_rows(root):
        labels = {_normalize(_element_text(cell)) for cell in cells}
        if "检验日期" in labels and "检验项目" in labels:
            registry = table
            header_row = row
            break
    if registry is None or header_row is None:
        return
    rows = registry.xpath("./w:tr", namespaces=NS)
    index = rows.index(header_row)
    if index + 1 >= len(rows):
        return
    cells = rows[index + 1].xpath("./w:tc", namespaces=NS)
    values_by_column = (
        _first(values["test_end"], values["test_start"]),
        values["test_project"],
        values["before_status"],
        values["after_status"],
        values["inspector"],
    )
    for cell, value in zip(cells, values_by_column, strict=False):
        _append_cell_value(cell, value)

    for _, row, cells in _table_rows(root):
        if registry not in row.iterancestors():
            continue
        normalized = [_normalize(_element_text(cell)) for cell in cells]
        if not any(text.startswith("领样人") for text in normalized):
            continue
        for cell in cells:
            text = _normalize(_element_text(cell))
            if text.startswith("领样人") and values["pickup_person"]:
                _fill_inline_cell(cell, values["pickup_person"])
            elif text.startswith("回库人") and values["return_person"]:
                _fill_inline_cell(cell, values["return_person"])
        date_cells = [cell for cell in cells if "年月日" in _normalize(_element_text(cell))]
        if date_cells and values["pickup_date"]:
            _set_cell_text(date_cells[0], _cn_date(values["pickup_date"]))
        if len(date_cells) > 1 and values["return_date"]:
            _set_cell_text(date_cells[1], _cn_date(values["return_date"]))


def _apply_values(root, kind, values):
    numbered_template = kind == "product" and _has_numbered_template_tokens(root)
    if numbered_template:
        _apply_numbered_template_fields(root, values)
    else:
        _apply_headers(root, kind, values)
    adjacent = {
        "委托单位": values["client"],
        "检验依据": values["basis"],
        "判定依据": values["judgment"],
        "检验项目": values["test_project"],
        "备    注": values["remark"],
        "试验室名称": values["laboratory"],
        "主  检  人": values["owner"],
        "参加试验人员": values["participants"],
        "报告编写人": values["writer"],
        "检 测 地 点": values["test_location"],
        "计划完成    日    期": values["plan_complete"],
        "报告批准\n日　　期": values["approval_date"],
        "项目负责人": values["owner"],
        "参加检验人员": values["participants"],
        "实际\n完成日期": values["approval_date"],
    }
    if kind == "engineering":
        adjacent.update({
            "项目名称": values["project_name"],
            "检验类别": values.get("category_display", values["category"]),
        })
    else:
        adjacent.update({
            "样品名称": values["sample_name"],
            "规格型号": values["spec"],
            "生产单位": values["manufacturer"],
            "生产日期\n/编号": values["production"],
            "送样日期": values["send_date"],
            "样品数量": values["quantity"],
            "商标": values["trademark"],
        })
        if "category_display" in values:
            adjacent["检验类别"] = values["category_display"]
    for label, value in adjacent.items():
        _fill_adjacent(root, label, value, blank_only=numbered_template)

    inline = {
        "委托人：": values["consignor"],
        "委托人电话：": values["consignor_phone"],
        "委托单位地址：": values["client_address"],
        "合同甲方：": values["contract_party_a"],
        "其他甲方（付款方）：": values["other_party_a"],
        "经手人：": values["handler"],
    }
    if not numbered_template:
        for label, value in inline.items():
            _fill_inline(root, label, value)

    _apply_contract_review(root, values)
    _apply_checkboxes(root, values)
    _apply_delivery(root, values)
    _apply_fees(root, values)
    if kind == "product":
        _apply_product_category(root, values)
        _apply_sample_registry(root, values)


def _fit_written_rows_to_template(root):
    """Fit populated rows without changing the template's pagination."""
    for row in root.xpath(".//w:tr", namespaces=NS):
        rendered = row.attrib.pop("data-rendered", None)
        heights = row.xpath("./w:trPr/w:trHeight", namespaces=NS)
        if rendered:
            for height in heights:
                height.set(W + "hRule", "exact")
        # The official product template leaves this repeated row unsized. WPS doubles
        # its automatic height after checkbox text is populated, shifting every
        # following form. 1050 twips retains all three populated lines without overflow.
        row_text = _normalize(_element_text(row))
        if not heights and "样品状态" in row_text and "样品处理" in row_text:
            properties = row.find(W + "trPr")
            if properties is None:
                properties = etree.Element(W + "trPr")
                row.insert(0, properties)
            height = etree.SubElement(properties, W + "trHeight")
            height.set(W + "val", "1050")
            height.set(W + "hRule", "exact")


def _render_package(path, kind, values):
    with ZipFile(path, "r") as source:
        infos = source.infolist()
        parts = {info.filename: source.read(info.filename) for info in infos}
    xml = parts.get("word/document.xml")
    if not xml:
        return None
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml, parser=parser)
    _apply_values(root, kind, values)
    # The official form already contains its complete pagination and table geometry.
    # Populate text in place and keep populated rows within the template geometry.
    _fit_written_rows_to_template(root)
    parts["word/document.xml"] = etree.tostring(
        root, encoding="UTF-8", xml_declaration=True, standalone=True,
    )
    output = BytesIO()
    with ZipFile(output, "w") as target:
        for info in infos:
            target.writestr(info, parts[info.filename])
    return output.getvalue()


def build_entrust_doc(entrust, report=None, template_kind=None, project_no="", language="CN"):
    """Return a populated DOCX while retaining every non-text template part."""
    kind = template_kind or _document_kind(entrust, report)
    if kind not in EXPECTED_PAGES:
        return None
    from . import docparser_field_only
    if docparser_field_only.applies_to_entrust(entrust):
        from .entrust_source_cache import render
        blob, _audit = render(
            entrust, report, kind, project_no, language,
        )
        return blob
    if kind.endswith('-extended'):
        raise ValueError('历史模板不支持扩展版，请使用新版原包委托单')
    path = _select_template(kind)
    if not path:
        return None
    from .contract_review_output import attach_legacy_signature
    blob = _render_package(path, kind, _business_values(entrust, report, project_no, language))
    return attach_legacy_signature(blob, report) if blob else blob


def business_form_pdf_pages(pdf):
    if not pdf:
        return 0
    try:
        import fitz
        with fitz.open(stream=pdf, filetype="pdf") as document:
            return document.page_count
    except Exception:
        return 0
