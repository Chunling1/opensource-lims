"""权限点目录 — 与前端 src/data/modules.ts 的模块/页面结构保持一致。

模块权限 = `${key}.view`；页面权限 = `${moduleKey}.${pageKey}.view`（dashboard 首页特殊用 dashboard.view）。
"""

MODULES = [
    ("bim_lab", "图纸识别与模拟", [("workbench", "图纸识别与模拟")]),
    ("dashboard", "首页", [("home", "首页", "dashboard.view")]),
    ("entrust", "委托管理", [
        ("registration", "委托登记"), ("sample_register", "样品登记"),
        ("contract_review", "合同评审"), ("query", "委托查询"),
        ("change", "委托更改"), ("void_approval", "作废审批"),
    ]),
    ("sample", "样品管理", [
        ("inbound", "样品入库"), ("outbound", "样品出库"), ("disposal", "样品处置"),
        ("flow_query", "样品流转查询"),
    ]),
    ("testing", "检测管理", [
        ("assignment", "检测任务分配"), ("sample_pickup", "检测样品领取"), ("task_query", "检测任务查询"),
        ("data_entry", "检测数据录入"), ("data_check", "检测数据校核"), ("data_change", "检测数据更改"),
        ("original_record_query", "电子原始记录查询"),
        ("original_record_review", "电子原始记录审核"),
        ("original_record_template", "电子原始记录模板"),
        ("completed_sample_handling", "检毕样品处理"),
    ]),
    ("report", "报告管理", [
        ("contract_review", "合同评审"),
        ("review", "报告审核"), ("approval", "报告批准"),
        ("print", "报告签发"), ("archive", "报告归档"), ("release", "报告发放"),
        ("query", "报告查询"), ("interim_report", "中间报告"), ("change_request", "报告更改申请"),
    ]),
    ("quality", "质量体系", [
        ("personnel_registration", "人员登记"), ("equipment_ledger", "设备台账"),
        ("equipment_ledger_department", "设备台账[科室]"), ("monthly_calibration_plan", "月检定计划"),
        ("supplier_evaluation", "供应商及评价"), ("reference_material", "标准物质登记"),
        ("consumables", "易耗品"), ("standard_library", "检测标准基础信息库"),
        ("standard_library_department", "检测标准基础信息库【科室】"), ("test_environment", "检测试验环境"),
        ("daily_affairs", "日常事务管理"), ("daily_affairs_approval", "日常事务审批"),
    ]),
    ("system", "系统管理", [
        ("approval_center", "审批中心"), ("runtime_parameters", "系统运行参数"), ("approval_settings", "审批设置"),
        ("project_workflow", "检测项目流程定义"), ("custom_project", "检测项目自定义"), ("sms_settings", "短信设置"),
        ("capability_management", "检测能力库"),
        ("integration_erp", "外部ERP接口设置"), ("report_template", "报告模板设置"),
        ("auto_collection", "自动采集设置"), ("org", "组织机构"), ("user", "用户管理"), ("logs", "日志查询"),
        ("ai_assistant", "AI 工作台"),
    ]),
    ("online_entrust", "网上委托", [("application", "委托办理"), ("query", "委托查询")]),
]

ACTION_PERMISSIONS = [
    ("online_entrust.application.process", "办理网上委托（受理及驳回）"),
    ("online_entrust.application.accept", "受理网上委托"),
    ("online_entrust.application.reject", "驳回网上委托"),
    ("entrust.register.complete", "完成委托登记"),
    ("entrust.register.undo", "撤销委托登记完成"),
    ("sample.register.complete", "完成样品登记"),
    ("sample.register.undo", "撤销样品登记完成"),
    ("sample.inbound.confirm", "样品入库确认"),
    ("sample.out_warehouse.sign", "样品出库领取签字"), ("sample.out_warehouse.return", "样品出库退回"),
    ("report.contract_review.pass", "合同评审通过"), ("report.contract_review.return", "合同评审退回"),
    ("report.review.pass", "报告审核通过"), ("report.review.return", "报告审核退回"),
    ("report.approval.pass", "报告批准通过"), ("report.approval.return", "报告批准退回"),
    ("report.print.pass", "报告签发确认"), ("report.print.return", "报告签发退回"),
    ("report.attachment.upload", "上传报告附件"), ("report.pdf.merge", "合并 PDF"),
    ("report.pdf.preview", "预览 PDF"), ("report.pdf.download", "下载 PDF"),
    ("report.sealed.download", "盖章报告下载（未发放状态）"),
    ("report.distribution.complete", "报告发放"),
    ("report.scope.review", "报告范围复核纠正"),
    ("report.review.undo", "撤销审核完成"),
    ("report.approval.undo", "撤销批准完成"),
    ("entrust.change.resubmit", "提交委托更改完成"),
    ("report.change.request", "批准后申请报告更改"), ("report.change.test_complete", "提交检测更改完成"),
    # R6 状态机补齐（2026-07-09 批次）
    ("report.contract_review.undo", "撤销合同评审"),
    ("report.print.undo", "撤销打印完成"),
    ("report.archive.pass", "报告归档"), ("report.archive.undo", "撤销归档"),
    ("sample.return_stock", "撤销领取（检测前）"), ("sample.dispose", "样品处置"),
    ("sample.register.void", "作废样品单"),
    ("quality.standard.create", "新增受控标准"),
    ("quality.standard.update", "修改受控标准"),
    ("quality.standard.delete", "移除受控标准"),
    ("quality.standard.authorize", "维护标准部门授权"),
    ("quality.standard.void", "作废或替代受控标准"),
    ("quality.master_standard.create", "新增标准主数据"),
    ("quality.master_standard.update", "修改标准主数据"),
    ("quality.master_standard.delete", "移除标准主数据"),
    ("quality.equipment.create", "新增设备台账"),
    ("quality.equipment.update", "修改设备台账"),
    ("quality.equipment.delete", "移除设备台账"),
    ("quality.equipment.batch_update", "批量修改设备台账"),
    ("quality.equipment.batch_delete", "批量删除设备台账"),
    ("quality.equipment.import", "导入设备台账"),
    ("quality.equipment.export", "导出设备台账"),
    ("quality.personnel.create", "新增人员档案"),
    ("quality.personnel.update", "修改人员档案"),
    ("quality.personnel.delete", "移除人员档案"),
    ("quality.personnel.sensitive.view", "查看人员敏感信息"),
    ("finance.pricing.execute", "确认计价"),
    ("finance.payment.register", "登记收款"),
    ("finance.payment.confirm", "确认或退回收款"),
    ("finance.invoice.issue", "登记发票"),
    ("finance.settlement.execute", "确认结算"),
    ("finance.refund.execute", "办理退款"),
    ("ai.voice.use", "使用 AI 语音录入"),
    ("workflow.date.override", "日期放行（已停用，日期不可颠倒）"),
    ("eln.record.session_revoke", "撤销电子原始记录录入会话"),
    ("eln.template.create", "新增电子原始记录模板"),
    ("eln.template.update", "修改电子原始记录模板"),
    ("eln.template.publish", "发布或撤回电子原始记录模板"),
]

# “完成”属于对应业务模块的基本办理能力，不再作为独立授权项展示。
# 保留旧 action code 仅用于兼容既有账号和审计记录。
MODULE_IMPLIED_ACTIONS = {
    "entrust.register.complete": ("entrust.registration.view",),
    "entrust.register.undo": ("entrust.registration.view",),
    "sample.register.complete": ("entrust.sample_register.view",),
    "sample.register.undo": ("entrust.sample_register.view",),
    "sample.register.void": ("entrust.sample_register.view",),
    "sample.inbound.confirm": ("sample.inbound.view",),
    "sample.out_warehouse.sign": ("sample.outbound.view",),
    "sample.out_warehouse.return": ("sample.outbound.view",),
    "sample.return_stock": ("sample.outbound.view", "sample.disposal.view", "testing.task_query.view"),
    "sample.dispose": ("sample.disposal.view", "testing.completed_sample_handling.view"),
    "report.contract_review.pass": ("entrust.contract_review.view", "report.contract_review.view"),
    "report.contract_review.return": ("entrust.contract_review.view", "report.contract_review.view"),
    "report.contract_review.undo": ("entrust.contract_review.view", "report.contract_review.view"),
    "report.report_check.undo": ("testing.data_entry.view",),
    "testing.data_entry.return": ("testing.data_entry.view",),
    "report.review.pass": ("report.review.view",),
    "report.review.return": ("report.review.view",),
    "report.review.undo": ("report.review.view",),
    "report.approval.pass": ("report.approval.view",),
    "report.approval.return": ("report.approval.view",),
    "report.approval.undo": ("report.approval.view",),
    "report.print.pass": ("report.print.view",),
    "report.print.return": ("report.print.view",),
    "report.print.undo": ("report.print.view",),
    "report.archive.pass": ("report.archive.view",),
    "report.archive.undo": ("report.archive.view",),
    "report.attachment.upload": (
        "testing.data_entry.view", "testing.data_change.view",
    ),
    "report.pdf.merge": ("testing.data_entry.view", "testing.data_change.view"),
    "report.pdf.preview": (
        "testing.data_entry.view", "report.review.view", "report.approval.view",
        "report.print.view", "report.archive.view", "report.release.view", "report.query.view", "report.change_request.view",
    ),
    "report.pdf.download": (
        "testing.data_entry.view", "report.review.view", "report.approval.view",
        "report.print.view", "report.archive.view", "report.release.view", "report.query.view", "report.change_request.view",
    ),
    "entrust.change.resubmit": ("entrust.change.view",),
    "report.change.request": ("report.change_request.view",),
    "report.change.test_complete": ("testing.data_change.view",),
    "quality.standard.create": ("quality.standard_library.view",),
    "quality.standard.update": ("quality.standard_library.view",),
    "quality.standard.delete": ("quality.standard_library.view",),
    "quality.standard.authorize": ("quality.standard_library.view",),
    "quality.standard.void": ("quality.standard_library.view",),
    "quality.master_standard.create": ("quality.standard_library.view",),
    "quality.master_standard.update": ("quality.standard_library.view",),
    "quality.master_standard.delete": ("quality.standard_library.view",),
    "quality.equipment.create": ("quality.equipment_ledger.view",),
    "quality.equipment.update": ("quality.equipment_ledger.view",),
    "quality.equipment.delete": ("quality.equipment_ledger.view",),
    "quality.equipment.batch_update": ("quality.equipment_ledger.view",),
    "quality.equipment.batch_delete": ("quality.equipment_ledger.view",),
    "quality.equipment.import": ("quality.equipment_ledger.view",),
    "quality.equipment.export": ("quality.equipment_ledger.view",),
    "quality.personnel.create": ("quality.personnel_registration.view",),
    "quality.personnel.update": ("quality.personnel_registration.view",),
    "quality.personnel.delete": ("quality.personnel_registration.view",),
    "quality.personnel.sensitive.view": ("quality.personnel_registration.view",),
    "finance.pricing.execute": ("finance.pricing.view",),
    "finance.payment.register": ("finance.payment_registration.view",),
    "finance.payment.confirm": ("finance.payment_confirmation.view",),
    "finance.invoice.issue": ("finance.invoice.view",),
    "finance.settlement.execute": ("finance.settlement.view",),
    "finance.refund.execute": ("finance.account_refund.view",),
    "eln.record.session_revoke": ("testing.original_record_query.view",),
    "eln.template.create": ("testing.original_record_template.view",),
    "eln.template.update": ("testing.original_record_template.view",),
    "eln.template.publish": ("testing.original_record_template.view",),
}


def assignable_action_permissions():
    return [
        (code, name)
        for code, name in ACTION_PERMISSIONS
        if code not in MODULE_IMPLIED_ACTIONS
    ]


def all_permission_catalog():
    """返回 [(code, name, ptype)]，覆盖所有模块权限和页面权限。"""
    rows = []
    seen = set()
    for mkey, mname, pages in MODULES:
        mcode = f"{mkey}.view"
        if mcode not in seen:
            rows.append((mcode, mname, "module"))
            seen.add(mcode)
        for page in pages:
            pkey, pname = page[0], page[1]
            pcode = page[2] if len(page) > 2 else f"{mkey}.{pkey}.view"
            if pcode not in seen:
                rows.append((pcode, pname, "page"))
                seen.add(pcode)
    return rows


def all_permission_codes():
    return [code for code, _, _ in all_permission_catalog()]


def all_action_codes():
    return [code for code, _ in ACTION_PERMISSIONS]
