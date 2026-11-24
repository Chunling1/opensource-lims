"""开源 LIMS 演示种子数据：1 个根机构 + 4 个模拟实验室部门，含主检/审核/批准角色权限与完整流程样例。"""
from datetime import date

# ---------- 部门（1 个根机构 + 4 个模拟实验室部门）----------
DEPARTMENTS = [
    ("ROOT", "开源示例检测实验室", None, "总部"),
    ("BIZ", "综合业务部", "ROOT", "总部"),
    ("CHEM", "理化检测室", "ROOT", "一号实验楼"),
    ("MECH", "力学性能室", "ROOT", "二号实验楼"),
    ("ENV", "环境可靠性室", "ROOT", "三号实验楼"),
]

DEPARTMENT_CODE_MERGES = {}
DEPARTMENT_NAME_MIGRATIONS = {}

# ---------- 角色权限集合 ----------
ACCEPT_PERMS = [
    "dashboard.view", "entrust.view", "entrust.registration.view",
    "entrust.sample_register.view", "entrust.contract_review.view", "entrust.query.view",
    "entrust.change.view", "entrust.void_approval.view", "report.view", "report.query.view",
]
ACCEPT_ACTIONS = ["report.contract_review.pass", "report.contract_review.return", "report.pdf.preview"]

SAMPLE_PERMS = [
    "dashboard.view", "sample.view", "sample.inbound.view", "sample.outbound.view",
    "sample.change.view", "sample.disposal.view", "sample.flow_query.view",
    "testing.view", "testing.task_query.view",
]
SAMPLE_ACTIONS = ["sample.inbound", "sample.outbound", "sample.dispose"]

TESTER_PERMS = [
    "dashboard.view", "sample.view", "sample.outbound.view", "sample.flow_query.view",
    "testing.view", "testing.assignment.view", "testing.sample_pickup.view",
    "testing.task_query.view", "testing.data_entry.view", "testing.data_check.view",
    "testing.data_change.view", "testing.completed_sample_handling.view",
    "report.view", "report.query.view", "quality.view", "quality.equipment_ledger.view",
    "quality.standard_library.view",
]
TESTER_ACTIONS = [
    "report.data_entry.complete", "report.attachment.upload",
    "report.pdf.merge", "report.pdf.preview",
]

REVIEWER_PERMS = [
    "dashboard.view", "entrust.view", "entrust.query.view",
    "sample.view", "sample.flow_query.view",
    "testing.view", "testing.task_query.view",
    "report.view", "report.review.view", "report.query.view",
    "quality.view", "quality.equipment_ledger.view", "quality.standard_library.view",
]
REVIEWER_ACTIONS = ["report.review.pass", "report.review.return", "report.pdf.preview", "report.pdf.download"]

APPROVER_PERMS = [
    "dashboard.view", "report.view", "report.approval.view", "report.query.view",
    "report.change_request.view",
]
APPROVER_ACTIONS = ["report.approval.pass", "report.approval.return", "report.pdf.preview", "report.pdf.download"]

ISSUER_PERMS = [
    "dashboard.view", "report.view", "report.print.view", "report.archive.view",
    "report.release.view", "report.query.view",
]
ISSUER_ACTIONS = [
    "report.print.pass", "report.print.return", "report.archive.pass",
    "report.release.pass", "report.pdf.preview", "report.pdf.download",
]

# ---------- 账号（4 个部门，每部门按岗位配置主检/审核/批准等权限）----------
ACCOUNTS = [
    # 综合业务部（4 人）
    {
        "account": "admin", "name": "系统管理员", "role_key": "admin", "role_name": "系统管理员",
        "home_path": "/inspection/dashboard", "dept": "ROOT",
        "scope_type": "all", "scope_desc": "不受数据范围限制",
        "permissions": "ALL", "actions": "ALL",
    },
    {
        "account": "biz_accept", "name": "林受理", "role_key": "acceptance", "role_name": "受理与评审员",
        "home_path": "/inspection/entrust/registration", "dept": "BIZ",
        "scope_type": "all", "scope_desc": "全实验室委托受理与合同评审",
        "permissions": ACCEPT_PERMS, "actions": ACCEPT_ACTIONS,
    },
    {
        "account": "biz_sample", "name": "周库管", "role_key": "sample_admin", "role_name": "样品管理员",
        "home_path": "/inspection/sample/inbound", "dept": "BIZ",
        "scope_type": "all", "scope_desc": "全实验室样品出入库与处置",
        "permissions": SAMPLE_PERMS, "actions": SAMPLE_ACTIONS,
    },
    {
        "account": "biz_issue", "name": "钱签发", "role_key": "printer", "role_name": "签发归档员",
        "home_path": "/inspection/report/print", "dept": "BIZ",
        "scope_type": "all", "scope_desc": "全实验室报告签发、归档与发放",
        "permissions": ISSUER_PERMS, "actions": ISSUER_ACTIONS,
    },
    # 理化检测室（3 人：主检 / 审核 / 批准）
    {
        "account": "chem_tester", "name": "张理化", "role_key": "tester", "role_name": "理化主检员",
        "home_path": "/inspection/testing/data_entry", "dept": "CHEM",
        "scope_type": "department", "scope_desc": "理化检测室检测任务与数据录入",
        "permissions": TESTER_PERMS, "actions": TESTER_ACTIONS,
    },
    {
        "account": "chem_reviewer", "name": "陈审核", "role_key": "reviewer", "role_name": "理化审核人",
        "home_path": "/inspection/report/review", "dept": "CHEM",
        "scope_type": "department", "scope_desc": "理化检测室报告审核",
        "permissions": REVIEWER_PERMS, "actions": REVIEWER_ACTIONS,
    },
    {
        "account": "chem_approver", "name": "赵批准", "role_key": "approver", "role_name": "理化批准人",
        "home_path": "/inspection/report/approval", "dept": "CHEM",
        "scope_type": "department", "scope_desc": "理化检测室报告批准",
        "permissions": APPROVER_PERMS, "actions": APPROVER_ACTIONS,
    },
    # 力学性能室（3 人：主检 / 审核 / 批准）
    {
        "account": "mech_tester", "name": "李力学", "role_key": "tester", "role_name": "力学主检员",
        "home_path": "/inspection/testing/data_entry", "dept": "MECH",
        "scope_type": "department", "scope_desc": "力学性能室检测任务与数据录入",
        "permissions": TESTER_PERMS, "actions": TESTER_ACTIONS,
    },
    {
        "account": "mech_reviewer", "name": "孙审核", "role_key": "reviewer", "role_name": "力学审核人",
        "home_path": "/inspection/report/review", "dept": "MECH",
        "scope_type": "department", "scope_desc": "力学性能室报告审核",
        "permissions": REVIEWER_PERMS, "actions": REVIEWER_ACTIONS,
    },
    {
        "account": "mech_approver", "name": "吴批准", "role_key": "approver", "role_name": "力学批准人",
        "home_path": "/inspection/report/approval", "dept": "MECH",
        "scope_type": "department", "scope_desc": "力学性能室报告批准",
        "permissions": APPROVER_PERMS, "actions": APPROVER_ACTIONS,
    },
    # 环境可靠性室（3 人：主检 / 审核 / 批准）
    {
        "account": "env_tester", "name": "王环境", "role_key": "tester", "role_name": "环境主检员",
        "home_path": "/inspection/testing/data_entry", "dept": "ENV",
        "scope_type": "department", "scope_desc": "环境可靠性室检测任务与数据录入",
        "permissions": TESTER_PERMS, "actions": TESTER_ACTIONS,
    },
    {
        "account": "env_reviewer", "name": "郑审核", "role_key": "reviewer", "role_name": "环境审核人",
        "home_path": "/inspection/report/review", "dept": "ENV",
        "scope_type": "department", "scope_desc": "环境可靠性室报告审核",
        "permissions": REVIEWER_PERMS, "actions": REVIEWER_ACTIONS,
    },
    {
        "account": "env_approver", "name": "冯批准", "role_key": "approver", "role_name": "环境批准人",
        "home_path": "/inspection/report/approval", "dept": "ENV",
        "scope_type": "department", "scope_desc": "环境可靠性室报告批准",
        "permissions": APPROVER_PERMS, "actions": APPROVER_ACTIONS,
    },
]


def _detail(entrust, sample, testing, record, checks, attachments, extra=None):
    data = {
        "summary": [
            {"title": "委托信息", "fields": entrust},
            {"title": "样品信息", "fields": sample},
            {"title": "实验信息", "fields": testing},
            {"title": "原始记录", "fields": record},
        ],
        "checks": checks,
        "attachments": attachments,
    }
    if extra:
        data.update(extra)
    return data


# ---------- 检测与报告样例数据（覆盖检测录入中 / 待审核 / 待批准 / 待打印 / 待发放）----------
REPORTS = [
    {
        "report_no": "RPT-2026-0001", "sample_no": "YP-2026-0001", "project": "室内空气甲醛检测",
        "project_name": "示范研发楼室内空气验收", "client": "示例科技有限公司", "template": "REPORT_GENERAL_CN",
        "version": "V1.0", "status": "检测录入中", "sign": "待主检签字", "deadline": "正常",
        "department": "理化检测室", "owner": "张理化",
        "detail": _detail(
            [["委托编号", "WT-2026-0001"], ["委托单位", "示例科技有限公司"], ["工程名称", "示范研发楼室内空气验收"], ["盖章要求", "CMA + CNAS"]],
            [["样品编号", "YP-2026-0001"], ["样品名称", "室内空气采样管"], ["规格型号", "3 点位 / 组"], ["流转状态", "已领取，检测录入中"]],
            [["检测项目", "室内空气甲醛检测"], ["检测日期", "2026-11-20"], ["主检人", "张理化"], ["执行标准", "GB/T 18883-2022"]],
            [["记录编号", "YJ-2026-0001"], ["记录条数", "3 条待提交"], ["采集方式", "人工录入"], ["校核状态", "录入中"]],
            [], [],
            extra={"checkInput": {"standard": "GB/T 18883-2022", "instrument": "分光光度计 UV-2600", "testDate": "2026-11-20", "conclusion": "符合标准要求"}},
        ),
    },
    {
        "report_no": "RPT-2026-0002", "sample_no": "YP-2026-0002", "project": "混凝土抗压强度检测",
        "project_name": "高新产业园 A 座主体工程", "client": "示例建设集团", "template": "REPORT_GENERAL_CN",
        "version": "V1.0", "status": "检测录入中", "sign": "待主检签字", "deadline": "正常",
        "department": "力学性能室", "owner": "李力学",
        "detail": _detail(
            [["委托编号", "WT-2026-0002"], ["委托单位", "示例建设集团"], ["工程名称", "高新产业园 A 座主体工程"], ["盖章要求", "CMA"]],
            [["样品编号", "YP-2026-0002"], ["样品名称", "混凝土试块"], ["规格型号", "C30 / 3 组"], ["流转状态", "已领取，检测录入中"]],
            [["检测项目", "混凝土抗压强度检测"], ["检测日期", "2026-11-21"], ["主检人", "李力学"], ["执行标准", "GB/T 50081-2019"]],
            [["记录编号", "YJ-2026-0002"], ["记录条数", "6 条待提交"], ["采集方式", "人工录入"], ["校核状态", "录入中"]],
            [], [],
            extra={"checkInput": {"standard": "GB/T 50081-2019", "instrument": "压力试验机 YAW-2000", "testDate": "2026-11-21", "conclusion": "抗压强度达到设计等级"}},
        ),
    },
    {
        "report_no": "RPT-2026-0003", "sample_no": "YP-2026-0003", "project": "混凝土抗压强度检测",
        "project_name": "市政综合管廊二标段", "client": "示例市政工程公司", "template": "REPORT_GENERAL_CN",
        "version": "V1.1", "status": "待审核", "sign": "主检已签", "deadline": "正常",
        "department": "力学性能室", "owner": "李力学",
        "detail": _detail(
            [["委托编号", "WT-2026-0003"], ["委托单位", "示例市政工程公司"], ["工程名称", "市政综合管廊二标段"], ["盖章要求", "CMA + CNAS"]],
            [["样品编号", "YP-2026-0003"], ["样品名称", "混凝土试块"], ["规格型号", "C40 / 3 组"], ["流转状态", "检测完成，留样待处置"]],
            [["检测项目", "混凝土抗压强度检测"], ["检测日期", "2026-11-18"], ["主检人", "李力学"], ["执行标准", "GB/T 50081-2019"]],
            [["记录编号", "YJ-2026-0003"], ["记录条数", "8 条已确认"], ["采集方式", "压力机采集"], ["校核状态", "已提交审核"]],
            [
                {"group": "标准与能力校验", "status": "通过", "type": "success", "items": [["检测标准", "GB/T 50081-2019 现行有效"], ["能力范围", "在 CMA/CNAS 资质范围内"]]},
                {"group": "仪器有效性校验", "status": "通过", "type": "success", "items": [["仪器名称", "压力试验机 YAW-2000"], ["有效期", "2026-01-01 至 2027-01-01 有效"]]},
            ],
            [{"name": "混凝土抗压强度检测报告.pdf", "type": "PDF", "source": "模板生成", "status": "已生成"}],
        ),
    },
    {
        "report_no": "RPT-2026-0004", "sample_no": "YP-2026-0004", "project": "金属材料拉伸性能检测",
        "project_name": "桥梁钢结构复验项目", "client": "示例路桥集团", "template": "REPORT_GENERAL_CN",
        "version": "V1.2", "status": "待批准", "sign": "审核已签", "deadline": "正常",
        "department": "力学性能室", "owner": "李力学",
        "detail": _detail(
            [["委托编号", "WT-2026-0004"], ["委托单位", "示例路桥集团"], ["工程名称", "桥梁钢结构复验项目"], ["盖章要求", "CMA"]],
            [["样品编号", "YP-2026-0004"], ["样品名称", "热轧带肋钢筋"], ["规格型号", "HRB400 Φ20 / 6 根"], ["流转状态", "检测完成，留样保存"]],
            [["检测项目", "金属材料拉伸性能检测"], ["检测日期", "2026-11-17"], ["主检人", "李力学"], ["执行标准", "GB/T 228.1-2021"]],
            [["记录编号", "YJ-2026-0004"], ["记录条数", "12 条已确认"], ["采集方式", "万能试验机采集"], ["校核状态", "审核通过"]],
            [
                {"group": "标准与能力校验", "status": "通过", "type": "success", "items": [["检测标准", "GB/T 228.1-2021 现行有效"], ["能力范围", "在 CMA 资质范围内"]]},
                {"group": "仪器有效性校验", "status": "通过", "type": "success", "items": [["仪器名称", "万能试验机 WAW-1000"], ["有效期", "2026-03-15 至 2027-03-15 有效"]]},
            ],
            [{"name": "金属材料拉伸性能检测报告.pdf", "type": "PDF", "source": "模板生成", "status": "已生成"}],
        ),
    },
    {
        "report_no": "RPT-2026-0005", "sample_no": "YP-2026-0005", "project": "保温材料导热系数检测",
        "project_name": "绿色建筑外墙保温抽检", "client": "示例地产开发公司", "template": "REPORT_GENERAL_CN",
        "version": "V1.0", "status": "待打印", "sign": "批准已签", "deadline": "正常",
        "department": "环境可靠性室", "owner": "王环境",
        "detail": _detail(
            [["委托编号", "WT-2026-0005"], ["委托单位", "示例地产开发公司"], ["工程名称", "绿色建筑外墙保温抽检"], ["盖章要求", "CMA"]],
            [["样品编号", "YP-2026-0005"], ["样品名称", "挤塑聚苯保温板"], ["规格型号", "XPS 50mm / 3 块"], ["流转状态", "检测完成，留样保存"]],
            [["检测项目", "保温材料导热系数检测"], ["检测日期", "2026-11-15"], ["主检人", "王环境"], ["执行标准", "GB/T 10294-2008"]],
            [["记录编号", "YJ-2026-0005"], ["记录条数", "4 条已确认"], ["采集方式", "导热仪采集"], ["校核状态", "批准通过"]],
            [
                {"group": "标准与能力校验", "status": "通过", "type": "success", "items": [["检测标准", "GB/T 10294-2008 现行有效"]]},
                {"group": "仪器有效性校验", "status": "通过", "type": "success", "items": [["仪器名称", "导热系数测定仪 DRX-300"], ["有效期", "2026-04-10 至 2027-04-10 有效"]]},
            ],
            [{"name": "保温材料导热系数检测报告.pdf", "type": "PDF", "source": "模板生成", "status": "已生成"}],
        ),
    },
]

# ---------- 仪器 ----------
INSTRUMENTS = [
    {"code": "UV-2600", "name": "紫外可见分光光度计 UV-2600", "department": "理化检测室", "site": "一号实验楼",
     "validities": [(date(2026, 1, 1), date(2027, 1, 1), "有效", "检定合格")]},
    {"code": "ME-204E", "name": "电子分析天平 ME-204E", "department": "理化检测室", "site": "一号实验楼",
     "validities": [(date(2026, 2, 1), date(2027, 2, 1), "有效", "检定合格")]},
    {"code": "YAW-2000", "name": "压力试验机 YAW-2000", "department": "力学性能室", "site": "二号实验楼",
     "validities": [(date(2026, 1, 1), date(2027, 1, 1), "有效", "检定合格")]},
    {"code": "WAW-1000", "name": "万能试验机 WAW-1000", "department": "力学性能室", "site": "二号实验楼",
     "validities": [(date(2026, 3, 15), date(2027, 3, 15), "有效", "检定合格")]},
    {"code": "DRX-300", "name": "导热系数测定仪 DRX-300", "department": "环境可靠性室", "site": "三号实验楼",
     "validities": [(date(2026, 4, 10), date(2027, 4, 10), "有效", "检定合格")]},
]

# ---------- 资质 ----------
QUALIFICATIONS = [
    {"kind": "CMA", "department": "理化检测室", "site": "一号实验楼", "scope": "室内空气与水质理化分析",
     "snapshots": [(date(2026, 1, 1), date(2028, 12, 31), "室内空气与水质理化分析", "有效")]},
    {"kind": "CNAS", "department": "力学性能室", "site": "二号实验楼", "scope": "建筑材料及金属力学性能",
     "snapshots": [(date(2026, 1, 1), date(2028, 12, 31), "建筑材料及金属力学性能", "有效")]},
    {"kind": "CMA", "department": "环境可靠性室", "site": "三号实验楼", "scope": "环境热工与可靠性",
     "snapshots": [(date(2026, 1, 1), date(2028, 12, 31), "环境热工与可靠性", "有效")]},
]

# ---------- 标准 ----------
STANDARDS = [
    {"code": "GB/T 18883-2022", "name": "室内空气质量标准", "auth_kind": "CNAS+CMA", "department": "理化检测室", "status": "现行", "expired": False},
    {"code": "GB/T 5750-2023", "name": "生活饮用水标准检验方法", "auth_kind": "CMA", "department": "理化检测室", "status": "现行", "expired": False},
    {"code": "GB/T 50081-2019", "name": "混凝土物理力学性能试验方法标准", "auth_kind": "CNAS+CMA", "department": "力学性能室", "status": "现行", "expired": False},
    {"code": "GB/T 228.1-2021", "name": "金属材料 拉伸试验 第1部分", "auth_kind": "CNAS+CMA", "department": "力学性能室", "status": "现行", "expired": False},
    {"code": "GB/T 10294-2008", "name": "绝热材料稳态热阻及有关特性的测定", "auth_kind": "CMA", "department": "环境可靠性室", "status": "现行", "expired": False},
]

# ---------- 标准工作流步骤 ----------
STANDARD_STEPS = [
    ("entrust_register", "委托登记"),
    ("entrust_review", "合同评审"),
    ("sample_inbound", "样品入库"),
    ("task_assign", "任务分配"),
    ("sample_outbound", "样品出库并领取"),
    ("task_process", "任务处理"),
    ("data_entry", "检测数据录入"),
    ("record_review", "原始记录审核"),
    ("report_review", "报告审核"),
    ("report_approval", "报告批准"),
    ("report_print", "报告签发"),
    ("report_archive", "报告归档"),
]

PROJECT_AUTHORIZATION_STEPS = [
    ("entrust_register", "委托登记"),
    ("entrust_review", "合同评审"),
    ("sample_inbound", "样品入库"),
    ("sample_outbound", "样品出库并领取"),
    ("data_entry", "检测数据录入"),
    ("report_review", "报告审核"),
    ("report_approval", "报告批准"),
    ("report_print", "报告签发"),
    ("report_archive", "报告归档"),
]

# ---------- 检测项目（分布在 3 个检测室）----------
PROJECTS = [
    {"code": "LH01", "name": "室内空气甲醛检测", "dept": "CHEM"},
    {"code": "LH02", "name": "水质理化指标检测", "dept": "CHEM"},
    {"code": "LX01", "name": "混凝土抗压强度检测", "dept": "MECH"},
    {"code": "LX02", "name": "金属材料拉伸性能检测", "dept": "MECH"},
    {"code": "HJ01", "name": "保温材料导热系数检测", "dept": "ENV"},
]

SITES = ["总部", "一号实验楼", "二号实验楼", "三号实验楼"]
