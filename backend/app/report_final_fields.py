"""Workflow-backed document fields. No provider requests or implicit approvals."""


def approval_date(report):
    if not getattr(report, 'id', None):
        return ''
    from .report_issue_dates import approval_event
    from .workflow_dates import business_date
    event = approval_event(report)
    return business_date(event.created_at).isoformat() if event else ''


def review_signature(report):
    from .contract_review_output import review_image
    return review_image(report)


def ensure_approved_date_version(report, version, actor=None):
    """Render the real approval date before dispatch, never rewrite signed bytes.

    Existing provider attempts (including unknown upload outcomes) retain their
    exact version. They must use the normal correction workflow if incomplete.
    """
    from .extensions import db
    from .models import Report, ReportEsignFlow
    from .report_documents import materialize_approved_report_pdf
    Report.query.filter_by(id=report.id).with_for_update().first()
    date = approval_date(report)
    if not date:
        raise ValueError('报告尚无批准记录，不能生成带签发日期的批准版本')
    from . import docparser_field_only
    if docparser_field_only.applies_to(report):
        from .report_version_consistency import require_reviewed_document
        require_reviewed_document(report, version, record_legacy=True, actor=actor)
        from .report_issue_dates import finalize_approved_version
        return finalize_approved_version(report, version, actor)
    if version and (version.snapshot or {}).get('approvalDate') == date:
        return version
    if version:
        flows = ReportEsignFlow.query.filter_by(report_id=report.id,
            report_document_version_id=version.id).all()
        if any(f.provider_file_id or f.provider_flow_id or f.dispatched_at
               or f.status not in ('ready', 'binding_required', 'failed') for f in flows):
            return version
    from .report_documents import composition_options
    if composition_options(report).get('preserveUploadedReport') is True:
        return _preserved_approval_version(report, version, date, actor)
    result = materialize_approved_report_pdf(report, actor)
    if (result.snapshot or {}).get('approvalDate') != date:
        raise ValueError('批准日期与生成版本不一致，已停止准备签署')
    # Do not commit here: caller owns the flow/version transaction.
    return result


def _preserved_approval_version(report, version, date, actor):
    """Freeze workflow metadata in a NEW version, reusing the exact approved PDF.

    approvalDate describes the workflow event, never a claim about PDF text.
    Neither the source snapshot nor any uploaded/signed file is rewritten.
    """
    import copy
    import hashlib
    from sqlalchemy import func
    from .extensions import db
    from .models import ReportDocumentVersion
    from .functions.stored_files import read_file_bytes
    from .report_documents import snapshot_hash
    from .audit import add_operation_audit
    if (not version or version.report_no != report.report_no or version.output_kind != 'official'
            or version.id != report.approved_document_version_id):
        raise ValueError('保留模式缺少当前批准的正式 PDF 版本，请核实批准文件')
    raw = read_file_bytes(version.pdf_file) if version.pdf_file_id else version.pdf_data
    if not raw or not raw.lstrip().startswith(b'%PDF') or hashlib.sha256(raw).hexdigest() != version.sha256:
        raise ValueError('保留报告 PDF 缺失或哈希不一致，未改变批准版本')
    snapshot = copy.deepcopy(version.snapshot or {})
    snapshot['approvalDate'] = date
    snapshot['approvalDateBinding'] = {
        'kind': 'workflow-metadata-only', 'sourceVersionId': version.id,
        'sourceApprovalDate': (version.snapshot or {}).get('approvalDate', ''),
        'sourcePdfSha256': version.sha256, 'pdfContentUnchanged': True,
    }
    number = (db.session.query(func.max(ReportDocumentVersion.version_no)).filter_by(
        report_no=report.report_no, output_kind='official').scalar() or 0) + 1
    result = ReportDocumentVersion(
        report_no=report.report_no, output_kind='official', version_no=number, status='approved',
        profile_code=version.profile_code, composition=copy.deepcopy(version.composition),
        snapshot=snapshot, source_hash=snapshot_hash(snapshot), sha256=version.sha256,
        pdf_file_id=version.pdf_file_id, pdf_data=version.pdf_data,
        docx_file_id=version.docx_file_id, docx_data=version.docx_data,
        warnings=[*(version.warnings or []), '流程批准日期已关联；保留文件及封面原样，正文日期未自动改写'],
        created_by=getattr(actor, 'account', None) or 'esign-system')
    db.session.add(result)
    db.session.flush()
    report.current_document_version_id = report.approved_document_version_id = result.id
    report.version = f'V{number}'
    add_operation_audit('report.esign.preserved_approval.bind', 'report', report.report_no,
        category='report', before={'approvedVersionId': version.id},
        after={'approvedVersionId': result.id, 'approvalDate': date, 'pdfSha256': result.sha256},
        actor=actor, message='新版本关联流程批准日期，保留完整报告文件字节不变')
    return result


def redact_public_project_name(report_no, facts):
    """Redact only the public response for explicitly configured exact numbers."""
    from flask import current_app
    if facts and report_no in current_app.config.get('REPORT_QUERY_REDACT_PROJECT_NAMES', ()):
        return {**facts, 'projectName': '/'}
    return facts


def public_facts(snapshot, version_no, issue_date=''):
    """Public display whitelist, projected only from the supplied version snapshot."""
    from .report_date_display import report_date
    def mapping(value):
        return value if isinstance(value, dict) else {}
    def text(value):
        if value is None or isinstance(value, bool):
            return ''
        if isinstance(value, (str, int, float)):
            return str(value).strip()
        if isinstance(value, (list, tuple)):
            return '；'.join(filter(None, (text(item) for item in value)))
        return ''
    def first(*values):
        return next((text(value) for value in values if text(value)), '')
    snap = mapping(snapshot)
    report = mapping(snap.get('report'))
    detail = mapping(report.get('detail'))
    raw = mapping(detail.get('rawSample'))
    check = mapping(detail.get('checkInput'))
    entrust = mapping(detail.get('entrustSnapshot'))
    info = mapping(entrust.get('info'))
    template = mapping(snap.get('template'))
    fields = mapping(template.get('fieldValues'))
    institution = mapping(template.get('institution'))
    profile = mapping(template.get('profile'))
    sections = []
    for key in ('summary', 'sections'):
        if isinstance(detail.get(key), list):
            sections.extend(detail[key])
    def field(*labels, section_title=None):
        for section in sections:
            if not isinstance(section, dict) or (section_title and section.get('title') != section_title):
                continue
            rows = section.get('fields')
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    label, value = row[:2]
                elif isinstance(row, dict):
                    label, value = row.get('label'), row.get('value')
                else:
                    continue
                if label in labels and text(value):
                    return text(value)
        return ''
    def frozen(key, *fallback):
        # A deliberately blank rendered field remains blank.
        return text(fields[key]) if key in fields else first(*fallback)
    report_type = first(raw.get('reportType'), field('报告类型'))
    calibration = profile.get('kind') == 'calibration' or '校准' in report_type or 'calibrat' in report_type.lower()
    centers = {
        'LAB': '示例检测机构', 'NCSA': '国家空调设备质量检验检测中心',
        'NCAS': '国家空调设备质量检验检测中心', 
        
        
    }
    center = first(profile.get('center'), raw.get('centerPrefix'), detail.get('centerPrefix'),
                   text(report.get('reportNo')).partition('-')[0]).upper()
    title = first(institution.get('centerName'), institution.get('companyName'),
                  raw.get('centerName'), detail.get('centerName'), centers.get(center))
    quantity = frozen('Quantity', raw.get('sampleAmount'), raw.get('sampleQuantity'),
                      raw.get('quantity'), field('样品数量', '数量'))
    unit = first(raw.get('unit'), raw.get('quantityUnit'), field('数量单位', '单位'))
    if 'Quantity' not in fields and quantity and unit and not quantity.endswith(unit):
        quantity += unit
    project = first(raw.get('projectName'), field('工程名称', section_title='委托信息'),
                    info.get('projectName'), entrust.get('projectName'))
    if profile.get('kind') == 'engineering':
        project = frozen('EngineeringName', project)
    intervals = check.get('testIntervals')
    if not isinstance(intervals, list):
        intervals = [{'start': check.get('testStartDate'), 'end': check.get('testDate')}]
    dates = []
    for interval in intervals:
        if isinstance(interval, dict):
            start, end = report_date(text(interval.get('start'))), report_date(text(interval.get('end')))
            if start or end:
                dates.append(start if start == end else '至'.join(filter(None, (start, end))))
    test_date = (frozen('CalibrationDate', raw.get('calibrationDate'), field('校准日期', '校准时间'), check.get('calibrationTime'))
                 if calibration else frozen('TestDate', '；'.join(dates), raw.get('testDate'), field('检测日期', '试验时间区间')))
    issue = first(snap.get('approvalDate'), fields.get('ReportDate'), issue_date)
    return {
        'version': 'V' + str(version_no), 'reportType': report_type,
        'reportKind': 'calibration' if calibration else 'inspection',
        'reportTitle': title,
        'client': frozen('Client', report.get('client'), field('委托单位', '送检单位')),
        'projectName': project,
        'sampleName': frozen('SampleName', raw.get('sampleName'), raw.get('sampleOrProjectName'), field('样品名称', '计量器具名称', '样品/工程名称')),
        'model': frozen('Model', raw.get('spec'), raw.get('specification'), raw.get('model'), field('规格型号', '型号规格')),
        'quantity': quantity,
        'testItems': frozen('Items', raw.get('projectList'), raw.get('projects'), raw.get('project'), field('校准项目', '检测项目', '检验项目'), report.get('project')),
        'serialNo': frozen('Serial', raw.get('factoryNo'), field('出厂编号', '出厂序号')),
        'standard': frozen('Basis', check.get('standardDisplay'), raw.get('standard'), field('检测依据', '检测标准', '校准依据', '执行标准')),
        'testDate': report_date(test_date), 'issueDate': report_date(issue),
    }
