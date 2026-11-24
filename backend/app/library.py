"""检测方案库与检测项目库。

标准、设备、人员和部门主数据由数据库模型及质量接口提供。
"""
from .extensions import db

# ---------- 检测方案库（按检测部门；方案编号进报告号：中心-年方案编号-序号）----------
# 旧常量仅用于尚未执行任命项目导入的开发空库；正式库优先读取 projects。
TEST_SCHEMES = [
    {"dept": "空调设备检测部", "name": "示例站点C-热回收新风机组", "code": "SYHR"},
    {"dept": "空调设备检测部", "name": "热风机-抽样", "code": "CR"},
    {"dept": "空调设备检测部", "name": "空气源热泵-抽检昌平", "code": "CPCHP"},
    {"dept": "空调设备检测部", "name": "暖风机、空气幕", "code": "M"},
    {"dept": "空调设备检测部", "name": "加湿器", "code": "JS"},
    {"dept": "空调设备检测部", "name": "焓差实验装置检验", "code": "JCHC"},
    {"dept": "空调设备检测部", "name": "空气源热泵-抽检示例站点D", "code": "DXCHP"},
    {"dept": "空调设备检测部", "name": "组合式空调机组（现场）", "code": "K"},
    {"dept": "空调设备检测部", "name": "热泵型新风环境控制一体机", "code": "HK"},
    {"dept": "空调设备检测部", "name": "空气源热泵-抽检门头沟", "code": "MTGCHP"},
    {
        "dept": "建筑热工检测部",
        "name": "绝热材料导热系数",
        "code": "RD",
        "project": "导热系数",
        "testDept": "建筑热工检测部",
        "testRoom": "导热系数实验室",
        "testBasis": "GB/T 10294-2008",
        "standardJudge": "GB/T 10294-2008",
        "defaultCycle": "正常",
        "sealRequirement": "CMA + CNAS",
    },
    {"dept": "综合检测部", "name": "墙体保温材料-产品", "code": "QTBW"},
    {"dept": "综合检测部", "name": "防水卷材-抽样", "code": "FSCY"},
    {"dept": "供暖设备检测部", "name": "采暖散热器", "code": "CN"},
    {"dept": "供暖设备检测部", "name": "电采暖散热器", "code": "DN"},
    {"dept": "供暖设备检测部", "name": "恒温阀检验", "code": "HWF"},
    {"dept": "建筑热工检测部", "name": "建筑外窗热工性能", "code": "RGRC"},
    {"dept": "建筑热工检测部", "name": "墙体传热系数（现场）", "code": "QTCR"},
    {"dept": "围护结构检测部", "name": "幕墙四性检测", "code": "MQSX"},
    {"dept": "围护结构检测部", "name": "门窗物理性能", "code": "MCWL"},
    {"dept": "热工设备检测部", "name": "集热器性能", "code": "TYJR"},
    {"dept": "节能中心", "name": "环境热工现场检测", "code": "JNXC"},
    {"dept": "示例中心", "name": "建筑能效测评", "code": "NXCP"},
    {"dept": "示例中心", "name": "室内环境检测", "code": "SNHJ"},
]


def _project_scheme_row(project):
    config = project.workflow_config if isinstance(project.workflow_config, dict) else {}
    department = project.department.name if project.department else ""
    parameters = str(config.get("detectionParameters") or project.name or "").strip()
    location = str(config.get("testLocation") or project.location or "").strip()
    report_type = str(config.get("reportType") or config.get("reportFormat") or "").strip()
    row = {
        "dept": department,
        "name": project.name,
        "code": project.display_code or project.number_code or project.code,
        "numberCode": project.number_code or "",
        "project": parameters,
        "detectionParameters": parameters,
        "testDept": str(config.get("testDept") or department).strip(),
        "reportTitle": str(config.get("reportTitle") or "").strip(),
        "centerPrefix": str(config.get("centerPrefix") or "").strip(),
        "testCategory": str(config.get("testCategory") or "").strip(),
        "reportType": report_type,
        "reportFormat": report_type,
        "sampleAmount": str(config.get("sampleAmount") or "").strip(),
        "sampleStatus": str(config.get("sampleStatus") or "").strip(),
        "testLocation": location,
        "location": location,
    }
    # During the project-master migration, some historical schemes retained
    # controlled standard/room defaults that are not yet represented by
    # dedicated Project columns.  Preserve those non-identity defaults by
    # scheme code while keeping the current project and department authoritative.
    code = str(row["code"] or "").upper()
    legacy = next(
        (item for item in TEST_SCHEMES if str(item.get("code") or "").upper() == code),
        None,
    )
    if legacy:
        for key in (
            "testBasis",
            "standardJudge",
            "testRoom",
            "defaultCycle",
            "sealRequirement",
        ):
            if not row.get(key) and legacy.get(key):
                row[key] = legacy[key]
    return row


def search_schemes(keyword="", dept="", limit=300):
    from .models import Project

    kw = (keyword or "").strip().lower()
    query = Project.query.filter_by(active=True)
    if dept:
        query = query.filter(Project.department.has(name=dept))
    projects = query.order_by(Project.name, Project.number_code, Project.id).all()
    if projects:
        rows = [_project_scheme_row(project) for project in projects]
    else:
        rows = TEST_SCHEMES
        if dept:
            rows = [r for r in rows if r["dept"] == dept]
    if kw:
        rows = [r for r in rows if kw in r["name"].lower() or kw in r["code"].lower()]
    return rows[:limit]


def find_scheme(code, dept=""):
    from .models import Project

    wanted = (code or "").strip().upper()
    query = Project.query.filter_by(active=True)
    if dept:
        query = query.filter(Project.department.has(name=dept))
    project = query.filter(
        db.or_(
            Project.number_code == wanted,
            Project.display_code == wanted,
            Project.code == wanted,
        )
    ).order_by(Project.id).first()
    if project:
        return _project_scheme_row(project)
    return next((row for row in TEST_SCHEMES if row["code"].upper() == wanted), None)


def schemes_tree(keyword="", dept=""):
    """按部门分组返回（前端树形选择）。"""
    rows = search_schemes(keyword, dept)
    by_dept = {}
    for r in rows:
        by_dept.setdefault(r["dept"], []).append(r)
    return [{"dept": d, "schemes": s} for d, s in by_dept.items()]


# ---------- 检测项目库（示例，可后续接真实库）----------
TEST_ITEMS = [
    {"dept": "建筑热工检测部", "name": "导热系数", "code": "RD"},
    {"dept": "综合检测部", "name": "抗压强度", "code": "KY"},
    {"dept": "综合检测部", "name": "防水卷材不透水性", "code": "FSBT"},
    {"dept": "综合检测部", "name": "保温板拉伸粘结强度", "code": "BWLS"},
    {"dept": "供暖设备检测部", "name": "钢筋拉伸", "code": "GJLS"},
    {"dept": "供暖设备检测部", "name": "钢绞线拉伸", "code": "GJXLS"},
    {"dept": "供暖设备检测部", "name": "散热器金属热强度", "code": "SRJS"},
    {"dept": "空调设备检测部", "name": "空气源热泵性能系数COP", "code": "COP"},
    {"dept": "空调设备检测部", "name": "焓差法制冷量", "code": "HCZL"},
    {"dept": "建筑热工检测部", "name": "外窗传热系数K值", "code": "KZHI"},
    {"dept": "围护结构检测部", "name": "幕墙气密性能", "code": "MQQM"},
    {"dept": "热工设备检测部", "name": "集热效率", "code": "JRXL"},
]


def search_items(keyword="", dept="", limit=200):
    from .models import Project

    kw = (keyword or "").strip().lower()
    query = Project.query.filter_by(active=True)
    if dept:
        query = query.filter(Project.department.has(name=dept))
    projects = query.order_by(Project.name, Project.number_code, Project.id).all()
    if projects:
        rows = [{
            "dept": project.department.name if project.department else "",
            "name": project.name,
            "code": project.display_code or project.number_code or project.code,
            "numberCode": project.number_code or "",
        } for project in projects]
    else:
        rows = TEST_ITEMS
        if dept:
            rows = [r for r in rows if r["dept"] == dept]
    if kw:
        rows = [r for r in rows if kw in r["name"].lower() or kw in r["code"].lower()]
    return rows[:limit]
