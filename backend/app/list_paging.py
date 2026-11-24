"""SQL list selection, separate from page-only business-row hydration.

No persistent cache: permissions, dates and workflow changes are visible on the
next request. Expressions are allowlisted; no client field becomes SQL text.
"""
import json
from sqlalchemy import Text, String, text, and_, or_, case, cast, func, literal, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from .extensions import db
from .models import Report, Entrust, OperationAudit
from .list_projection import _source


class JsonText(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(JsonText, 'sqlite')
def _sqlite_json(element, compiler, **kw):
    return compiler.process(func.json_extract(*element.clauses), **kw)


@compiles(JsonText, 'mysql')
@compiles(JsonText, 'mariadb')
def _mysql_json(element, compiler, **kw):
    return compiler.process(func.nullif(func.json_unquote(func.json_extract(*element.clauses)), 'null'), **kw)


class JsonType(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(JsonType, 'sqlite')
def _sqlite_type(element, compiler, **kw):
    return compiler.process(func.json_type(*element.clauses), **kw)


@compiles(JsonType, 'mysql')
@compiles(JsonType, 'mariadb')
def _mysql_type(element, compiler, **kw):
    return compiler.process(func.lower(func.json_type(func.json_extract(*element.clauses))), **kw)


def json_true(column, path):
    kind = JsonType(_source(column), literal('$.'+path))
    return or_(kind == 'true', and_(kind == 'boolean', j(column,path) == 'true'))


def json_truthy(column, path):
    kind = JsonType(_source(column), literal('$.'+path))
    value = cast(j(column,path),Text)
    return func.coalesce(case((kind.in_(['text','string']), value != ''),
        (kind.in_(['integer','double','real']), cast(value, db.Float) != 0),
        (kind.in_(['object','array']), value.notin_(['{}','[]'])),
        else_=json_true(column,path)),False)


def j(column, path):
    return JsonText(_source(column), literal('$.' + path))


def first(*values):
    return func.coalesce(*(func.nullif(func.trim(cast(v, Text)), '') for v in values), '')


class DisplayText(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(DisplayText, 'sqlite')
def _sqlite_display(element, compiler, **kw):
    value = compiler.process(list(element.clauses)[0], **kw)
    return (f"CASE WHEN json_valid({value}) AND substr({value}, 1, 1) = '[' THEN "
            f"(SELECT group_concat(CAST(value AS TEXT), '、') FROM json_each({value}) WHERE type NOT IN ('null','object','array')) "
            f"ELSE {value} END")


@compiles(DisplayText, 'mysql')
@compiles(DisplayText, 'mariadb')
def _mysql_display(element, compiler, **kw):
    value = compiler.process(list(element.clauses)[0], **kw)
    return (f"CASE WHEN json_valid({value}) AND left({value}, 1) = '[' THEN "
            f"(SELECT group_concat(v ORDER BY pos SEPARATOR '、') FROM JSON_TABLE({value}, '$[*]' "
            "COLUMNS (pos FOR ORDINALITY, v TEXT PATH '$' NULL ON ERROR)) dt) "
            f"ELSE {value} END")


class SummaryValue(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(SummaryValue, 'sqlite')
def _sqlite_summary(element, compiler, **kw):
    source, *labels = [compiler.process(c, **kw) for c in element.clauses]
    return (f"(SELECT json_extract(f.value, '$[1]') FROM json_each({source}, '$.summary') s "
            f"JOIN json_each(s.value, '$.fields') f WHERE json_extract(f.value, '$[0]') IN ({','.join(labels)}) "
            "AND trim(coalesce(json_extract(f.value, '$[1]'), '')) <> '' ORDER BY s.key,f.key LIMIT 1)")


@compiles(SummaryValue, 'mysql')
@compiles(SummaryValue, 'mariadb')
def _mysql_summary(element, compiler, **kw):
    source, *labels = [compiler.process(c, **kw) for c in element.clauses]
    return (f"(SELECT sf.val FROM JSON_TABLE({source}, '$.summary[*].fields[*]' "
            "COLUMNS (pos FOR ORDINALITY, label VARCHAR(100) PATH '$[0]', val TEXT PATH '$[1]')) sf "
            f"WHERE sf.label IN ({','.join(labels)}) AND trim(coalesce(sf.val, '')) <> '' ORDER BY sf.pos LIMIT 1)")


def summary(*labels):
    return first(SummaryValue(_source(Report.detail), *(literal(label) for label in labels)))


def _date_expression(value):
    """Same day precision for ISO and legacy YYYY年M月D日 / slash dates."""
    text = func.trim(cast(value, Text))
    for old, new in [('年','-'),('月','-'),('日',''),('/','-'),('.','-')]:
        text = func.replace(text,old,new)
    rest = func.substr(text,6)
    split = func.instr(rest,'-')
    month = func.substr(rest,1,split-1)
    day = func.substr(rest,split+1,2)
    normalized = cast(func.substr(text,1,4),String) + literal('-') + cast(func.substr(literal('0') + cast(func.trim(month),String),-2),String) + literal('-') + cast(func.substr(literal('0') + cast(func.trim(day),String),-2),String)
    return case((text.op('REGEXP')(r'^\d{4}-\d{1,2}-\d{1,2}'),normalized),else_=text)


class DateText(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(DateText, 'sqlite')
def _sqlite_date(element, compiler, **kw):
    # Do not expand the snapshot/summary expression repeatedly: compound date
    # filters otherwise exceed SQLite's parser stack even for a small dataset.
    value = compiler.process(list(element.clauses)[0], **kw)
    expression = compiler.process(_date_expression(db.literal_column('date_value')), **kw)
    return f'(SELECT {expression} FROM (SELECT {value} AS date_value))'


@compiles(DateText, 'mysql')
@compiles(DateText, 'mariadb')
def _mysql_date(element, compiler, **kw):
    return compiler.process(_date_expression(list(element.clauses)[0]), **kw)


def date_text(value):
    return DateText(value)


class BusinessTimestamp(FunctionElement):
    type = Text()
    inherit_cache = True


@compiles(BusinessTimestamp,'sqlite')
def _sqlite_business_time(element,compiler,**kw):
    value=compiler.process(list(element.clauses)[0],**kw)
    return f"strftime('%Y-%m-%d %H:%M:%S', {value}, '+8 hours')"


@compiles(BusinessTimestamp,'mysql')
@compiles(BusinessTimestamp,'mariadb')
def _mysql_business_time(element,compiler,**kw):
    value=compiler.process(list(element.clauses)[0],**kw)
    return f"DATE_FORMAT(DATE_ADD({value}, INTERVAL 8 HOUR), '%%Y-%%m-%%d %%H:%%i:%%s')"


def scheme_fields():
    value=summary('检测方案')
    normalized=func.replace(func.replace(value,'（','('),'）',')')
    opening=func.instr(normalized,'(')
    valid=normalized.op('REGEXP')(r'^.*[(] *[A-Za-z0-9._-]+ *[)] *$')
    code=case((valid,func.trim(func.substr(normalized,opening+1,func.char_length(func.trim(normalized))-opening-1))),else_='')
    name=case((valid,func.trim(func.substr(normalized,1,opening-1))),else_=value)
    return first(j(Report.detail,'rawSample.schemeCode'),code), first(j(Report.detail,'rawSample.schemeName'),j(Report.detail,'rawSample.testPlan'),name)


def audit_value(kind, identity, actions, column='created_at'):
    a = OperationAudit
    return select(getattr(a, column)).where(a.object_type == kind, a.object_id == identity,
        a.success.is_(True), a.action.in_(actions)).order_by(a.id.desc()).limit(1).correlate_except(a).scalar_subquery()


def edited_at(model, kind, identity):
    value = select(func.max(OperationAudit.created_at)).where(
        OperationAudit.object_type == kind, OperationAudit.object_id == identity,
        OperationAudit.success.is_(True)).correlate_except(OperationAudit).scalar_subquery()
    return value if model is Report else func.coalesce(value, model.created_at)


def join_edit_times(query, model, kind, identity, fields):
    """Aggregate audit timestamps once before sorting the authorized list.

    A correlated MAX for every candidate repeatedly scans the audit table on
    production MySQL. The grouped relation preserves the same timestamp and
    keeps report JSON projection confined to the selected page.
    """
    edits = select(OperationAudit.object_id.label('object_id'),
                   func.max(OperationAudit.created_at).label('edited_at')).where(
        OperationAudit.object_type == kind,
        OperationAudit.success.is_(True)).group_by(OperationAudit.object_id).subquery()
    query = query.outerjoin(edits, edits.c.object_id == identity)
    fields['editedAt'] = edits.c.edited_at if model is Report else func.coalesce(edits.c.edited_at, model.created_at)
    return query


def started(*, logistics=False, audit=audit_value):
    marker = j(Report.detail, 'dataEntryStarted')
    saved = j(Report.detail, 'checkInput')
    fallback = and_(saved.is_not(None), json_truthy(Report.detail,'checkInput'))
    # All presentations follow the same audit-aware legacy rule.
    pickup = audit('report', Report.report_no, ['sample.out_warehouse.sign'], 'id')
    save = audit('report', Report.report_no, ['report.data_entry.save'], 'id')
    fallback = case((pickup.is_not(None), func.coalesce(save > pickup, False)), else_=fallback)
    return case((marker.is_not(None), json_truthy(Report.detail,'dataEntryStarted')), else_=fallback)


def released():
    version = func.coalesce(Report.approved_document_version_id, Report.current_document_version_id)
    return and_(Report.status == '已发放', Report.archive_state == '归档完成',
        json_true(Report.detail,'reportDelivery.released'),
        json_truthy(Report.detail,'reportDelivery.sealedFlowId'), json_truthy(Report.detail,'reportDelivery.versionId'),
        JsonType(_source(Report.detail),literal('$.reportDelivery.versionId')).in_(['integer','real','double','true','boolean']),
        j(Report.detail, 'reportDelivery.versionId') == version)


def issuance_label():
    from flask import current_app
    from .models import ReportEsignFlow, ReportEsignSigner
    f, s = ReportEsignFlow, ReportEsignSigner
    latest = select(f.id).where(f.report_id == Report.id,
        f.report_document_version_id == func.coalesce(Report.approved_document_version_id, Report.current_document_version_id),
        f.id >= int(current_app.config.get('ESIGN_PROVIDER_FLOW_MIN_ID', 0))).order_by(
            f.attempt_no.desc(), f.id.desc()).limit(1).correlate(Report).scalar_subquery()
    included = j(f.positioning_json, 'organizationSeal.included')
    has_seal = case((JsonType(_source(f.positioning_json),literal('$.organizationSeal.included')).is_not(None), json_true(f.positioning_json,'organizationSeal.included')),
        else_=and_(JsonType(_source(f.positioning_json),literal('$.positions.cover')).is_not(None), JsonType(_source(f.positioning_json),literal('$.positions.date')).is_not(None)))
    any_signer = select(s.id).where(s.flow_id == f.id).exists()
    unsigned = select(s.id).where(s.flow_id == f.id, or_(s.status.is_(None), s.status != 'signed')).exists()
    label = case((f.status.in_(['cancelled','cancelling','rejected','expired','superseded']), '报告签发中'),
        (and_(f.status.in_(['completed','verified']), has_seal, func.coalesce(f.signed_file_id,0)!=0, func.coalesce(f.signed_sha256, '') != ''), '报告已盖章，归档中，未发放'),
        (and_(j(f.positioning_json, 'flowKind') == 'organization_seal', json_truthy(f.positioning_json,'sourceFlowId')), '报告盖章中'),
        (and_(any_signer, ~unsigned), '报告盖章中'), else_='报告签发中')
    return func.coalesce(select(label).where(f.id == latest).correlate(Report).scalar_subquery(), '报告签发中')


def data_status(*, logistics=False, audit=audit_value):
    from .status_machine import _REPORT_STAGE
    return case((or_(Report.voided.is_(True), Report.sample_reg_state == '已作废'), '样品单已作废'),
        (and_(Report.status == '待合同评审', Report.sample_reg_state == '登记中'), '样品登记中'),
        (and_(Report.status == '检测录入中', Report.sample_status == '已领取', ~started(logistics=logistics, audit=audit)), '样品出库领取完成'),
        (Report.status == '待校核', case((Report.sample_status == '待入库', '样品入库中（历史数据）'),
            (Report.sample_status == '已入库', '样品出库领取中（历史数据）'), else_='报告审核中')),
        (Report.status.in_(['待发放','已发放']), case((released(), '报告发放完成'),
            (Report.archive_state == '归档完成', '报告已归档，发放中'), else_='报告已盖章，归档中，未发放')),
        (Report.status == '待打印', issuance_label()),
        *[(Report.status == key, value) for key, value in _REPORT_STAGE.items()], else_=Report.status)


def report_fields(presentation='report', *, logistics=False, audit=audit_value, correction=None):
    r, e = Report, Entrust
    raw = lambda key: j(r.detail, 'rawSample.' + key)
    snap = lambda key: j(r.detail, 'entrustSnapshot.' + key)
    from .admin_corrections.source import SourceCorrection
    override=lambda key: j(correction,key) if correction is not None else select(j(SourceCorrection.fields,key)).where(SourceCorrection.kind=='sample-snapshot',
        SourceCorrection.source_key==cast(r.id,String)).correlate(r).scalar_subquery()
    def info(key):
        saved = case((JsonType(_source(r.detail),literal('$.entrustSnapshot.info.'+key)).is_not(None),
                      func.coalesce(snap('info.'+key),'')),else_=j(e.info,key))
        return case((e.id.is_not(None),func.coalesce(override(key),saved)),else_='')
    # An explicit top-level null retains the original column; nested null clears.
    def effective(key,column,alias=None):
        fallback=case((JsonType(_source(r.detail),literal('$.entrustSnapshot.info.client')).is_not(None),info('client')),else_=first(info('client'),column)) if key=='client' else first(info(alias or key),column)
        value=case((JsonType(_source(r.detail),literal('$.entrustSnapshot.'+key)).is_not(None),func.coalesce(snap(key),column)),
                   else_=fallback)
        return case((e.id.is_not(None),value),else_='')
    project_type = func.coalesce(override('projectType'), e.project_type)
    handler = effective('owner', e.owner, 'handler')
    department = effective('department', e.department, 'handleDept')
    sample_project = effective('projectName', e.project_name)
    sample_client = effective('client', e.client)

    scheme_code, scheme_name = scheme_fields()
    sample_type = first(j(r.detail, 'reportCategory'), raw('reportCategory'), literal('普通'))
    fields = {name: getattr(r, attr) for name, attr in {
        'reportNo':'report_no','sampleNo':'sample_no','project':'project','client':'client','owner':'owner',
        'department':'department','entrustNo':'entrust_no','version':'version','deadline':'deadline',
        'status':'status','sampleStatus':'sample_status','sampleRegState':'sample_reg_state','archiveState':'archive_state',
    }.items()}
    main=first(r.main_report_no,j(r.detail,'mainReportNo'),j(r.detail,'derivedFrom'),raw('baseReportNo'))
    tail=func.substr(r.report_no,func.instr(r.report_no,'-')+1)
    main_tail=func.substr(main,func.instr(main,'-')+1)
    suffix=func.substr(tail,func.length(main_tail)+1)
    fields['sampleStatus']=first(r.sample_status,literal('待入库'))
    fields['sampleRegState']=first(r.sample_reg_state,literal('登记完成'))
    fields['entrustId']=e.id
    fields['sampleNo']=case((and_(main!='',main!=r.report_no,func.instr(main,'-')>0,
        func.instr(r.report_no,'-')>0,func.substr(tail,1,func.length(main_tail))==main_tail,
        or_(func.upper(suffix).in_(['BC','GZ','EN','(E)','（E）']),and_(func.substr(suffix,1,1)=='-',func.length(suffix)>1)),
        r.sample_no==tail),main_tail),else_=r.sample_no)
    fields.update(dataStatus=data_status(logistics=logistics, audit=audit), editedAt=edited_at(r,'report',r.report_no),
        reportCategory=sample_type, sampleType=sample_type, schemeCode=scheme_code, schemeName=scheme_name,
        schemeDisplay=case((and_(scheme_code!='',scheme_name!=''),cast(scheme_code,String)+literal(' · ')+cast(scheme_name,String)),else_=first(scheme_code,scheme_name)),
        testDepartment=first(raw('testDept'),summary('检测部门','检测科室'),r.department),
        sampleOrProjectName=first(raw('sampleName'),summary('样品/工程名称','样品名称'),r.project_name),
        projectName=first(r.project_name,sample_project,raw('sampleName'),summary('样品/工程名称','样品名称')),
        sampleRegisteredAt=first(j(r.detail,'sampleRegisteredAt'),raw('registeredAt'),raw('sampleArrivalDate')),
        entrustDate=first(override('entrustDate'),j(e.info,'entrustDate'),func.substr(cast(e.created_at,Text),1,10),summary('委托日期')),
        handler=first(handler,r.owner), registrar=first(raw('registrar'),j(r.detail,'sampleRegistrar'),r.owner),
        consignor=info('consignor'),consignorPhone=info('consignorPhone'),clientAddress=first(info('clientAddr'),info('clientAddress')),
        erpProjectNo=first(override('contractNo'),e.contract_no,info('erpProjectNo'),info('projectCode')),
        erpProjectType=first(override('erpType'),j(e.info,'erpType'),override('projectType'),e.project_type), amount=first(raw('stdPrice'),snap('amount'),e.amount),
        testCategory=first(raw('testCategory'),project_type), reportFormat=first(raw('reportFormat'),raw('reportType')),
        sendDate=first(raw('sendDate'),summary('送样日期')),samplingTime=first(raw('sampleTime'),summary('抽样时间')),
        samplingUnit=first(raw('sampleUnit'),summary('抽样单位')),sampler=first(raw('sampler'),summary('抽样人')),
        reportTitle=first(raw('centerPrefix'),j(r.detail,'centerPrefix'),case((r.report_no.op('REGEXP')('^[A-Za-z]+-'),func.upper(func.substr(r.report_no,1,func.instr(r.report_no,'-')-1))),else_='')),sealRequirement=first(raw('seal'),summary('盖章要求')),
        testItems=first(DisplayText(raw('projectList')),DisplayText(raw('projects')),raw('project'),r.project),
        inboundDate=first(j(r.detail,'workflowDates.sampleInboundAt'),j(r.detail,'mobileSampleFlow.inbound.operatedAt')),
        outboundDate=j(r.sample_pickup,'outTime'),
        collectionPerson=j(r.sample_pickup,'receiverName'),customerRequirement=first(j(r.detail,'mobileSampleFlow.return.disposalMethod'),raw('sampleHandle'),summary('样品处理方式')),
        problemSource=j(r.detail,'returnInfo.source'),problemSubmitter=j(r.detail,'returnInfo.by'),problemSubmittedAt=j(r.detail,'returnInfo.date'),problemDescription=j(r.detail,'returnInfo.note'),
        processingResult=case((r.status=='委托更改中','问题处理中'),(j(r.detail,'returnInfo.source').is_not(None),'问题已处理'),else_=''),
        approvalResult=case((r.voided.is_(True),'已作废'),else_='未作废'),
        flowStatus=case(*[(r.sample_status==key,value) for key,value in {'已处置':'样品已处置','已领取':'样品已领取','已出库':'样品已出库','已入库':'样品已入库'}.items()],else_=r.sample_status))
    from .applications.report_lifecycle.query_details import STAGES
    stage_keys = tuple(STAGES) if presentation == 'report' else {
        'entry': ('dataSaved', 'dataCompleted'),
        'registration-sample': ('contractReviewed',),
    }.get(presentation, ())
    for key in stage_keys:
        kind, actions = STAGES[key]
        identity = r.entrust_no if kind=='entrust' else r.report_no
        fields[key+'By']=first(audit(kind,identity,actions,'user_name'),audit(kind,identity,actions,'account'))
        fields[key+'At']=BusinessTimestamp(audit(kind,identity,actions))
    for key,source in {'specification':'spec','manufacturer':'manufacturer','productionDate':'produceDate','sampleQuantity':'sampleAmount','productCode':'factoryNo','sampleAppearance':'appearance','testingLocation':'testLocation','assessmentStandard':'standardJudge','paymentMethod':'payWay','samplingLocation':'samplingLocation'}.items():
        fields[key]=raw(source)
    fields.update(testBasis=first(j(r.detail,'checkInput.standard'),raw('testBasis'),summary('检测依据','执行标准')),
        testStartDate=j(r.detail,'checkInput.testStartDate'),testEndDate=j(r.detail,'checkInput.testDate'),
        testResult=first(j(r.detail,'checkInput.result'),j(r.detail,'checkInput.conclusion'),summary('检测结果','结论')),
        sampleInboundDate=fields['inboundDate'],sampleOutboundDate=j(r.sample_pickup,'outTime'),samplePickupDate=first(j(r.sample_pickup,'pickupTime'),j(r.detail,'workflowDates.samplePickupAt')),
        sampleReceiver=case((json_truthy(r.sample_pickup,'signed'),j(r.sample_pickup,'receiverName')),else_=''))
    if presentation == 'report':
        for key in ('sampleInboundDate','sampleOutboundDate','samplePickupDate'):
            fields[key] = date_text(fields[key])
    for key in (('sampleRegisteredAt',) if presentation!='report' else ()) + ('entrustDate','sendDate','samplingTime'):
        fields[key]=date_text(fields[key])
    aliases={'code':'sampleNo','reportCode':'reportNo','commissionCode':'entrustNo','customer':'client','name':'testItems',
        'parameters':'testItems','dataEntryPerson':'owner','requestedTestDate':'deadline','commissionDate':'entrustDate',
        'testPlan':'schemeName','testPlanName':'schemeName','collectionDate':'samplePickupDate',
        'contact':'consignor','phone':'consignorPhone','customerAddress':'clientAddress','engineeringName':'projectName',
        'commissionOwner':'handler'}
    if presentation=='entry': aliases['commissionDate']='sampleRegisteredAt'
    if presentation != 'report': aliases['name']='sampleOrProjectName'
    if presentation=='registration-sample': aliases['owner']='registrar'
    if presentation in {'inbound','outbound','disposal','flow'}: aliases['owner']='registrar'
    if presentation in {'entry','flow','inbound','outbound','disposal','cancel','change','task'}: aliases['projectName']='schemeName'
    fields.update({key:fields[source] for key,source in aliases.items()})
    if presentation in {'entry','flow','inbound','outbound','disposal','cancel','change','task'}:
        fields['requestedTestDate'] = case((r.deadline.op('REGEXP')('^[0-9]{4}-[0-9]{2}-[0-9]{2}'),r.deadline),else_='')
    fields['outboundPerson']=first(j(r.sample_pickup,'managerName'),j(r.sample_pickup,'managerId'))
    fields.update(reviewer=j(r.detail,'contractReview.reviewer'),
        handlerDepartment=first(department,info('handleDepartment'),info('handlerDepartment'),r.department),
        registrarDepartment=first(raw('registrarDepartment'),j(r.detail,'sampleRegistrarDepartment'),info('handleDept'),e.department),
        standardPrice=fields['amount'],discountPrice=literal(''),actualPrice=literal(''),attachmentCount=literal(''),
        resultStatus=literal(''),disposalDate=literal(''))
    fields['inboundPerson']=first(audit('report',r.report_no,['sample.inbound.confirm','sample.mobile.inbound.confirm'],'user_name'),
        audit('report',r.report_no,['sample.inbound.confirm','sample.mobile.inbound.confirm'],'account'),
        j(r.detail,'mobileSampleFlow.inbound.operatorName'),j(r.detail,'mobileSampleFlow.inbound.operatorAccount'))
    fields['erpContractNo']=literal('')
    fields['contractCode']=fields['erpContractNo']
    fields['client']=fields['customer']=first(r.client,sample_client)
    result_status=first(j(r.detail,'checkInput.resultStatus'))
    fields['resultStatus']=case((result_status=='判定合格','合格'),(result_status=='判定不合格','不合格'),else_=result_status)
    fields['conclusion']=fields['resultStatus']
    for key,stage,workflow in [('checkDate','reportChecked','checkDate'),('auditDate','reportReviewed','auditDate'),
                              ('approvalDate','reportApproved','approvalDate'),('printDate','reportIssued','reportDate'),
                              ('archiveDate','reportArchived','archiveDate'),('distributionDate','reportReleased','distributionDate')]:
        fields[key]=first(j(r.detail,'workflowDates.'+workflow),fields.get(stage+'At',literal('')))
    fields['disposalDate']=BusinessTimestamp(audit('report',r.report_no,['sample.dispose']))
    fields['voidedAt']=BusinessTimestamp(audit('report',r.report_no,['sample.register.void']))
    method=first(raw('deliverWay'))
    fields['collectionMethod']=case((method.in_(['领取','自取']),'自取'),(method=='邮寄','邮寄'),(method!='','其他'),else_='')
    fields['releaseStatus']=case((released(),'已发放'),else_='未发放')
    fields['archiveStatus']=case((r.archive_state=='归档完成','已归档'),else_='待归档')
    fields['issueStatus']=case((r.status.in_(['待发放','已发放','已归档']),'已签发'),else_='未签发')
    fields['date']=fields['commissionDate']
    for key in ('assignedBy','assignedDate','inspector','tester1','tester2',
                'notes','mailingAddress','projectAddress','restockPerson','restockDate','retentionTime',
                'disposalResult','disposalPerson','customerSignature','applicant','applicationReason',
                'appliedAt','approver','rejectionReason','approvedAt','contract','projects',
                'projectRegistrationCode','projectTradingCode','erpContract'):
        fields[key]=literal('')
    if presentation not in {'report','entry'}:
        fields['sampleType']=case(*[(sample_type==k,v) for k,v in {'普通':'原始样品','英文':'英文报告样品','分项':'分项/阶段性报告样品','补充':'补充报告'}.items()],else_=sample_type)
    return fields


REPORT_ALL_SEARCH_KEYS=('sampleNo','entrustNo','reportNo','handler','registrar','sampleOrProjectName','testItems','schemeName','client','erpProjectType')
ENTRUST_ALL_SEARCH_KEYS=('entrustNo','handler','client','name','erpProjectType')

def all_search_keys(body, fields):
    if body.get('view') == 'change_request':
        return ['reportNo', 'client', 'project']
    keys=list(ENTRUST_ALL_SEARCH_KEYS if 'id' in fields else REPORT_ALL_SEARCH_KEYS)
    # Report query renders code + name; other sample surfaces render schemeName.
    if 'id' not in fields and body.get('presentation')=='report':keys[keys.index('schemeName')]='schemeDisplay'
    return [key for key in keys if key in fields]

def requested_field_keys(body,fields):
    """Only materialize expressions used by this request, keeping values intact."""
    keys={body.get('sort') or 'editedAt','editedAt'}
    term=str(body.get('contains') or body.get('keyword') or body.get('code') or '').strip()
    if term:
        key='code' if body.get('code') else body.get('searchField') or 'all'
        keys.update(all_search_keys(body,fields) if key=='all' else [key])
    for key in ('dataStatus','sampleType','requirement','source','result','conclusion','collectionMethod','releaseStatus','archiveStatus','issueStatus'):
        if body.get(key):keys.add({'requirement':'customerRequirement','source':'problemSource','result':'approvalResult' if body.get('presentation')=='cancel' else 'processingResult','conclusion':'resultStatus'}.get(key,key))
    if body.get('status'):keys.add('flowStatus' if body.get('presentation')=='flow' else 'disposalStatus' if body.get('presentation')=='disposal' else 'dataStatus')
    if body.get('checkStatus'):keys.add('status')
    keys.update(k for k,v in (body.get('fields') or {}).items() if v)
    if any(body.get(k) for k in ('from','to','commissionFrom','commissionTo')):keys.add('problemSubmittedAt' if body.get('presentation')=='change' else body.get('dateField') or 'commissionDate')
    if body.get('dates'):keys.update(('inboundDate','outboundDate','collectionDate','disposalDate'))
    if body.get('plans'):keys.update(('schemeCode','department','testDepartment'))
    if body.get('ids'):keys.add('id' if 'id' in fields else 'reportNo')
    if 'id' in fields:keys.add('id')
    return keys

def apply_filters(query, body, fields):
    def field(key):
        if key not in fields:
            raise ValueError('列表查询字段无效：' + str(key))
        return func.coalesce(cast(fields[key],Text),'')
    if body.get('startDate') or body.get('endDate'):
        raise ValueError('分页查询请指定日期字段并使用 from/to 条件')
    term=str(body.get('contains') or body.get('keyword') or body.get('code') or '').strip()
    if term:
        key='code' if body.get('code') else body.get('searchField') or 'all'
        if key != 'all': candidates=[field(key)]
        else:
            keys = all_search_keys(body, fields)
            candidates=[field(k) for k in dict.fromkeys(keys) if k in fields]
        query=query.filter(or_(*(func.lower(c).contains(term.lower(),autoescape=True) for c in candidates)))
    for key in ('dataStatus','sampleType','requirement','source','result','conclusion','collectionMethod','releaseStatus','archiveStatus','issueStatus'):
        if body.get(key):
            name={'requirement':'customerRequirement','source':'problemSource','result':'approvalResult' if body.get('presentation')=='cancel' else 'processingResult','conclusion':'resultStatus'}.get(key,key)
            query=query.filter(field(name)==str(body[key]))
    if body.get('checkStatus'):
        view=body.get('view')
        expected={'review':('未审核','已审核','待审核','待批准'),'approval':('未批准','已批准','待批准','待打印')}.get(view)
        if not expected or body['checkStatus'] not in expected[:2]:raise ValueError('报告操作状态无效')
        query=query.filter(field('status')==expected[2 if body['checkStatus']==expected[0] else 3])
    if body.get('status'):
        key='flowStatus' if body.get('presentation')=='flow' else 'disposalStatus' if body.get('presentation')=='disposal' else 'dataStatus'
        query=query.filter(field(key)==str(body['status']))
    for key,value in (body.get('fields') or {}).items():
        if value: query=query.filter(func.lower(field(key)).contains(str(value).lower(),autoescape=True))
    ranges=[('problemSubmittedAt' if body.get('presentation')=='change' else body.get('dateField') or 'commissionDate',body.get('from') or body.get('commissionFrom'),body.get('to') or body.get('commissionTo'))]
    for key,value in (body.get('dates') or {}).items():
        if body.get('presentation')!='flow':continue
        if key not in {'inbound','outbound','collection','disposal'}:raise ValueError('样品流转日期字段无效')
        ranges.append(({'inbound':'inboundDate','outbound':'outboundDate','collection':'collectionDate','disposal':'disposalDate'}[key],value.get('from'),value.get('to')))
    for key,value in (body.get('workflowDates') or {}).items():
        if key not in {'testStartDate','testEndDate','checkDate','auditDate','approvalDate','reportDate','preparationDate'}:
            raise ValueError('流程日期字段无效')
        if value.get('enabled'):
            fields['workflow:'+key]=j(Report.detail,'workflowDates.'+key)
            ranges.append(('workflow:'+key,value.get('from'),value.get('to')))
    for key,start,end in ranges:
        if start: query=query.filter(func.substr(field(key),1,10)>=str(start))
        if end: query=query.filter(and_(field(key)!='',func.substr(field(key),1,10)<=str(end)))
    plans=body.get('plans') or {}
    def plan(value):
        department,code=json.loads(value)
        return and_(fields['schemeCode']==code,or_(fields['department']==department,fields['testDepartment']==department) if department else literal(True))
    choices=[plan(v) for v in plans.get('planIds',[])]+[or_(fields['department']==v,fields['testDepartment']==v) for v in plans.get('groupIds',[])]
    if choices: query=query.filter(or_(*choices),~or_(*(plan(v) for v in plans.get('excludedPlanIds',[]))) if plans.get('excludedPlanIds') else literal(True))
    if 'commissionIds' in body:
        query=query.filter(Entrust.id.in_([int(v) for v in body['commissionIds']]))
    if body.get('ids'): query=query.filter(fields['id' if 'id' in fields else 'reportNo'].in_(body['ids']))
    return query


class NaturalNumberKey(FunctionElement):
    """Natural ordering for identifiers without loading their full business rows."""
    type = Text()
    inherit_cache = True


@compiles(NaturalNumberKey,'sqlite')
def _sqlite_natural(element,compiler,**kw):
    value=compiler.process(list(element.clauses)[0],**kw)
    return ("(WITH RECURSIVE nk(rest, digits, result) AS ("
        f"SELECT coalesce({value},'') || ' ', '', '' UNION ALL "
        "SELECT substr(rest,2), CASE WHEN substr(rest,1,1) GLOB '[0-9]' THEN digits || substr(rest,1,1) ELSE '' END, "
        "result || CASE WHEN substr(rest,1,1) GLOB '[0-9]' THEN '' ELSE "
        "CASE WHEN digits='' THEN '' ELSE printf('%04d',length(ltrim(digits,'0'))) || ltrim(digits,'0') END || substr(rest,1,1) END "
        "FROM nk WHERE rest<>'' ) SELECT result FROM nk WHERE rest='' LIMIT 1)")


@compiles(NaturalNumberKey,'mysql')
@compiles(NaturalNumberKey,'mariadb')
def _mysql_natural(element,compiler,**kw):
    value=compiler.process(list(element.clauses)[0],**kw)
    return ("(WITH RECURSIVE nk(rest, digits, result) AS ("
        f"SELECT concat(coalesce({value},''),' '), CAST('' AS CHAR(255)), CAST('' AS CHAR(2048)) UNION ALL "
        "SELECT substr(rest,2), CASE WHEN substr(rest,1,1) REGEXP '[0-9]' THEN concat(digits,substr(rest,1,1)) ELSE '' END, "
        "concat(result, CASE WHEN substr(rest,1,1) REGEXP '[0-9]' THEN '' ELSE concat("
        "CASE WHEN digits='' THEN '' ELSE concat(lpad(length(trim(LEADING '0' FROM digits)),4,'0'),trim(LEADING '0' FROM digits)) END, substr(rest,1,1)) END) "
        "FROM nk WHERE rest<>'' ) SELECT result FROM nk WHERE rest='' LIMIT 1)")


def select_page(query, model, body, fields, *, allow_page_ids=True):
    from flask import current_app
    if allow_page_ids and current_app.config.get('LIST_PAGE_IDS', False):
        # Preserve the database's ordering/collation and the complete authorized
        # predicate, but keep large JSON projections out of the sorting query.
        from .list_query_prototype import select_ids
        try:
            return select_ids(query, model, body, fields)
        except Exception as exc:
            db.session.rollback()
            current_app.logger.warning('list page ids fallback: %s', type(exc).__name__)
    if db.engine.dialect.name in {'mysql','mariadb'}:
        # GROUP_CONCAT defaults to 1024 bytes; a legal parameter list must not
        # silently stop matching after its first kilobyte. Bound by packet size.
        db.session.execute(text('SET SESSION group_concat_max_len = @@max_allowed_packet'))
    page=max(1,int(body.get('page') or 1)); size=max(1,min(200,int(body.get('pageSize') or 10)))
    total=query.order_by(None).with_entities(model.id).count()
    sort=body.get('sort') or 'editedAt'
    if sort not in fields: raise ValueError('列表排序字段无效：'+str(sort))
    expr=fields[sort]
    if sort in {'code','sampleNo','reportNo','reportCode','entrustNo','commissionCode','contractNo','erpProjectNo'}:
        expr=NaturalNumberKey(expr)
    descending=(not body.get('sort')) or body.get('direction','asc')=='desc'
    ordered=query.order_by(None).order_by(expr.desc() if descending else expr.asc(),fields['editedAt'].desc(),model.id.desc())
    return ordered.offset((page-1)*size).limit(size),{'total':total,'page':page,'pageSize':size}


class PageMeta(dict):
    """Public pagination keys plus explicit, non-serialized projection order."""
    def __init__(self, *, page_ids=None, **values):
        super().__init__(values)
        self.page_ids = page_ids


def query_path(body):
    """Request-only rollout: A2 is independent of the A rollout switch."""
    from flask import current_app
    term=str(body.get('contains') or body.get('keyword') or body.get('code') or '').strip()
    field='code' if body.get('code') else body.get('searchField') or 'all'
    if current_app.config.get('LIST_QUERY_A2',False) and term and field=='all':
        return 'a2'
    # The numbered-field probe is slower with audit winner joins; use the
    # measured legacy path. This choice depends only on request parameters.
    if term and field in {'reportNo','reportCode'}:
        return 'legacy'
    # Measured active-only handling scopes are cheaper on the legacy path.
    if body.get('rowProjection')=='active' and body.get('view') in {'release', 'review', 'print', 'approval', 'data_change'}:
        return 'legacy'
    if current_app.config.get('LIST_QUERY_PROTOTYPE',False):
        return 'a'
    return 'legacy'


def report_page(query,user,view,body,*,samples=False):
    from flask import current_app
    path=query_path(body)
    if path=='legacy':
        return _report_page(query,user,view,body,samples=samples,allow_page_ids=False)
    try:
        return _report_page(query,user,view,body,samples=samples,prototype=True,a2=path=='a2')
    except Exception as exc:
        # Never log SQL, parameters, customer search text or exception messages.
        current_app.logger.warning('list query prototype fallback: %s', type(exc).__name__)
        db.session.rollback()
        return _report_page(query,user,view,body,samples=samples,allow_page_ids=False)


def load_report_page(query,user,view,body,*,samples=False):
    """Production callers consume page/order together, including safe hydration.

    Retrying starts a fresh read-only list scope so request-local primed reads
    cannot leak partial prototype state into the legacy attempt.
    """
    from flask import current_app
    from .list_projection import list_reports
    from .list_reads import reuse_list_reads
    @reuse_list_reads
    def attempt(path, *, allow_page_ids=True):
        page,meta=_report_page(query,user,view,body,samples=samples,prototype=path!='legacy',a2=path=='a2',allow_page_ids=allow_page_ids)
        return list_reports(page,page_ids=getattr(meta,'page_ids',None)),meta
    path=query_path(body)
    if path=='legacy':return attempt(path)
    try:
        return attempt(path)
    except Exception as exc:
        current_app.logger.warning('list query prototype fallback: %s',type(exc).__name__)
        db.session.rollback()
        return attempt('legacy', allow_page_ids=False)


def _report_page(query,user,view,body,*,samples=False,prototype=False,a2=False,allow_page_ids=True):
    """Apply global predicates before LIMIT; callers hydrate only returned page."""
    from .list_page_access import report_access,sample_access
    from .admin_corrections import can_correct_business_data
    from .report_groups import apply_report_group
    query = apply_report_group(query, body.get('reportGroup'))
    r=Report
    kind=body.get('presentation') or ('registration-sample' if samples else 'report')
    requested_projection=body.get('rowProjection') or None
    if requested_projection not in (None,'active','recall'):
        raise ValueError('列表办理范围无效')
    if view=='contract_review' or requested_projection=='active':
        query=query.filter(func.coalesce(r.voided,False).is_(False))
    if samples:
        if not body.get('includeVoided'): query=query.filter(func.coalesce(r.voided,False).is_(False))
        if view=='register' and not can_correct_business_data(user):
            query=query.filter(r.status=='待合同评审',first(r.sample_reg_state,literal('登记完成')).in_(['登记中','登记完成']),func.coalesce(r.voided,False).is_(False))
        if view=='inbound': query=query.filter(or_(and_(r.status=='待样品入库',r.sample_status=='待入库'),and_(r.status=='待样品领取',r.sample_status=='已入库')))
        if view=='outbound':
            from .organization_privileges import has_full_platform_authority
            can_recall=has_full_platform_authority(user) or 'sample.return_stock' in user.action_codes()
            query=query.filter(or_(and_(r.status=='待样品领取',r.sample_status=='已入库'),
                and_(r.status=='检测录入中',r.sample_status=='已领取',~started(logistics=True),literal(can_recall))))
        query=sample_access(query,user,view)
        if requested_projection:
            active={'register':and_(r.status=='待合同评审',first(r.sample_reg_state,literal('登记完成')).in_(['登记中','登记完成'])),
                    'inbound':and_(r.status=='待样品入库',r.sample_status=='待入库'),
                    'outbound':and_(r.status=='待样品领取',r.sample_status=='已入库')}.get(view)
            if active is not None:query=query.filter(active if requested_projection=='active' else ~active)
    else:
        from .list_page_access import report_candidates
        query=report_candidates(query,user,view,row_projection=requested_projection,presentation=kind)
    if view == 'change_request' and body.get('correctionStatus'):
        from .models import ReportCorrectionRequest
        correction = ReportCorrectionRequest
        status = case((correction.status == 'pending_approval', 'pending_director'),
                      (correction.status == 'rejected', 'none'), else_=correction.status)
        latest = select(status).where(correction.main_report_no == r.report_no).order_by(
            correction.id.desc()).limit(1).correlate(r).scalar_subquery()
        query = query.filter(func.coalesce(latest, 'none') == body['correctionStatus'])
    from flask import current_app
    if prototype:
        from .list_query_prototype import joined_sources
        # Inspect only expressions this request uses. The ten-field search has
        # no stage operators; unused By/At fields must not force their joins.
        from sqlalchemy.sql import visitors
        from sqlalchemy.sql.elements import BindParameter
        requested=report_fields(kind,logistics=samples)
        needed=requested_field_keys(body,requested)
        actions=set()
        for key in needed:
            for node in visitors.iterate(requested.get(key,literal(''))):
                if isinstance(node,BindParameter):
                    for value in node.value if isinstance(node.value,(list,tuple)) else [node.value]:
                        if isinstance(value,str):actions.add(value)
        query, audit, correction, edit_time = joined_sources(query,required_actions=actions)
        fields=report_fields(kind, logistics=samples, audit=audit, correction=correction)
    else:
        fields=report_fields(kind, logistics=samples)
    if body.get('adapter') == 'platform':
        # The alternate frontend maps a different vocabulary from the primary
        # list presentation. Keep its filters aligned with the displayed row.
        fields.update(name=fields['sampleOrProjectName'], owner=fields['registrar'],
            projectName=fields['schemeDisplay'], testPlan=fields['schemeCode'],
            category=fields['testCategory'], contract=literal(''), site=literal(''),
            createdAt=date_text(fields['sampleRegisteredAt']), inspector=r.owner,
            commissionDate=fields['entrustDate'], version=literal(0))
        sample_type=fields['reportCategory']
        fields['sampleType']=case(*[(sample_type==k,v) for k,v in {'普通':'原始样品','英文':'英文报告样品','分项':'分项/阶段性报告样品','补充':'补充报告'}.items()],else_=sample_type)
        fields['checkStatus']=case((r.status==('待批准' if view=='review' else '待打印'),'已'+('审核' if view=='review' else '批准')),else_='未'+('审核' if view=='review' else '批准')) if view in {'review','approval'} else literal('')
        body=dict(body)
        status=body.get('status')
        mapped_status=case((r.voided.is_(True),'voided'),(r.sample_reg_state=='登记中','pending'),else_='completed')
        if status in {'voided','pending','completed'}:
            query=query.filter(mapped_status==status);body['status']=''
        elif view in {'review','approval'} and status in {'报告审核完成','报告批准完成','报告审核中','报告批准中'}:
            query=query.filter(fields['checkStatus']==('已' if status.endswith('完成') else '未')+('审核' if view=='review' else '批准'));body['status']=''
        if body.get('dataStatus') in {'委托登记中','完成登记'}:
            query=query.filter(r.sample_reg_state==('登记中' if body['dataStatus']=='委托登记中' else '登记完成'))
            if body['dataStatus']=='完成登记':query=query.filter(r.status=='待合同评审')
            body['dataStatus']=''
    early=['待合同评审','待样品入库','待样品领取','检测录入中','退回待重传','委托更改中','检测更改中']
    disposable=and_(r.sample_status.in_(['已领取','已出库']),r.status.notin_(early))
    fields['disposalStatus']=case((r.sample_status=='已处置','样品已处置'),(disposable,'样品待处置'),else_='')
    if kind=='disposal': query=query.filter(or_(r.sample_status=='已处置',disposable))
    if kind=='task': query=query.filter(r.sample_status.in_(['已领取','已出库']))
    if kind=='change': query=query.filter(r.status=='委托更改中')
    query=query.outerjoin(Entrust,Entrust.entrust_no==r.entrust_no)
    if prototype:
        fields['editedAt'] = edit_time
    else:
        query=join_edit_times(query,r,'report',r.report_no,fields)
    if prototype and a2:
        from .list_query_values import materialize_fields
        # This predicate names Entrust directly. Apply it while that relation
        # is still in scope, before moving the authorized query into a derived
        # table; otherwise SQLAlchemy would add an unrelated outer Entrust.
        if 'commissionIds' in body:
            query=query.filter(Entrust.id.in_([int(v) for v in body['commissionIds']]))
            body=dict(body)
            body.pop('commissionIds')
        query, fields = materialize_fields(query, {k:v for k,v in fields.items() if k in requested_field_keys(body,fields)})
    query=apply_filters(query,body,fields)
    if prototype:
        from .list_query_prototype import select_ids
        return select_ids(query,r,body,fields)
    return select_page(query,r,body,fields,allow_page_ids=allow_page_ids)


def load_entrust_page(query, body):
    """Apply the same opt-in/fallback boundary to the independent entrust path."""
    from flask import current_app
    from .list_projection import list_entrusts
    from .list_reads import reuse_list_reads
    @reuse_list_reads
    def attempt(path, *, allow_page_ids=True):
        page,meta=_entrust_page(query,body,prototype=path!='legacy',a2=path=='a2',allow_page_ids=allow_page_ids)
        return list_entrusts(page,page_ids=getattr(meta,'page_ids',None)),meta
    path=query_path(body)
    if path=='legacy':return attempt(path)
    try:
        return attempt(path)
    except Exception as exc:
        current_app.logger.warning('list query prototype fallback: %s',type(exc).__name__)
        db.session.rollback()
        return attempt('legacy', allow_page_ids=False)


def entrust_page(query,body):
    # Existing direct callers keep the legacy query contract.
    return _entrust_page(query,body)


def _entrust_page(query,body,*,prototype=False,a2=False,allow_page_ids=True):
    e=Entrust
    info=lambda key:j(e.info,key)
    fields={'id':e.id,'code':e.entrust_no,'entrustNo':e.entrust_no,'name':e.project_name,
        'projectName':e.project_name,'customer':e.client,'client':e.client,'contract':first(info('erpContractNo')),
        'contractNo':e.contract_no,'owner':first(info('handler'),e.owner),'handler':first(info('handler'),e.owner),
        'department':e.department,'handlerDepartment':first(info('handleDept'),info('handleDepartment'),info('handlerDepartment'),e.department),
        'commissionDate':first(info('entrustDate'),func.substr(cast(e.created_at,Text),1,10)),
        'erpProjectNo':first(info('erpProjectNo'),info('projectCode'),info('projectRecordNo'),info('projectTradeCode')),
        'erpProjectType':first(info('erpType'),info('erpProjectType'),e.project_type),
        'contractPartyA':first(info('contractPartyA'),e.client),'otherPartyA':info('otherPartyA'),
        'contact':info('consignor'),'consignor':info('consignor'),'clientAddress':first(info('clientAddr'),info('clientAddress')),
        'amount':e.amount,'receivableAmount':e.amount,'remark':first(info('remark'),info('note')),
        'dataStatus':case((e.status=='委托中','委托登记中'),(e.status=='委托完成','委托登记完成'),else_=e.status),
        'status':e.status,'editedAt':edited_at(e,'entrust',e.entrust_no)}
    body=dict(body)
    if body.get('status'):
        query=query.filter(e.status=={'已完成':'委托完成','未完成':'委托中'}.get(body['status'],body['status']))
        body['status']=''
    fields.update(projectRegistrationCode=literal(''),projectTradingCode=literal(''))
    if body.get('adapter') == 'platform':
        fields.update(contract=e.contract_no,owner=e.owner,erpContract=fields['erpProjectNo'],
            contractParty=fields['contractPartyA'],payer=fields['otherPartyA'],customerAddress=fields['clientAddress'],
            departmentId=e.department,handlingDepartmentId=fields['handlerDepartment'],notes=info('remark'),
            phone=info('consignorPhone'),createdAt=func.substr(cast(e.created_at,Text),1,10),version=literal(0),
            projectRegistrationCode=info('projectRecordNo'),projectTradingCode=info('projectTradeCode'))
    fields['commissionDate']=date_text(fields['commissionDate'])
    if prototype:
        candidates=query.with_entities(e.entrust_no.label('identity')).order_by(None).distinct().subquery('list_entrust_candidates')
        edits=select(OperationAudit.object_id.label('identity'),func.max(OperationAudit.created_at).label('edited_at')).join(
            candidates, candidates.c.identity==OperationAudit.object_id).where(
                OperationAudit.object_type=='entrust',OperationAudit.success.is_(True)).group_by(OperationAudit.object_id).subquery('list_entrust_edits')
        query=query.outerjoin(edits,edits.c.identity==e.entrust_no)
        fields['editedAt']=func.coalesce(edits.c.edited_at,e.created_at)
    else:
        query=join_edit_times(query,e,'entrust',e.entrust_no,fields)
    if a2:
        from .list_query_values import materialize_fields
        query,fields=materialize_fields(query,{k:v for k,v in fields.items() if k in requested_field_keys(body,fields)},model=e,json_column=e.info)
    query=apply_filters(query,body,fields)
    if prototype:
        from .list_query_prototype import select_ids
        return select_ids(query,e,body,fields)
    return select_page(query,e,body,fields,allow_page_ids=allow_page_ids)
