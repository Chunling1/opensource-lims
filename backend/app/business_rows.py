"""Canonical list rows shared by sample, review and entrust-query workbenches."""

import re
from datetime import date, datetime

from .platform.workflow import report_data_status


def clean(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (list, tuple, set)):
        return "、".join(filter(None, (clean(item) for item in value)))
    if isinstance(value, dict):
        return ""
    return str(value).strip()


def first(*values):
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def date_only(value):
    text = clean(value)
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if not match:
        return text
    year, month, day = (int(part) for part in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def summary_field(detail, *labels):
    wanted = set(labels)
    for section in (detail or {}).get("summary", []):
        for field in section.get("fields", []):
            if len(field) >= 2 and field[0] in wanted:
                value = clean(field[1])
                if value:
                    return value
    return ""


def recursive_text(value):
    if isinstance(value, dict):
        return " ".join(recursive_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(recursive_text(item) for item in value)
    return clean(value)


def row_contains(row, keyword):
    needle = clean(keyword).casefold()
    return not needle or needle in recursive_text(row).casefold()


def row_in_date_range(row, start_date="", end_date="", fields=()):
    start = clean(start_date)
    end = clean(end_date)
    if not start and not end:
        return True
    def date_values(value):
        if isinstance(value, dict):
            return [item for child in value.values() for item in date_values(child)]
        if isinstance(value, (list, tuple, set)):
            return [item for child in value for item in date_values(child)]
        text = clean(value)
        return [text[:10]] if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text) else []

    values = [clean(row.get(field)) for field in fields]
    values = [value[:10] for value in values if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", value)]
    values.extend(date_values(row))
    if not values:
        return False
    return any((not start or value >= start) and (not end or value <= end) for value in values)


def paginate_rows(rows, body):
    page = int(body.get("page") or 0)
    page_size = int(body.get("pageSize") or 0)
    total = len(rows)
    if page > 0 and page_size > 0:
        start = (page - 1) * page_size
        rows = rows[start:start + min(page_size, 200)]
    return {"rows": rows, "total": total, "page": page or 1, "pageSize": page_size or total}


def agreement_business_row(agreement):
    row = agreement.to_row()
    info = agreement.info or {}
    registered_at = first(info.get("regTime"), info.get("regDate"), agreement.created_at)
    row.update({
        "erpProjectNo": first(agreement.project_code, agreement.agreement_no),
        "erpProjectType": first(agreement.erp_type, agreement.category),
        "projectAuditTime": date_only(first(info.get("auditTime"), info.get("projectAuditTime"))),
        "businessDepartment": first(info.get("bizDept"), agreement.department),
        "projectOwner": first(info.get("projectOwner"), agreement.owner),
        "registrar": first(info.get("registrar"), agreement.owner),
        "testDepartment": first(info.get("testDept"), agreement.department),
        "registeredAt": date_only(registered_at),
        "remark": first(info.get("remark"), info.get("note")),
    })
    # Source-bound display correction only. Stored business records, signing files,
    # ownership and manually maintained agreements remain untouched.
    if info.get('fromErp') in ('1',1,True):
        _bridge_settings = lambda: None; find_erp_contract = lambda *_a, **_k: None
        if _bridge_settings() is not None:
            source=find_erp_contract(agreement.agreement_no)
            if source:
                row['erpType']=row['erpProjectType']=source.get('erpType') or '待核实（未提供类型）'
                row['businessDepartment']=source.get('bizDept') or '待补全部门名称'
                row['projectAuditTime']=source.get('auditTime') or '未提供审核日期'
                row['client']=source.get('client') or ''
                row['contractStartDate']=source.get('contractStartDate') or ''
                row['erpLogReceivedAt']=source.get('erpLogReceivedAt') or ''
                row['fieldStates']=source.get('fieldStates',{})
                states={'raw':'原文提供','supplemented':'核实补充','missing':'待补','conflict':'冲突','invalid':'待核实'}
                labels={'zjjt_customername_name':'客户','projectorg_name':'部门','auditdate':'审核时间','zjjt_projecttype':'类型','recordVersion':'版本'}
                summary='；'.join(labels.get(k,k)+'：'+states.get(v.get('state'),'待核实') for k,v in row['fieldStates'].items())
                row['info']=dict(info,bizDept=row['businessDepartment'],auditTime=source.get('auditTime') or '',sourceFieldSummary=summary,contractStartDate=source.get('contractStartDate') or '',erpLogReceivedAt=source.get('erpLogReceivedAt') or '',dateFieldStates=source.get('dateFieldStates',{}))
            else:
                # Do not resurrect the former default type/creation timestamp if
                # the verified receiver record is temporarily unavailable.
                row['erpType']=row['erpProjectType']='待核实（转发记录暂不可用）'
                row['businessDepartment']='待核实（转发记录暂不可用）'
                row['projectAuditTime']='待核实（转发记录暂不可用）'
                row['contractStartDate']=row['erpLogReceivedAt']=''
                row['info']=dict(info,bizDept=row['businessDepartment'],auditTime='',contractStartDate='',erpLogReceivedAt='')
    return row


def entrust_business_row(entrust):
    row = entrust.to_row()
    info = entrust.info or {}
    row.update({
        "erpProjectNo": first(
            info.get("erpProjectNo"), info.get("projectCode"),
            info.get("projectRecordNo"), info.get("projectTradeCode"),
        ),
        "erpProjectType": first(info.get("erpType"), info.get("erpProjectType"), entrust.project_type),
        "contractPartyA": first(info.get("contractPartyA"), entrust.client),
        "otherPartyA": clean(info.get("otherPartyA")),
        "entrustDate": date_only(first(info.get("entrustDate"), entrust.created_at)),
        "handler": first(info.get("handler"), entrust.owner),
        "handlerDepartment": first(info.get("handleDept"), info.get("handleDepartment"), info.get("handlerDepartment"), entrust.department),
        "consignor": clean(info.get("consignor")),
        "consignorPhone": clean(info.get("consignorPhone")),
        "clientAddress": first(info.get("clientAddr"), info.get("clientAddress")),
        "remark": first(info.get("remark"), info.get("note")),
    })
    return row


def report_business_row(report, entrust=None, *, issuance_label=None):
    from .list_reads import erp_contract_number
    detail = report.detail or {}
    raw = detail.get("rawSample") or {}
    review = detail.get("contractReview") or {}
    if entrust is not None:
        from .sample_entrust import sample_entrust_object
        entrust = sample_entrust_object(report, entrust)
    entrust_row = entrust_business_row(entrust) if entrust is not None else {}
    projects = raw.get("projectList") or raw.get("projects") or []
    project_text = first(projects, raw.get("project"), report.project)
    sample_name = first(raw.get("sampleName"), summary_field(detail, "样品/工程名称", "样品名称"), report.project_name)
    seal = first(raw.get("seal"), summary_field(detail, "盖章要求"))
    # “报告标题”在样品表单中实际保存为中心前缀（LAB/NCSA 等）。
    # 历史数据可能没有 rawSample.centerPrefix，此时从正式报告编号首段回填，
    # 不能再用样品名称兜底，否则列表会把普通业务字段误显示成报告标题。
    report_title = first(raw.get("centerPrefix"), detail.get("centerPrefix"))
    if not report_title:
        prefix_match = re.match(r"^([A-Za-z]+)-", clean(report.report_no))
        report_title = prefix_match.group(1).upper() if prefix_match else ""
    scheme_summary = summary_field(detail, "检测方案")
    scheme_name = first(raw.get("schemeName"), raw.get("testPlan"))
    scheme_code = clean(raw.get("schemeCode"))
    if scheme_summary:
        parsed_scheme = re.match(
            r"^(.*?)\s*[（(]\s*([A-Za-z0-9._-]+)\s*[）)]\s*$",
            scheme_summary,
        )
        if parsed_scheme:
            scheme_name = scheme_name or clean(parsed_scheme.group(1))
            scheme_code = scheme_code or clean(parsed_scheme.group(2))
        elif not scheme_name:
            scheme_name = scheme_summary
    scheme_display = " · ".join(part for part in (scheme_code, scheme_name) if part)
    test_department = first(
        raw.get("testDept"),
        summary_field(detail, "检测部门", "检测科室"),
        report.department,
    )
    row = report.to_row(issuance_label=issuance_label)
    row.update({
        "entrustId": entrust.id if entrust is not None else None,
        "erpProjectNo": first(entrust_row.get("contractNo"), entrust_row.get("erpProjectNo")),
        "erpProjectType": first(entrust_row.get("erpProjectType"), entrust_row.get("projectType")),
        "erpContractNo": erp_contract_number(report.report_no),
        "handler": first(entrust_row.get("handler"), report.owner),
        "handlerDepartment": first(entrust_row.get("handlerDepartment"), report.department),
        "registrar": first(raw.get("registrar"), detail.get("sampleRegistrar"), report.owner),
        "registrarDepartment": first(
            raw.get("registrarDepartment"),
            detail.get("sampleRegistrarDepartment"),
            entrust_row.get("handlerDepartment"),
        ),
        "sampleOrProjectName": sample_name,
        "projectName": first(report.project_name, entrust_row.get("projectName"), sample_name),
        "testItems": project_text,
        "testDepartment": test_department,
        "schemeName": scheme_name,
        "schemeCode": scheme_code,
        "schemeDisplay": scheme_display,
        "client": first(report.client, entrust_row.get("client")),
        "amount": first(raw.get("stdPrice"), entrust_row.get("amount")),
        "reportCategory": first(detail.get("reportCategory"), raw.get("reportCategory"), "普通"),
        "reportFormat": first(raw.get("reportFormat"), raw.get("reportType")),
        "testCategory": first(raw.get("testCategory"), entrust_row.get("projectType")),
        "sampleRegisteredAt": date_only(first(detail.get("sampleRegisteredAt"), raw.get("registeredAt"), raw.get("sampleArrivalDate"))),
        "sendDate": date_only(first(raw.get("sendDate"), summary_field(detail, "送样日期"))),
        "entrustDate": date_only(first(entrust_row.get("entrustDate"), summary_field(detail, "委托日期"))),
        "reportTitle": report_title,
        "sealRequirement": seal,
        "samplingUnit": first(raw.get("sampleUnit"), summary_field(detail, "抽样单位")),
        "sampler": first(raw.get("sampler"), summary_field(detail, "抽样人")),
        "samplingTime": date_only(first(raw.get("sampleTime"), summary_field(detail, "抽样时间"))),
        "consignor": clean(entrust_row.get("consignor")),
        "consignorPhone": clean(entrust_row.get("consignorPhone")),
        "clientAddress": clean(entrust_row.get("clientAddress")),
        "reviewer": clean(review.get("reviewer")),
        "reviewedAt": date_only(first(review.get("reviewedAt"), review.get("reviewTime"))),
        "dataStatus": report_data_status(
            report.status,
            report.sample_status,
            report.sample_reg_state,
            report.archive_state,
            report.voided,
            row.get("dataEntryStarted"),
            row.get("dataStatus") if report.status == "待打印" else None,
            row.get("distributionComplete", False),
        ),
    })
    return row
