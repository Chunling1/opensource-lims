"""初始化数据库并灌入种子数据。幂等：已存在数据则跳过（除非 force=True）。"""
import secrets

from flask import current_app

from . import catalog, seed_data
from .extensions import db
from .models import (
    Agreement,
    Department,
    Entrust,
    EquipmentItem,
    FinanceBill,
    Instrument,
    InstrumentValidity,
    Permission,
    Personnel,
    Project,
    ProjectStep,
    Qualification,
    QualificationSnapshot,
    Report,
    Standard,
    StdLibraryItem,
    User,
    department_permissions,
    department_project_permissions,
    user_action_permissions,
    user_data_departments,
    user_data_sites,
)
from .security import hash_password

# 客户协议维护示例（流程图 #2）：一条已登记（进合同库）+ 一条登记中
AGREEMENTS = [
    dict(agreement_no="KD-2026-0188", client="示例建设集团", erp_type="委托检测",
         contract_type="标准合同", project_code="XM-2026-0188", project_name="星河湾三期保温工程",
         category="委托检测", amount="¥86,000", payment="转账", department="综合业务部",
         owner="吴纯凌", status="已登记"),
    dict(agreement_no="KD-2026-0192", client="示例华东客户", erp_type="见证取样",
         contract_type="框架", project_code="XM-2026-0192", project_name="云岭学校扩建",
         category="见证取样", amount="¥42,300", payment="转账", department="综合业务部",
         owner="吴纯凌", status="合同登记中"),
]

# 全模块核查用虚拟项目：同一批数据按不同节点停留，便于在合同、委托、样品、评审、
# 入出库、检测和报告模块逐页核查，且不影响真实业务编号。
VIRTUAL_CHECK_PROJECTS = [
    ("VH-2026-0701", "WT-VH-2026-0701", "BG-VH-2026-0701", "SN-VH-2026-0701", "合同登记核查项目", "华北建工测试有限公司", "合同登记中", "委托中", "待合同评审", "待合同评审", "登记中", ""),
    ("VH-2026-0702", "WT-VH-2026-0702", "BG-VH-2026-0702", "SN-VH-2026-0702", "委托登记核查项目", "示例能源工程有限公司", "已登记", "委托中", "待合同评审", "待合同评审", "登记完成", ""),
    ("VH-2026-0703", "WT-VH-2026-0703", "BG-VH-2026-0703", "SN-VH-2026-0703", "样品登记核查项目", "示例材料科技有限公司", "已登记", "委托完成", "待合同评审", "待合同评审", "登记中", ""),
    ("VH-2026-0704", "WT-VH-2026-0704", "BG-VH-2026-0704", "SN-VH-2026-0704", "合同评审核查项目", "环科建设集团", "已登记", "委托完成", "待合同评审", "待合同评审", "登记完成", ""),
    ("VH-2026-0705", "WT-VH-2026-0705", "BG-VH-2026-0705", "SN-VH-2026-0705", "检测数据核查项目", "城建节能科技有限公司", "已登记", "委托完成", "待审核", "已领取", "登记完成", ""),
    ("VH-2026-0706", "WT-VH-2026-0706", "BG-VH-2026-0706", "SN-VH-2026-0706", "报告归档核查项目", "绿色建筑咨询有限公司", "已登记", "委托完成", "已发放", "已处置", "登记完成", "归档完成"),
]


def _virtual_detail(entrust_no, sample_no, name, state):
    return {
        "summary": [
            {"title": "委托信息", "fields": [["委托编号", entrust_no], ["委托单位", "虚拟核查单位"], ["工程名称", name], ["盖章要求", "CMA"]]},
            {"title": "样品信息", "fields": [["样品编号", sample_no], ["样品名称", "虚拟核查样品"], ["规格型号", "核查规格 / 3 件"], ["流转状态", state]]},
            {"title": "实验信息", "fields": [["检测项目", "保温材料导热系数"], ["检测日期", "2026-07-09"], ["主检人", "系统管理员"], ["执行标准", "GB/T 10294-2008"]]},
            {"title": "原始记录", "fields": [["记录编号", "YJ-" + sample_no], ["记录条数", "虚拟核查记录"], ["采集方式", "手工录入"], ["校核状态", "待核查"]]},
        ],
        "checks": [{"group": "核查数据标记", "status": "演示", "type": "info", "items": [["用途", "模块功能核查"], ["数据来源", "系统虚拟项目"]]}],
        "attachments": [{"name": "虚拟核查附件说明.pdf", "type": "PDF", "source": "系统种子", "status": "已生成"}],
    }


def _seed_virtual_check_projects():
    """幂等补齐全模块核查项目，线上已有业务数据时也可安全调用。"""
    for (_contract_no, entrust_no, report_no, sample_no, project_name, client,
         _agreement_status, entrust_status, report_status, sample_status, sample_reg_state, archive_state) in VIRTUAL_CHECK_PROJECTS:
        if not Entrust.query.filter_by(entrust_no=entrust_no).first():
            db.session.add(Entrust(
                entrust_no=entrust_no, contract_no="", client=client, project_name=project_name,
                project_type="检测核查", amount="¥12,800", department="综合业务部", owner="系统管理员",
                status=entrust_status,
                info={"entrustDate": "2026-07-09",
                      "handler": "系统管理员", "handleDepartment": "综合业务部", "consignor": "核查专员",
                      "clientAddr": "北京市朝阳区核查路 9 号"},
            ))
        if not Report.query.filter_by(report_no=report_no).first():
            db.session.add(Report(
                report_no=report_no, sample_no=sample_no, entrust_no=entrust_no, project="保温材料导热系数",
                project_name=project_name, client=client, template="PRODUCT_REPORT", version="V1.0",
                status=report_status, sign="虚拟核查", deadline="正常", department="综合业务部", owner="系统管理员",
                sample_status=sample_status, sample_reg_state=sample_reg_state, archive_state=archive_state,
                detail=_virtual_detail(entrust_no, sample_no, project_name, report_status),
            ))
    db.session.commit()


def _seed_agreements():
    """幂等灌入示例委托与核查项目（开源版不灌入合同数据）。"""
    _seed_virtual_check_projects()
    if Entrust.query.first() is None:
        db.session.add(Entrust(
            entrust_no="WT-2026-0001", contract_no="", client="示例建设集团",
            project_name="星河湾三期保温工程", project_type="委托检测", amount="¥86,000",
            department="综合业务部", owner="吴纯凌", info={"entrustDate": "2026-07-09"}, status="委托完成",
        ))
        db.session.commit()


def _ensure_columns():
    """对已存在的表补齐模型新增列（用 SQLAlchemy inspector 读列名，跨库通用；
    新库 create_all 已建全所有列，这里全跳过。原 PRAGMA 仅 SQLite 支持，达梦/MySQL 等会报错）。"""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())

    def add(table, col, ddl):
        if table not in tables:
            return
        cols = {c["name"] for c in insp.get_columns(table)}
        if col not in cols:
            try:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
            except Exception as exc:
                # gunicorn 多 worker 同时启动时可能同时发现缺列；另一 worker 已完成补列即视为成功。
                # 其他迁移错误仍然抛出，避免吞掉真实数据库故障。
                if "duplicate column" not in str(exc).lower() and "already exists" not in str(exc).lower():
                    raise
                db.session.rollback()

    for col, ddl in [
        ("out_of_scope", "BOOLEAN DEFAULT 0"), ("out_of_scope_note", "VARCHAR(200)"),
        ("sample_status", "VARCHAR(20) DEFAULT '已入库'"), ("stamped", "BOOLEAN DEFAULT 0"),
        ("sample_pickup", "CLOB"), ("entrust_no", "VARCHAR(40)"),
        # R6 状态机（2026-07-09 批次）：样品登记两态 / 归档态 / 作废（存量默认登记完成、未归档、未作废）
        ("sample_reg_state", "VARCHAR(20) DEFAULT '登记完成'"), ("archive_state", "VARCHAR(20) DEFAULT ''"),
        ("voided", "BOOLEAN DEFAULT 0"),
        ("current_document_version_id", "INTEGER"), ("approved_document_version_id", "INTEGER"),
    ]:
        add("reports", col, ddl)
    for col, ddl in [
        ("must_change_password", "BOOLEAN DEFAULT 0"), ("failed_attempts", "INTEGER DEFAULT 0"),
        ("locked_until", "DATETIME"), ("e_signature", "VARCHAR(120) DEFAULT ''"),
    ]:
        add("users", col, ddl)
    add("agreements", "info", "CLOB")
    for col, ddl in [("category", "VARCHAR(120)"), ("deleted_at", "DATETIME")]:
        add("standards", col, ddl)
    for col, ddl in [("standard_id", "INTEGER"), ("deleted_at", "DATETIME")]:
        add("std_library_items", col, ddl)
    add("equipment_items", "deleted_at", "DATETIME")
    add("equipment_items", "certificate_no", "VARCHAR(160)")
    add("personnel", "deleted_at", "DATETIME")
    for col, ddl in [("file_id", "INTEGER"), ("deleted_at", "DATETIME")]:
        add("report_attachments", col, ddl)
    for col in ("docx_file_id", "pdf_file_id"):
        add("report_document_versions", col, "INTEGER")
    # 数据授权三个面 + 留痕（含子部门/看数据/看成员/授权人/时间）
    for col, ddl in [
        ("include_children", "BOOLEAN NOT NULL DEFAULT 0"), ("see_data", "BOOLEAN NOT NULL DEFAULT 1"),
        ("see_members", "BOOLEAN NOT NULL DEFAULT 1"), ("granted_by", "VARCHAR(40)"), ("granted_at", "VARCHAR(30)"),
    ]:
        add("user_data_departments", col, ddl)
    db.session.commit()


def _ensure_unique_constraints():
    from sqlalchemy import inspect, text

    def agreement_table(inspector):
        return next((name for name in inspector.get_table_names() if name.lower() == "agreements"), None)

    def has_unique_agreement_number():
        inspector = inspect(db.engine)
        table = agreement_table(inspector)
        if not table:
            return False
        unique_columns = set()
        try:
            unique_columns.update(
                tuple(str(column).lower() for column in (item.get("column_names") or ()))
                for item in inspector.get_unique_constraints(table)
            )
        except NotImplementedError:
            pass
        try:
            unique_columns.update(
                tuple(str(column).lower() for column in (item.get("column_names") or ()))
                for item in inspector.get_indexes(table)
                if item.get("unique")
            )
        except NotImplementedError:
            pass
        return ("agreement_no",) in unique_columns

    inspector = inspect(db.engine)
    if not agreement_table(inspector):
        return

    db.session.execute(text(
        "UPDATE agreements SET agreement_no = CASE "
        "WHEN TRIM(agreement_no) = '' THEN NULL ELSE TRIM(agreement_no) END "
        "WHERE agreement_no IS NOT NULL"
    ))
    duplicate = (
        db.session.query(Agreement.agreement_no)
        .filter(Agreement.agreement_no.isnot(None))
        .group_by(Agreement.agreement_no)
        .having(db.func.count(Agreement.id) > 1)
        .first()
    )
    if duplicate:
        db.session.rollback()
        raise RuntimeError("检测到重复合同编号，请先合并重复合同后再升级数据库")

    db.session.commit()
    if has_unique_agreement_number():
        return

    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX uq_agreements_agreement_no "
            "ON agreements (agreement_no)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        if not has_unique_agreement_number():
            raise
    if not has_unique_agreement_number():
        raise RuntimeError("合同编号唯一索引创建后未通过数据库反射校验")


def _seed_quality_ledgers():
    """幂等导入五类参考数据；开源演示环境下无外部 JSON 时自动播种通用示例三库数据。"""
    import os

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(os.path.join(data_dir, "std_library.json")):
        from .functions.reference_data_import import import_all_reference_data
        import_all_reference_data(data_dir, dry_run=False)
    else:
        if Personnel.query.count() == 0:
            dept_names = {code: name for code, name, _p, _s in seed_data.DEPARTMENTS}
            for acc in seed_data.ACCOUNTS:
                dname = dept_names.get(acc["dept"], "综合业务部")
                db.session.add(Personnel(
                    name=acc["name"],
                    code=acc["account"],
                    dept=dname,
                    title="工程师",
                    position=acc["role_name"],
                    assigned_depts=dname,
                    permissions=acc["role_name"],
                ))
        if EquipmentItem.query.count() == 0:
            for ins in seed_data.INSTRUMENTS:
                vf, vt, _st, _note = ins["validities"][0]
                db.session.add(EquipmentItem(
                    archive_no=ins["code"],
                    name=ins["name"],
                    spec=ins["code"],
                    factory_no=f"SN-{ins['code']}",
                    maker="示例仪器厂",
                    dept=ins["department"],
                    place=ins["site"],
                    last_cal_date=vf.isoformat(),
                    period="12个月",
                    plan_cal_date=vt.isoformat(),
                    actual_cal_date=vf.isoformat(),
                ))
        if StdLibraryItem.query.count() == 0:
            default_params = {
                "GB/T 18883-2022": "甲醛;苯;甲苯;二甲苯;TVOC",
                "GB/T 5750-2023": "pH值;色度;浑浊度;总硬度;溶解性总固体",
                "GB/T 50081-2019": "立方体抗压强度;轴心抗压强度;劈裂抗拉强度",
                "GB/T 228.1-2021": "上屈服强度;下屈服强度;抗拉强度;断后伸长率",
                "GB/T 10294-2008": "导热系数;热阻",
            }
            for idx, st in enumerate(seed_data.STANDARDS, start=1):
                db.session.add(StdLibraryItem(
                    controlled_no=f"STD-2026-{idx:03d}",
                    code=st["code"],
                    name=st["name"],
                    parameters=default_params.get(st["code"], ""),
                    auth_kind=st["auth_kind"],
                    category="国家标准",
                    use_depts=st["department"],
                    impl_date="2023-01-01",
                ))
        db.session.commit()

    standard_by_code = {row.code: row.id for row in Standard.query.filter_by(deleted_at=None).all()}
    for row in StdLibraryItem.query.filter_by(standard_id=None, deleted_at=None).all():
        row.standard_id = standard_by_code.get(row.code)
    db.session.commit()


def _force_autoincrement():
    """达梦/Oracle 系方言仅在 column.autoincrement is True 时才生成 IDENTITY 自增列；
    模型默认是 'auto'（不等于 True）。这里对所有单列整数主键显式置 True，须在 create_all 前调用。
    SQLite 上等价（仍是自增主键），无副作用。"""
    from sqlalchemy import Integer
    for table in db.metadata.tables.values():
        pk = list(table.primary_key.columns)
        if len(pk) == 1 and isinstance(pk[0].type, Integer):
            pk[0].autoincrement = True


def seed_all(force: bool = False):
    if force:
        db.drop_all()
    _force_autoincrement()  # 达梦等需显式 autoincrement=True 才建 IDENTITY 列
    db.create_all()
    # 仅给历史 SQLite 开发库保留补列兼容；MySQL/达梦必须走 Alembic，且应用账号无需读取系统目录表。
    if db.engine.dialect.name == "sqlite":
        _ensure_columns()  # 必须在 User.query 之前补列
        _ensure_unique_constraints()
    from .report_documents import seed_default_profiles
    seed_default_profiles()

    if User.query.first() is not None and not force:
        _seed_quality_ledgers()
        _upgrade_inplace()  # 已初始化：仅做幂等的增量升级（新表/新项目/站点/超管授权）
        from .finance_service import sync_finance_bills
        sync_finance_bills()
        return

    # 权限点目录
    for code, name, ptype in catalog.all_permission_catalog():
        db.session.add(Permission(code=code, name=name, ptype=ptype))
    db.session.flush()
    perm_by_code = {p.code: p for p in Permission.query.all()}

    # 部门（两遍：先建后挂父级）
    dept_by_code = {}
    for code, name, parent, site in seed_data.DEPARTMENTS:
        d = Department(code=code, name=name, site=site)
        db.session.add(d)
        dept_by_code[code] = d
    db.session.flush()
    for code, name, parent, site in seed_data.DEPARTMENTS:
        if parent:
            dept_by_code[code].parent_id = dept_by_code[parent].id

    # 项目与步骤
    proj_step_by_key = {}
    for proj in seed_data.PROJECTS:
        p = Project(code=proj["code"], name=proj["name"], department_id=dept_by_code[proj["dept"]].id)
        db.session.add(p)
        db.session.flush()
        for step_code, step_name in seed_data.STANDARD_STEPS:
            s = ProjectStep(project_id=p.id, step_code=step_code, step_name=step_name)
            db.session.add(s)
            db.session.flush()
            proj_step_by_key[(proj["code"], step_code)] = s

    all_codes = set(catalog.all_permission_codes())
    all_actions = catalog.all_action_codes()

    # Bootstrap requires an explicit strong administrator credential; all seeded users change it on first login.
    from .platform.identity.login_security import initial_password, password_is_strong
    prod = bool(current_app.config.get("PROD", False))
    _ap = current_app.config.get("ADMIN_PASSWORD", "")
    if not password_is_strong(_ap) or (prod and len(_ap) < 12):
        raise RuntimeError("初始化需设置强 ADMIN_PASSWORD：大小写英文、数字、特殊字符，至少 8 位；生产至少 12 位")

    def _seed_pw(account):
        return _ap if account == "admin" else initial_password(account)

    # 账号
    for acc in seed_data.ACCOUNTS:
        perms = all_codes if acc["permissions"] == "ALL" else acc["permissions"]
        actions = all_actions if acc["actions"] == "ALL" else acc["actions"]
        u = User(
            account=acc["account"],
            password_hash=hash_password(_seed_pw(acc["account"])),
            name=acc["name"],
            role_key=acc["role_key"],
            role_name=acc["role_name"],
            home_path=acc["home_path"],
            department_id=dept_by_code[acc["dept"]].id,
            data_scope_type=acc["scope_type"],
            data_scope_desc=acc["scope_desc"],
            realname_verified=True,
            must_change_password=True,
        )
        for code in perms:
            if code in perm_by_code:
                u.permissions.append(perm_by_code[code])
        db.session.add(u)
        db.session.flush()
        for action in actions:
            db.session.execute(user_action_permissions.insert().values(user_id=u.id, action_code=action))
        # 按岗位授予本科室或全院项目的对应步骤授权
        role_step_map = {
            "tester": {"data_entry", "sample_outbound", "task_assign", "task_process"},
            "reviewer": {"report_review"},
            "approver": {"report_approval"},
            "acceptance": {"entrust_register", "entrust_review"},
            "sample_admin": {"sample_inbound", "sample_outbound"},
            "printer": {"report_print", "report_archive"},
        }
        if acc["role_key"] in role_step_map:
            wanted_steps = role_step_map[acc["role_key"]]
            for (pcode, scode), step in proj_step_by_key.items():
                if scode not in wanted_steps:
                    continue
                proj = next(p for p in seed_data.PROJECTS if p["code"] == pcode)
                if acc["scope_type"] == "all" or dept_by_code[proj["dept"]].id == u.department_id:
                    u.project_steps.append(step)
        # 超级管理员：全部项目步骤 + 全部数据部门 + 全部站点
        if acc["role_key"] == "admin":
            for step in proj_step_by_key.values():
                u.project_steps.append(step)
            for d in dept_by_code.values():
                u.data_departments.append(d)
            db.session.flush()
            for site in seed_data.SITES:
                db.session.execute(user_data_sites.insert().values(user_id=u.id, site=site))

    # 部门授权初始值采用本部门既有人员授权的并集；人员后续只能在此上限内分配。
    db.session.flush()
    for department in dept_by_code.values():
        if department.code == "ROOT":
            department.permissions = Permission.query.all()
            department.projects = Project.query.filter_by(active=True).all()
            department.project_steps = ProjectStep.query.join(Project).filter(
                Project.active.is_(True)
            ).all()
            continue
        member_users = User.query.filter_by(department_id=department.id).all()
        department.permissions = list({
            permission.code: permission
            for user in member_users
            for permission in user.permissions
        }.values())
        department.projects = list({
            step.project_id: step.project
            for user in member_users
            for step in user.project_steps
            if step.project
        }.values())
        department.project_steps = list({
            step.id: step
            for user in member_users
            for step in user.project_steps
            if step.project and step.project.active
        }.values())

    # 报告
    for r in seed_data.REPORTS:
        db.session.add(Report(
            report_no=r["report_no"], sample_no=r["sample_no"], project=r["project"],
            project_name=r["project_name"], client=r["client"], template=r["template"],
            version=r["version"], status=r["status"], sign=r["sign"], deadline=r["deadline"],
            department=r["department"], owner=r["owner"], detail=r["detail"],
            sample_reg_state="登记完成", sample_status="已领取",
        ))

    # 仪器 + 有效期
    for ins in seed_data.INSTRUMENTS:
        i = Instrument(code=ins["code"], name=ins["name"], department=ins["department"], site=ins["site"], controlled=True)
        db.session.add(i)
        db.session.flush()
        for vf, vt, status, note in ins["validities"]:
            db.session.add(InstrumentValidity(instrument_id=i.id, valid_from=vf, valid_to=vt, status=status, note=note))

    # 资质 + 快照
    for q in seed_data.QUALIFICATIONS:
        qa = Qualification(kind=q["kind"], department=q["department"], site=q["site"], scope=q["scope"])
        db.session.add(qa)
        db.session.flush()
        for ef, vt, scope, status in q["snapshots"]:
            db.session.add(QualificationSnapshot(qualification_id=qa.id, effective_from=ef, valid_to=vt, scope=scope, status=status))

    # 标准
    for s in seed_data.STANDARDS:
        db.session.add(Standard(**s))

    db.session.commit()
    _seed_quality_ledgers()
    _seed_agreements()
    from .finance_service import sync_finance_bills
    sync_finance_bills()


def _replace_department_names(value, migrations):
    """递归替换业务 JSON 中作为字段值保存的旧部门名称。"""
    if isinstance(value, dict):
        return {key: _replace_department_names(item, migrations) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_department_names(item, migrations) for item in value]
    if isinstance(value, str):
        return migrations.get(value, value)
    return value


def _sync_departments():
    """将已有组织树幂等迁移到统一部门清单，并保留人员、项目和授权关系。"""
    desired = {code: (name, parent, site) for code, name, parent, site in seed_data.DEPARTMENTS}
    by_code = {department.code: department for department in Department.query.all()}

    # 先补齐目标节点，再统一名称、站点和上下级。
    for code, (name, _parent, site) in desired.items():
        if code not in by_code:
            department = Department(code=code, name=name, site=site)
            db.session.add(department)
            by_code[code] = department
    db.session.flush()
    for code, (name, parent, site) in desired.items():
        department = by_code[code]
        department.name = name
        department.site = site
        department.parent_id = by_code[parent].id if parent else None
    db.session.flush()

    def merge_department(old, target):
        """把一个旧/重复组织节点的所有 ID 关联迁移到目标节点。"""
        if old is None or old.id == target.id:
            return
        User.query.filter_by(department_id=old.id).update(
            {"department_id": target.id}, synchronize_session=False,
        )
        Project.query.filter_by(department_id=old.id).update(
            {"department_id": target.id}, synchronize_session=False,
        )
        grant_rows = db.session.execute(
            user_data_departments.select().where(user_data_departments.c.department_id == old.id),
        ).mappings().all()
        for grant in grant_rows:
            exists = db.session.execute(
                user_data_departments.select().where(
                    user_data_departments.c.user_id == grant["user_id"],
                    user_data_departments.c.department_id == target.id,
                ),
            ).first()
            if not exists:
                values = dict(grant)
                values["department_id"] = target.id
                db.session.execute(user_data_departments.insert().values(**values))
        db.session.execute(
            user_data_departments.delete().where(user_data_departments.c.department_id == old.id),
        )
        for association, value_column in (
            (department_permissions, department_permissions.c.permission_code),
            (department_project_permissions, department_project_permissions.c.project_id),
        ):
            values = [
                row[0]
                for row in db.session.execute(
                    db.select(value_column).where(
                        association.c.department_id == old.id
                    )
                ).all()
            ]
            existing_values = {
                row[0]
                for row in db.session.execute(
                    db.select(value_column).where(
                        association.c.department_id == target.id
                    )
                ).all()
            }
            for value in values:
                if value not in existing_values:
                    db.session.execute(
                        association.insert().values(
                            department_id=target.id,
                            **{value_column.name: value},
                        )
                    )
            db.session.execute(
                association.delete().where(association.c.department_id == old.id)
            )
        Department.query.filter_by(parent_id=old.id).update(
            {"parent_id": target.id}, synchronize_session=False,
        )
        db.session.delete(old)

    # 合并被取消的旧代码节点。关联使用部门 ID 的数据先转到目标节点。
    for old_code, target_code in seed_data.DEPARTMENT_CODE_MERGES.items():
        merge_department(by_code.get(old_code), by_code[target_code])
    db.session.flush()

    # 参考数据历史上可能以 LQD_* 代码导入过同名旧节点，也一并按名称合并。
    desired_codes = set(desired)
    desired_by_name = {department.name: department for code, department in by_code.items() if code in desired_codes}
    for old in Department.query.all():
        if old.code in desired_codes:
            continue
        target_name = seed_data.DEPARTMENT_NAME_MIGRATIONS.get(old.name)
        target = desired_by_name.get(target_name or old.name)
        if target is not None:
            merge_department(old, target)
    db.session.flush()

    migrations = seed_data.DEPARTMENT_NAME_MIGRATIONS
    for model, attribute in (
        (Agreement, "department"),
        (Entrust, "department"),
        (Report, "department"),
        (FinanceBill, "department"),
        (Instrument, "department"),
        (Qualification, "department"),
        (Standard, "department"),
        (EquipmentItem, "dept"),
        (Personnel, "dept"),
    ):
        column = getattr(model, attribute)
        for old_name, new_name in migrations.items():
            model.query.filter(column == old_name).update(
                {column: new_name}, synchronize_session=False,
            )

    # 多部门文本字段去重迁移。
    for row in Personnel.query.filter(Personnel.assigned_depts.isnot(None)).all():
        values = [migrations.get(item, item) for item in (row.assigned_depts or "").split(";") if item]
        row.assigned_depts = ";".join(dict.fromkeys(values))
    for row in StdLibraryItem.query.filter(StdLibraryItem.use_depts.isnot(None)).all():
        values = [migrations.get(item, item) for item in (row.use_depts or "").split(";") if item]
        row.use_depts = ";".join(dict.fromkeys(values))

    # 表单快照中的部门也同步，避免查看旧单时继续出现已取消名称。
    for row in Agreement.query.filter(Agreement.info.isnot(None)).all():
        row.info = _replace_department_names(row.info, migrations)
    for row in Entrust.query.filter(Entrust.info.isnot(None)).all():
        row.info = _replace_department_names(row.info, migrations)
    for row in Report.query.filter(Report.detail.isnot(None)).all():
        row.detail = _replace_department_names(row.detail, migrations)

    return {department.code: department for department in Department.query.all()}


def _upgrade_inplace():
    """对已存在的数据库做幂等增量升级，不动报告等业务数据。

    用于线上库平滑加入：新检测项目 + 标准步骤、站点、超管的项目/数据/站点授权。
    """
    dept_by_code = _sync_departments()

    # 合同登记状态改名：登记中 → 合同登记中（幂等，平滑升级老库）
    from sqlalchemy import text as _t
    db.session.execute(_t("UPDATE agreements SET status='合同登记中' WHERE status='登记中'"))
    # 委托单状态：旧库「已登记」→「委托中」（新增手动「完成委托」流转 委托中→委托完成）
    db.session.execute(_t("UPDATE entrusts SET status='委托中' WHERE status='已登记'"))
    # 迁移旧的复合状态为显式节点，避免同一记录同时显示“待校核/样品入库中”。
    db.session.execute(_t(
        "UPDATE reports SET status='待样品领取' "
        "WHERE status IN ('待合同评审','待校核') AND sample_status='已入库'"
    ))
    db.session.execute(_t(
        "UPDATE reports SET status='待样品入库' "
        "WHERE status='待校核' AND sample_status='待入库'"
    ))
    db.session.execute(_t(
        "UPDATE reports SET status='检测录入中' "
        "WHERE status='待合同评审' AND sample_status IN ('已领取','已出库')"
    ))
    for report in Report.query.filter_by(status="待校核").all():
        if (report.sample_status or "") in ("已领取", "已出库") \
                and not ((report.detail or {}).get("checkInput") or {}).get("standard"):
            report.status = "检测录入中"
        else:
            # 已完成检测录入的历史记录跳过已取消的报告校核，直接进入审核。
            report.status = "待审核"

    # 列补齐已在 seed_all → _ensure_columns 提前完成
    _seed_agreements()  # 新增 agreements 表的示例数据（幂等）

    # 1) 同步检测项目为新集合（清理旧项目，补齐新项目 + 标准步骤）
    want_codes = {p["code"] for p in seed_data.PROJECTS}
    for p in Project.query.all():
        if p.code not in want_codes:
            db.session.delete(p)
    db.session.flush()
    for proj in seed_data.PROJECTS:
        p = Project.query.filter_by(code=proj["code"]).first()
        if not p:
            dep = dept_by_code.get(proj["dept"])
            p = Project(code=proj["code"], name=proj["name"], department_id=dep.id if dep else None)
            db.session.add(p)
            db.session.flush()
        have = {s.step_code for s in p.steps}
        for step_code, step_name in seed_data.STANDARD_STEPS:
            if step_code not in have:
                db.session.add(ProjectStep(project_id=p.id, step_code=step_code, step_name=step_name))
    db.session.flush()

    # 1.5) 刷新仪器校准有效期（覆盖当前期间，便于三库校验演示）
    for ins_data in seed_data.INSTRUMENTS:
        ins = Instrument.query.filter_by(code=ins_data["code"]).first()
        if ins:
            for v in list(ins.validities):
                db.session.delete(v)
            db.session.flush()
            for vf, vt, status, note in ins_data["validities"]:
                db.session.add(InstrumentValidity(instrument_id=ins.id, valid_from=vf, valid_to=vt, status=status, note=note))

    # 1.8) 补齐权限点目录新增项（如合同评审页面/动作权限）
    have_perm = {p.code for p in Permission.query.all()}
    for code, name, ptype in catalog.all_permission_catalog():
        if code not in have_perm:
            db.session.add(Permission(code=code, name=name, ptype=ptype))
    db.session.flush()

    # 2) 超级管理员补齐：全部功能/动作权限 + 项目步骤 + 数据部门 + 站点
    admin = User.query.filter_by(role_key="admin").first()
    if admin:
        admin.permissions = Permission.query.all()
        from sqlalchemy import text as _text
        have_actions = {row[0] for row in db.session.execute(
            _text("SELECT action_code FROM user_action_permissions WHERE user_id=:uid"),
            {"uid": admin.id}).fetchall()}
        for action in catalog.all_action_codes():
            if action not in have_actions:
                db.session.execute(user_action_permissions.insert().values(user_id=admin.id, action_code=action))
        admin.project_steps = ProjectStep.query.all()
        admin.data_departments = Department.query.all()
        existing_sites = set(admin.data_site_names())
        for site in seed_data.SITES:
            if site not in existing_sites:
                db.session.execute(user_data_sites.insert().values(user_id=admin.id, site=site))

    # 根机构是固定的全院权限边界；发布升级或新增项目后自动补齐。
    root_department = dept_by_code.get("ROOT")
    if root_department:
        root_department.permissions = Permission.query.all()
        root_department.projects = Project.query.filter_by(active=True).all()
        root_department.project_steps = ProjectStep.query.join(Project).filter(
            Project.active.is_(True)
        ).all()

    finance_user = User.query.filter_by(role_key="finance").first()
    if finance_user:
        from sqlalchemy import text as _text
        have_actions = {row[0] for row in db.session.execute(
            _text("SELECT action_code FROM user_action_permissions WHERE user_id=:uid"),
            {"uid": finance_user.id}).fetchall()}
        for action in [
            "finance.pricing.execute", "finance.payment.register", "finance.payment.confirm",
            "finance.invoice.issue", "finance.settlement.execute", "finance.refund.execute",
        ]:
            if action not in have_actions:
                db.session.execute(user_action_permissions.insert().values(user_id=finance_user.id, action_code=action))

    db.session.commit()
