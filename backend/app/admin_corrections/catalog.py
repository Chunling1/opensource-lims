"""Editable business records; storage identities and immutable artifacts stay owned."""
from .. import models as m

# Keys are an explicit allowlist, never caller-supplied table/model names.
CATALOG = {
    "entrusts": ("委托", m.Entrust, ("entrust_no", "project_name", "client")),
    "reports": ("样品与检测数据", m.Report, ("report_no", "sample_no", "project", "client")),
    "standard-library": ("标准库", m.StdLibraryItem, ("code", "name", "controlled_no")),
    "standards": ("标准基础资料", m.Standard, ("code", "name")),
    "capabilities": ("检测能力与参数", m.CapabilityEntry, ("item_name", "standard_code", "object_name")),
    "equipment": ("仪器设备", m.EquipmentItem, ("archive_no", "name")),
    "personnel": ("人员资料", m.Personnel, ("code", "name", "dept")),
    "projects": ("检测项目配置", m.Project, ("code", "name")),
    "departments": ("部门资料", m.Department, ("code", "name")),
    "finance": ("费用资料", m.FinanceBill, ("bill_no", "project_name", "client")),
}

LABELS = {
    "agreement_no": "合同编号", "entrust_no": "委托编号", "report_no": "报告编号",
    "sample_no": "样品编号", "contract_no": "关联合同编号", "project_name": "项目名称",
    "project_type": "项目类型", "project_code": "项目编号", "client": "委托单位",
    "erp_type": "外部ERP项目类型", "contract_type": "合同类型", "category": "类别",
    "amount": "金额", "payment": "付款方式", "department": "所属部门", "owner": "负责人",
    "status": "状态", "info": "登记信息", "detail": "样品、检测与流程信息",
    "project": "检测项目", "template": "模板", "version": "版本", "sign": "签字信息",
    "deadline": "截止日期", "out_of_scope": "超范围", "out_of_scope_note": "超范围说明",
    "sample_status": "样品状态", "sample_pickup": "样品领取信息",
    "sample_reg_state": "样品登记状态", "archive_state": "归档状态", "voided": "已作废",
    "code": "编号", "name": "名称", "auth_kind": "资质类别", "expired": "已过期",
    "controlled_no": "受控号", "location": "存放地点", "issue_count": "发放数量",
    "issuer": "发放人", "use_depts": "使用部门", "impl_date": "实施日期",
    "void_date": "作废日期", "delay_days": "延期天数", "replace_no": "替代标准号",
    "is_english": "英文标准", "is_onsite_standard": "现场标准", "remark": "备注",
    "capability_type": "资质类型", "certificate_no": "证书编号", "site": "场所",
    "section_path": "分类", "object_seq": "对象序号", "object_name": "检测对象",
    "item_seq": "参数序号", "item_name": "检测参数", "standard_code": "标准编号",
    "standard_name": "标准名称", "method_clause": "方法条款", "restriction": "限制范围",
    "effective_date": "生效日期", "expires_on": "到期日期", "mapping_status": "匹配状态",
    "active": "启用", "archive_no": "档案号", "spec": "规格型号", "factory_no": "出厂编号",
    "maker": "生产厂家", "cal_unit": "校准单位", "dept": "部门", "place": "地点",
    "last_cal_date": "上次校准日期", "period": "周期", "plan_cal_date": "计划校准日期",
    "actual_cal_date": "实际校准日期", "range": "量程", "accuracy": "精度", "keeper": "保管人",
    "buy_date": "购置日期", "buy_price": "购置金额", "use_record": "使用记录",
    "gender": "性别", "education": "学历", "title": "职称", "major": "专业",
    "grad_time": "毕业时间", "position": "岗位", "approval_position": "审批岗位",
    "test_scope": "检测范围", "check_scope": "检查范围", "birth_date": "出生日期",
    "id_no": "身份证号", "mobile": "手机号", "ethnicity": "民族", "native_place": "籍贯",
    "political": "政治面貌", "school": "毕业院校", "work_start_time": "参加工作日期",
    "join_time": "入职日期", "assigned_depts": "可工作部门", "permissions": "流程权限",
    "description": "说明", "enabled": "启用", "sort": "排序", "sort_order": "排序",
    "bill_no": "费用单号", "note": "说明", "total_amount": "总金额",
    "received_amount": "已收金额", "invoice_no": "发票号", "invoice_type": "发票类型",
    "invoice_date": "开票日期", "settlement_no": "结算编号", "settlement_date": "结算日期",
    "refund_date": "退款日期", "display_code": "项目显示编号", "number_code": "编号代码",
    "source_department": "来源部门", "code_aliases": "历史编号", "workflow_config": "流程配置",
    "amount_due": "应收金额", "pending_payment": "待确认金额", "amount_received": "已收金额",
    "amount_invoiced": "已开票金额", "amount_refunded": "已退金额", "payment_method": "付款方式",
    "payment_reference": "收款凭证", "payment_date": "收款日期", "meas_range": "测量范围",
    "manual": "说明书", "cert": "证书", "accept_doc": "验收资料", "equip_type": "设备类型",
    "cal_person": "校准人员", "valid_until": "有效期至",
}

# Link identifiers are not free text: changing them without coordinated relation
# updates would orphan attachments, finance receipts and externally signed files.
OWNED = {
    "id", "agreement_no", "entrust_no", "report_no", "sample_no", "contract_no",
    "bill_no", "main_report_no", "current_document_version_id", "approved_document_version_id",
    "edit_version", "created_at", "updated_at", "created_by", "updated_by", "deleted_at",
    "source_file", "source_page", "source_row", "source_sha256", "raw_cells",
    "stamped", "report_kind", "report_suffix", "version", "last_command_key", "source_key",
}


def columns(model):
    from .numbering import NUMBER_FIELDS
    return [c for c in model.__table__.columns
            if not c.primary_key and not c.foreign_keys
            and (c.name not in OWNED or c.name in NUMBER_FIELDS.get(model, ()))]


def field_type(column):
    from sqlalchemy import Boolean, Integer, Numeric, DateTime, Date
    if isinstance(column.type, m.JSONText):
        return "object"
    if isinstance(column.type, Boolean):
        return "boolean"
    if isinstance(column.type, (Integer, Numeric)):
        return "number"
    if isinstance(column.type, DateTime):
        return "datetime"
    if isinstance(column.type, Date):
        return "date"
    return "text"
