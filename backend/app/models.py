"""数据库模型 — 按《检测信息系统后台开发说明》第 2 节权限与业务模型设计。

权限模型对应规格：
  部门权限 = 功能授权 + 项目授权（部门多级，子部门是父部门子集）
  用户权限 = 功能授权 + 项目授权 + 数据授权 + 审批事项授权（均为部门授权的子集）
"""
import json
from datetime import date, datetime
from uuid import uuid4

from flask import g, has_request_context
from sqlalchemy.types import Text, TypeDecorator, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB

from .extensions import db
from .platform.workflow import (
    agreement_data_status,
    entrust_data_status,
    report_data_status,
)


class JSONText(TypeDecorator):
    """可移植 JSON 列：以 TEXT/CLOB 存储（json 序列化），适配 SQLite / 达梦 / 人大金仓 / GaussDB / MySQL 等。
    读出自动反序列化为 dict/list；写入自动 json.dumps。避免依赖各方言的原生 JSON 类型（达梦方言可能不支持 db.JSON，
    导致 create_all 建表失败）。本系统 detail/info 均整体重赋值（非就地改），无需 Mutable 追踪。"""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        # MySQL 的 TEXT 只有 64 KiB，业务快照与模板内容必须使用 LONGTEXT。
        if dialect.name in {"mysql", "mariadb"}:
            from sqlalchemy.dialects.mysql import LONGTEXT

            return dialect.type_descriptor(LONGTEXT())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value


# ---------- 关联表 ----------

# 用户-功能授权（菜单/页面/操作权限点）
user_permissions = db.Table(
    "user_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("permission_code", db.String(80), db.ForeignKey("permissions.code"), primary_key=True),
)

# 用户-审批事项授权（report.review.pass 等动作 / 报告更改、合同更改等事项）
user_action_permissions = db.Table(
    "user_action_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("action_code", db.String(80), primary_key=True),
)

# 用户-项目授权（检测项目的某个工作流步骤）
user_project_permissions = db.Table(
    "user_project_permissions",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("project_step_id", db.Integer, db.ForeignKey("project_steps.id"), primary_key=True),
)

# 人员权限模板。模板仅保存可复用的功能/项目环节组合；套用模板时仍写入
# user_permissions / user_project_permissions，运行时鉴权因此保持单一口径。
permission_template_permissions = db.Table(
    "permission_template_permissions",
    db.Column(
        "template_id",
        db.Integer,
        db.ForeignKey("permission_templates.id"),
        primary_key=True,
    ),
    db.Column(
        "permission_code",
        db.String(80),
        db.ForeignKey("permissions.code"),
        primary_key=True,
    ),
)

permission_template_project_steps = db.Table(
    "permission_template_project_steps",
    db.Column(
        "template_id",
        db.Integer,
        db.ForeignKey("permission_templates.id"),
        primary_key=True,
    ),
    db.Column(
        "project_step_id",
        db.Integer,
        db.ForeignKey("project_steps.id"),
        primary_key=True,
    ),
)

permission_template_users = db.Table(
    "permission_template_users",
    db.Column(
        "template_id",
        db.Integer,
        db.ForeignKey("permission_templates.id"),
        primary_key=True,
    ),
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("users.id"),
        primary_key=True,
    ),
)

# 部门-功能授权。人员功能授权必须是所属部门授权的子集。
department_permissions = db.Table(
    "department_permissions",
    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey("departments.id"),
        primary_key=True,
    ),
    db.Column(
        "permission_code",
        db.String(80),
        db.ForeignKey("permissions.code"),
        primary_key=True,
    ),
)

# 部门-项目步骤授权。人员的项目步骤授权必须是所属部门项目步骤授权的子集。
department_project_step_permissions = db.Table(
    "department_project_step_permissions",
    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey("departments.id"),
        primary_key=True,
    ),
    db.Column(
        "project_step_id",
        db.Integer,
        db.ForeignKey("project_steps.id"),
        primary_key=True,
    ),
)

# 旧版部门-完整项目授权表继续保留，用于兼容历史数据和旧接口；新授权逻辑以
# department_project_step_permissions 为准。
department_project_permissions = db.Table(
    "department_project_permissions",
    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey("departments.id"),
        primary_key=True,
    ),
    db.Column(
        "project_id",
        db.Integer,
        db.ForeignKey("projects.id"),
        primary_key=True,
    ),
)

# 用户-标准禁用项。标准先按所属部门默认全部授权，仅记录管理员明确取消的例外。
user_standard_denials = db.Table(
    "user_standard_denials",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("standard_item_id", db.Integer, db.ForeignKey("std_library_items.id"), primary_key=True),
)

# CNAS 能力条目可同时服务多个部门。仅保存经过现有标准/项目库确认的映射，
# 未映射条目保留在导入批次中但不向业务表单开放。
capability_departments = db.Table(
    "capability_departments",
    db.Column(
        "capability_entry_id",
        db.Integer,
        db.ForeignKey("capability_entries.id"),
        primary_key=True,
    ),
    db.Column(
        "department_id",
        db.Integer,
        db.ForeignKey("departments.id"),
        primary_key=True,
    ),
)

# 用户-数据授权（按部门，可跨部门授权多个）
# 每条授权带三个面：看数据(see_data) / 看成员(see_members) / 含子部门(include_children)，并留痕授权人/时间
user_data_departments = db.Table(
    "user_data_departments",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("departments.id"), primary_key=True),
    db.Column("include_children", db.Boolean, nullable=False, server_default=db.text("0")),
    db.Column("see_data", db.Boolean, nullable=False, server_default=db.text("1")),
    db.Column("see_members", db.Boolean, nullable=False, server_default=db.text("1")),
    db.Column("granted_by", db.String(40)),
    db.Column("granted_at", db.String(30)),
)

# 用户-数据授权（按站点）
user_equipment_departments = db.Table(
    "user_equipment_departments",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("departments.id"), primary_key=True),
)

user_data_sites = db.Table(
    "user_data_sites",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("site", db.String(80), primary_key=True),
)


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    site = db.Column(db.String(80))  # 实验室地点，按资质区分不同实验室
    children = db.relationship("Department", backref=db.backref("parent", remote_side=[id]))
    permissions = db.relationship("Permission", secondary=department_permissions)
    projects = db.relationship("Project", secondary=department_project_permissions)
    project_steps = db.relationship(
        "ProjectStep",
        secondary=department_project_step_permissions,
    )

    def ancestor_codes(self):
        codes, node = [], self
        while node is not None:
            codes.append(node.code)
            node = node.parent
        return codes


def _dept_tree_maps():
    """构建 部门id->子id列表 与 部门id->名称 映射，用于含子部门的授权展开。请求内缓存避免重复全表建树。"""
    if has_request_context() and hasattr(g, "_dept_maps_cache"):
        return g._dept_maps_cache
    rows = Department.query.with_entities(Department.id, Department.parent_id, Department.name).all()
    children, name_by_id = {}, {}
    for did, pid, name in rows:
        name_by_id[did] = name
        children.setdefault(pid, []).append(did)
    result = (children, name_by_id)
    if has_request_context():
        g._dept_maps_cache = result
    return result


def _descendant_ids(dept_id, children):
    """含自身的全部后代部门 id（带 seen 防数据成环导致死循环）。"""
    out, stack, seen = [], [dept_id], set()
    while stack:
        d = stack.pop()
        if d in seen:
            continue
        seen.add(d)
        out.append(d)
        stack.extend(children.get(d, []))
    return out


class Permission(db.Model):
    __tablename__ = "permissions"
    code = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    ptype = db.Column(db.String(20), nullable=False)  # module / page


class PermissionTemplate(db.Model):
    __tablename__ = "permission_templates"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(300), default="")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    permissions = db.relationship(
        "Permission",
        secondary=permission_template_permissions,
    )
    project_steps = db.relationship(
        "ProjectStep",
        secondary=permission_template_project_steps,
    )
    users = db.relationship(
        "User",
        secondary=permission_template_users,
        back_populates="permission_templates",
    )


class PermissionAppointmentImport(db.Model):
    """一次经确认的人员任命表导入及其异常清单。"""

    __tablename__ = "permission_appointment_imports"
    id = db.Column(db.Integer, primary_key=True)
    source_sha256 = db.Column(db.String(64), nullable=False, index=True)
    source_name = db.Column(db.String(255), nullable=False, default="")
    summary = db.Column(JSONText)
    exceptions = db.Column(JSONText)
    applied_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    display_code = db.Column(db.String(40))
    number_code = db.Column(db.String(40))
    location = db.Column(db.String(80))
    source_department = db.Column(db.String(80))
    source_key = db.Column(db.String(64), index=True)
    # 项目编号变更后保留旧编号，保证历史报告仍能定位到原项目。
    code_aliases = db.Column(JSONText)
    # {"skippedSteps": ["entrust_review", ...]}，按项目控制报告流转节点。
    workflow_config = db.Column(JSONText)
    active = db.Column(db.Boolean, nullable=False, default=True)
    department = db.relationship("Department")
    steps = db.relationship("ProjectStep", backref="project", cascade="all, delete-orphan")


class ProjectStep(db.Model):
    __tablename__ = "project_steps"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    step_code = db.Column(db.String(40), nullable=False)
    step_name = db.Column(db.String(80), nullable=False)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    role_key = db.Column(db.String(30), nullable=False)
    role_name = db.Column(db.String(30), nullable=False)
    home_path = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    # 数据授权：站点/部门分组，最小颗粒度部门
    data_scope_type = db.Column(db.String(20), default="department")  # all/department/self/authorization
    data_scope_desc = db.Column(db.String(120), default="")
    enabled = db.Column(db.Boolean, default=True)
    realname_verified = db.Column(db.Boolean, default=False)
    e_signature = db.Column(db.String(120), default="")  # 电子签名（主检/审核/批准签字时取用）
    # 登录安全（流程图 #1）：首次登录改密 + 连续 5 次错误锁定 30 分钟
    must_change_password = db.Column(db.Boolean, default=False)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)

    department = db.relationship("Department")
    permissions = db.relationship("Permission", secondary=user_permissions)
    project_steps = db.relationship("ProjectStep", secondary=user_project_permissions)
    data_departments = db.relationship("Department", secondary=user_data_departments)
    permission_templates = db.relationship(
        "PermissionTemplate",
        secondary=permission_template_users,
        back_populates="users",
    )

    def permission_codes(self):
        from .organization_privileges import has_full_platform_authority
        if has_full_platform_authority(self):
            from .catalog import all_permission_codes
            return sorted(set(all_permission_codes()) | {p.code for p in Permission.query.all()})
        return sorted(self._page_codes_with_actions(self._action_grant_rows()))

    def _page_codes_with_actions(self, action_rows):
        codes = {p.code for p in self.permissions}
        # Distribution grants include their navigation prerequisite. Derive it
        # instead of persisting a page grant that would survive revocation.
        from .report_delivery import RELEASE_ACTION
        if any(row.action_code == RELEASE_ACTION for row in action_rows):
            codes.add('report.release.view')
        return codes

    def _action_grant_rows(self):
        from .list_reads import user_grant_rows
        return user_grant_rows(user_action_permissions, self.id, lambda: db.session.execute(
            user_action_permissions.select().where(user_action_permissions.c.user_id == self.id)
        ).fetchall())

    def action_codes(self):
        from .catalog import ACTION_PERMISSIONS, MODULE_IMPLIED_ACTIONS

        from .organization_privileges import has_full_platform_authority
        if has_full_platform_authority(self):
            return sorted(
                {code for code, _name in ACTION_PERMISSIONS}
                | set(MODULE_IMPLIED_ACTIONS)
            )
        rows = self._action_grant_rows()
        # 已绑定功能模块的操作不再接受历史独立授权，避免旧的
        # “删除/撤销/通过”等操作码绕过对应模块权限。
        granted = {
            r.action_code
            for r in rows
            if r.action_code not in MODULE_IMPLIED_ACTIONS
            and not r.action_code.startswith("erp.outbound.")
        }
        permissions = self._page_codes_with_actions(rows)
        granted.update(
            action_code
            for action_code, module_codes in MODULE_IMPLIED_ACTIONS.items()
            if permissions.intersection(module_codes)
        )
        return sorted(granted)

    def data_site_names(self):
        from .list_reads import user_grant_rows
        rows = user_grant_rows(user_data_sites, self.id, lambda: db.session.execute(
            user_data_sites.select().where(user_data_sites.c.user_id == self.id)
        ).fetchall())
        return sorted(r.site for r in rows)

    def _data_grant_rows(self):
        from .list_reads import user_grant_rows
        return user_grant_rows(user_data_departments, self.id, lambda: db.session.execute(
            user_data_departments.select().where(user_data_departments.c.user_id == self.id)
        ).fetchall())

    def data_department_ids(self):
        """数据可见部门 ID 集合：see_data 授权 + 含子部门展开。"""
        from .organization_privileges import has_full_platform_authority
        if has_full_platform_authority(self):
            return {row.id for row in Department.query.all()}
        rows = self._data_grant_rows()
        if rows:
            children, _ = _dept_tree_maps()
            ids = set()
            for r in rows:
                if not r.see_data:
                    continue
                ids.update(_descendant_ids(r.department_id, children) if r.include_children else [r.department_id])
            if ids:
                return ids
        return {self.department_id} if self.department_id else set()

    def data_department_names(self):
        """兼容展示用部门名；业务数据边界应优先使用 ``data_department_ids``。"""
        ids = self.data_department_ids()
        if not ids:
            return []
        _, name_by_id = _dept_tree_maps()
        return [name_by_id[i] for i in sorted(ids) if i in name_by_id]

    def member_visible_department_ids(self):
        """成员可见部门 id 集合：本部门 + see_members 授权（含子部门展开）。"""
        from .organization_privileges import has_full_platform_authority
        if has_full_platform_authority(self):
            return {row.id for row in Department.query.all()}
        children, _ = _dept_tree_maps()
        ids = set()
        if self.department_id:
            ids.add(self.department_id)
        for r in self._data_grant_rows():
            if not r.see_members:
                continue
            ids.update(_descendant_ids(r.department_id, children) if r.include_children else [r.department_id])
        return ids

    def project_step_ids(self):
        return sorted(s.id for s in self.effective_project_steps())

    def effective_project_steps(self):
        from .organization_privileges import has_full_platform_authority
        if has_full_platform_authority(self):
            return ProjectStep.query.order_by(ProjectStep.id).all()
        return self.project_steps

    def data_scope(self):
        from .organization_privileges import has_full_platform_authority
        full = has_full_platform_authority(self)
        return {
            "department": self.department.name if self.department else "",
            "scopeType": "all" if full else self.data_scope_type,
            "description": "管理员或公司直属人员：全院数据、全部业务代码及功能权限" if full else self.data_scope_desc or "",
            "departments": self.data_department_names(),
            "sites": self.data_site_names(),
        }


class BusinessNumberSequence(db.Model):
    __tablename__ = "business_number_sequences"
    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(80), unique=True, nullable=False)
    last_value = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    # Business form concurrency token; separate from the published report version.
    edit_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": edit_version}

    report_no = db.Column(db.String(40), unique=True, nullable=False)
    sample_no = db.Column(db.String(40))
    project = db.Column(db.Text)
    project_name = db.Column(db.Text)
    client = db.Column(db.Text)
    template = db.Column(db.String(60))
    version = db.Column(db.String(20))
    status = db.Column(db.String(20))
    sign = db.Column(db.String(20))
    deadline = db.Column(db.String(20))
    department = db.Column(db.String(40))
    owner = db.Column(db.String(40))
    detail = db.Column(JSONText)  # 委托/样品/实验/原始记录 + 三组校验 + 附件
    # 超范围：检测人员在校验未通过（标准不在库/仪器失效）时仍强行提交，批准人需收到通知
    out_of_scope = db.Column(db.Boolean, default=False)
    out_of_scope_note = db.Column(db.Text)
    # 样品实物流转独立记录，不随报告签发或归档改变
    sample_status = db.Column(db.String(20), default="待入库")
    # 样品出库领取单：{managerId, managerName, outTime, receiverName, pickupTime, signed, returnNote}
    sample_pickup = db.Column(JSONText)
    # 所属委托单（一个委托单下多个样品/报告）
    entrust_no = db.Column(db.String(40), index=True)
    # 电子签章/盖章：打印环节加盖
    stamped = db.Column(db.Boolean, default=False)
    # R6 状态机补充：样品登记两态（登记完成才进合同评审待办）；报告归档态（归档完成=流程结束）(R6)
    sample_reg_state = db.Column(db.String(20), default="登记完成")
    archive_state = db.Column(db.String(20), default="")
    # R3 作废样品单：作废后从有效流程剔除，数据保留可查询（Q4 默认不可恢复）
    voided = db.Column(db.Boolean, default=False)
    # 当前用于流转的正式报告版本，以及批准时锁定的版本。旧报告允许为空，
    # 新版标准报告在校核/审核/批准前由报告文档服务校验版本与业务快照一致。
    current_document_version_id = db.Column(db.Integer)
    approved_document_version_id = db.Column(db.Integer)
    # 主报告及其派生报告关系。历史数据为空时按 main 处理。
    main_report_no = db.Column(db.String(40), index=True)
    report_kind = db.Column(db.String(20), nullable=False, default="main", index=True)
    report_suffix = db.Column(db.String(40), default="")
    # Server-owned creation timestamp used by the immutable template-engine
    # rollout cutoff.  Historical rows are backfilled from their first audit.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_row(self, *, issuance_label=None):
        from .sample_identity import sample_number
        if self.status == "待打印" and not self.voided and issuance_label is None:
            from .issuance_data_status import issuance_status
            issuance_label = issuance_status(self)
        from .report_delivery import delivery_released
        released = delivery_released(self)
        from .data_entry_state import report_data_entry_started
        data_entry_started = report_data_entry_started(self)
        from .report_scope import scope_projection
        scope = scope_projection(self) if (self.detail or {}).get('checkInput') else None
        return {
            "editVersion": self.edit_version,
            "reportNo": self.report_no,
            "sampleNo": sample_number(self),
            "project": self.project,
            "client": self.client,
            "template": self.template,
            "version": self.version,
            "status": self.status,
            "sign": self.sign,
            "deadline": self.deadline,
            "outOfScope": scope["outOfScope"] if scope else bool(self.out_of_scope),
            "scopeStatus": scope["state"] if scope else "needs_review",
            "outOfScopeNote": (scope["note"] if scope["outOfScope"] else "") if scope else (self.out_of_scope_note or ""),
            "sampleStatus": self.sample_status or "待入库",
            # 仅表示检测数据表单是否至少保存过一次草稿；与“完成检测”分开。
            "dataEntryStarted": data_entry_started,
            "samplePickup": self.sample_pickup or None,
            "workflowDates": (self.detail or {}).get("workflowDates") or {},
            "entrustNo": self.entrust_no or "",
            "stamped": bool(self.stamped),
            "department": self.department,
            "owner": self.owner,
            # 退回信息（校核/审核/批准退回 或 更正申请时记录），供检测数据更改页展示
            "returnInfo": (self.detail or {}).get("returnInfo") or None,
            "hasInternalCorrectionHistory": bool((self.detail or {}).get("internalCorrectionRevision")),
            # R6 数据状态（派生标签，G5 列表/表单统一展示）
            "sampleRegState": self.sample_reg_state or "登记完成",
            "archiveState": self.archive_state or "",
            "distributionComplete": released,
            "voided": bool(self.voided),
            "currentDocumentVersionId": self.current_document_version_id,
            "approvedDocumentVersionId": self.approved_document_version_id,
            "mainReportNo": self.main_report_no or self.report_no,
            "reportKind": self.report_kind or "main",
            "reportSuffix": self.report_suffix or "",
            "dataStatus": report_data_status(self.status, self.sample_status,
                                             self.sample_reg_state, self.archive_state, self.voided,
                                             data_entry_started, issuance_label, released),
        }


class Entrust(db.Model):
    """委托单（一单多样品）：检测人员选认领的外部ERP合同后填写提交，样品归属于委托单。"""
    __tablename__ = "entrusts"
    id = db.Column(db.Integer, primary_key=True)
    # Business form concurrency token; separate from the published report version.
    edit_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": edit_version}

    entrust_no = db.Column(db.String(40), index=True, unique=True)
    contract_no = db.Column(db.String(60))      # 关联的外部ERP合同编号（已认领）
    client = db.Column(db.String(120))
    project_name = db.Column(db.String(200))
    project_type = db.Column(db.String(40))     # 项目类型/检测类别
    amount = db.Column(db.String(40))
    department = db.Column(db.String(40))
    owner = db.Column(db.String(40))
    info = db.Column(JSONText)                   # 完整委托表单字段
    status = db.Column(db.String(20), default="委托中")    # 委托中 → 委托完成（手动完成委托）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def sample_count(self):
        from .list_reads import sample_count
        return sample_count(self.entrust_no, lambda:
            Report.query.filter(Report.entrust_no == self.entrust_no).count())

    def to_row(self):
        info = self.info or {}
        return {
            "editVersion": self.edit_version,
            "id": self.id,
            "entrustNo": self.entrust_no,
            "contractNo": self.contract_no,
            "client": self.client,
            "projectName": self.project_name,
            "projectType": self.project_type,
            "amount": self.amount,
            "department": self.department,
            "owner": self.owner,
            "status": self.status,
            "sampleCount": self.sample_count(),
            "date": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
            "info": info,
            # 委托登记清单字段：外部ERP来源与检测侧手工补录分开返回，供列表、查询和导出复用。
            "erpProjectNo": (
                info.get("erpProjectNo") or info.get("projectCode")
                or info.get("projectRecordNo") or info.get("projectTradeCode") or ""
            ),
            "erpProjectType": info.get("erpType") or self.project_type,
            "contractPartyA": info.get("contractPartyA") or self.client,
            "otherPartyA": info.get("otherPartyA") or "",
            "entrustDate": info.get("entrustDate") or (self.created_at.strftime("%Y-%m-%d") if self.created_at else ""),
            "handler": info.get("handler") or self.owner,
            "handlerDepartment": info.get("handleDepartment") or self.department,
            "consignor": info.get("consignor") or "",
            "clientAddress": info.get("clientAddr") or "",
            "dataStatus": entrust_data_status(self.status),
        }


class FinanceBill(db.Model):
    """委托费用单：计价、收款、确认、开票、结算、退款共用一个权威状态。"""
    __tablename__ = "finance_bills"
    id = db.Column(db.Integer, primary_key=True)
    bill_no = db.Column(db.String(80), unique=True, nullable=False, index=True)
    entrust_no = db.Column(db.String(60), unique=True, nullable=False, index=True)
    contract_no = db.Column(db.String(60), index=True)
    client = db.Column(db.String(160), index=True)
    project_name = db.Column(db.String(240))
    department = db.Column(db.String(80), index=True)
    amount_due = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    pending_payment = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    amount_received = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    amount_invoiced = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    amount_refunded = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="待计价", index=True)
    payment_method = db.Column(db.String(40))
    payment_reference = db.Column(db.String(100))
    payment_date = db.Column(db.String(20))
    invoice_no = db.Column(db.String(100))
    invoice_type = db.Column(db.String(60))
    invoice_date = db.Column(db.String(20))
    settlement_no = db.Column(db.String(100))
    settlement_date = db.Column(db.String(20))
    refund_date = db.Column(db.String(20))
    note = db.Column(db.Text)
    last_command_key = db.Column(db.String(80))
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.String(60))
    updated_by = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def _money(value):
        return f"{value or 0:.2f}"

    def to_row(self):
        received = self.amount_received or 0
        refunded = self.amount_refunded or 0
        due = self.amount_due or 0
        return {
            "id": self.id, "billNo": self.bill_no, "entrustNo": self.entrust_no,
            "contractNo": self.contract_no or "", "client": self.client or "",
            "projectName": self.project_name or "", "department": self.department or "",
            "amountDue": self._money(due), "pendingPayment": self._money(self.pending_payment),
            "amountReceived": self._money(received), "amountInvoiced": self._money(self.amount_invoiced),
            "amountRefunded": self._money(refunded),
            "netReceived": self._money(received - refunded),
            "outstanding": self._money(max(due - received, 0)), "status": self.status,
            "paymentMethod": self.payment_method or "", "paymentReference": self.payment_reference or "",
            "paymentDate": self.payment_date or "", "invoiceNo": self.invoice_no or "",
            "invoiceType": self.invoice_type or "", "invoiceDate": self.invoice_date or "",
            "settlementNo": self.settlement_no or "", "settlementDate": self.settlement_date or "",
            "refundDate": self.refund_date or "", "note": self.note or "", "version": self.version,
            "createdBy": self.created_by or "", "updatedBy": self.updated_by or "",
            "createdAt": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updatedAt": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
        }


class Agreement(db.Model):
    """客户协议/合同维护（流程图 #2）：外部ERP回传只读字段 + 科室维护信息，登记中→已登记后推送合同库。"""
    __tablename__ = "agreements"
    __table_args__ = (
        db.Index("uq_agreements_agreement_no", "agreement_no", unique=True),
    )
    id = db.Column(db.Integer, primary_key=True)
    # Business form concurrency token; separate from the published report version.
    edit_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": edit_version}

    # 外部ERP回传（只读）
    agreement_no = db.Column(db.String(60))               # 合同协议编号
    client = db.Column(db.String(120))                    # 委托单位甲方
    erp_type = db.Column(db.String(40))               # 外部ERP项目类型
    # 合同类型：标准合同 / 框架 / 虚拟框架
    contract_type = db.Column(db.String(20), default="标准合同")
    project_code = db.Column(db.String(60))               # 项管平台推送的项目编号
    # 科室维护信息
    project_name = db.Column(db.String(200))              # 项目名称（委托工程名称）
    category = db.Column(db.String(40))                   # 类别
    amount = db.Column(db.String(40))                     # 金额
    payment = db.Column(db.String(40))                    # 支付方式
    department = db.Column(db.String(40))                 # 部门
    owner = db.Column(db.String(40))                      # 项目负责人
    status = db.Column(db.String(20), default="合同登记中")    # 合同登记中 / 已登记
    # 合同登记补充信息（甲方/乙方/标准基本属性等，认领后补充）
    info = db.Column(JSONText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_row(self):
        return {
            "editVersion": self.edit_version,
            "id": self.id,
            "agreementNo": self.agreement_no or "",
            "client": self.client,
            "erpType": self.erp_type,
            "contractType": self.contract_type,
            "projectCode": self.project_code,
            "projectName": self.project_name,
            "category": self.category,
            "amount": self.amount,
            "payment": self.payment,
            "department": self.department,
            "owner": self.owner,
            "status": self.status,
            "info": self.info or {},
            "dataStatus": agreement_data_status(self.status),
        }


class ErpContractState(db.Model):
    """外部ERP回传合同在本系统中的认领或删除状态。"""
    __tablename__ = "erp_contract_states"
    id = db.Column(db.Integer, primary_key=True)
    contract_no = db.Column(db.String(60), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    source_data = db.Column(JSONText)
    updated_by = db.Column(db.String(40))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ReportAttachment(db.Model):
    """报告附件元数据；新文件存目录，data 仅作为旧数据回退列。"""
    __tablename__ = "report_attachments"
    id = db.Column(db.Integer, primary_key=True)
    report_no = db.Column(db.String(40), index=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.Text, default="application/octet-stream")
    kind = db.Column(db.String(20))  # PDF / Word
    source = db.Column(db.String(60))
    status = db.Column(db.String(40))
    file_id = db.Column(db.Integer, db.ForeignKey("stored_files.id"), index=True)
    data = db.Column(LargeBinary().with_variant(LONGBLOB(), 'mysql', 'mariadb'))
    uploaded_by = db.Column(db.String(40))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, index=True)
    stored_file = db.relationship("StoredFile", foreign_keys=[file_id])

    def meta(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.kind,
            "source": self.source,
            "status": self.status,
            "uploadedBy": self.uploaded_by,
            "contentType": self.content_type,
            "sizeBytes": self.stored_file.size_bytes if self.stored_file else len(self.data or b""),
        }


class ReportCorrectionRequest(db.Model):
    """更正申请、两级审批记录与附件证据。"""

    __tablename__ = "report_correction_requests"
    id = db.Column(db.Integer, primary_key=True)
    main_report_no = db.Column(db.String(40), nullable=False, index=True)
    correction_report_no = db.Column(db.String(40), index=True)
    return_mode = db.Column(db.String(24), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    application_attachment_id = db.Column(
        db.Integer, db.ForeignKey("report_attachments.id"), nullable=False
    )
    status = db.Column(db.String(32), nullable=False, default="pending_director", index=True)
    applicant_account = db.Column(db.String(40), nullable=False)
    applicant_name = db.Column(db.String(60), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    director_account = db.Column(db.String(40))
    director_name = db.Column(db.String(60))
    director_note = db.Column(db.Text)
    director_at = db.Column(db.DateTime)
    leader_account = db.Column(db.String(40))
    leader_name = db.Column(db.String(60))
    leader_note = db.Column(db.Text)
    leader_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    correction_type = db.Column(db.String(16))
    receipt_attachment_id = db.Column(db.Integer, db.ForeignKey("report_attachments.id"))
    approver_account = db.Column(db.String(40))
    approver_name = db.Column(db.String(60))
    approver_note = db.Column(db.Text)
    approver_at = db.Column(db.DateTime)
    application_attachment = db.relationship("ReportAttachment", foreign_keys=[application_attachment_id])
    receipt_attachment = db.relationship("ReportAttachment", foreign_keys=[receipt_attachment_id])

    def to_dict(self):
        return {
            "id": self.id,
            "mainReportNo": self.main_report_no,
            "correctionReportNo": self.correction_report_no or "",
            "returnMode": self.return_mode,
            "reason": self.reason,
            "applicationAttachment": self.application_attachment.meta() if self.application_attachment else None,
            "correctionType": self.correction_type or "legacy",
            "receiptAttachment": self.receipt_attachment.meta() if self.receipt_attachment else None,
            "approverAccount": self.approver_account or "",
            "approverName": self.approver_name or "",
            "approverNote": self.approver_note or "",
            "approverAt": self.approver_at.isoformat(timespec="seconds") if self.approver_at else "",
            "status": self.status,
            "applicantAccount": self.applicant_account,
            "applicantName": self.applicant_name,
            "department": self.department,
            "directorAccount": self.director_account or "",
            "directorName": self.director_name or "",
            "directorNote": self.director_note or "",
            "directorAt": self.director_at.isoformat(timespec="seconds") if self.director_at else "",
            "leaderAccount": self.leader_account or "",
            "leaderName": self.leader_name or "",
            "leaderNote": self.leader_note or "",
            "leaderAt": self.leader_at.isoformat(timespec="seconds") if self.leader_at else "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }


class ReportTemplateProfile(db.Model):
    """报告版式配置：按报告编号/检测中心选择页面组成与必填字段。"""
    __tablename__ = "report_template_profiles"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    report_no_pattern = db.Column(db.String(160), nullable=False)
    center_prefix = db.Column(db.String(20), default="")
    report_type = db.Column(db.String(40), default="")
    composition = db.Column(JSONText)
    required_fields = db.Column(JSONText)
    requires_version = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "reportNoPattern": self.report_no_pattern,
            "centerPrefix": self.center_prefix or "",
            "reportType": self.report_type or "",
            "composition": self.composition or [],
            "requiredFields": self.required_fields or [],
            "requiresVersion": bool(self.requires_version),
            "active": bool(self.active),
        }


class ReportDocumentContent(db.Model):
    """结构化报告正文。结果组、照片位与附加页以可移植 JSON/CLOB 保存。"""
    __tablename__ = "report_document_contents"
    id = db.Column(db.Integer, primary_key=True)
    report_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    profile_code = db.Column(db.String(80), nullable=False, default="STANDARD-COVER-HOME")
    result_groups = db.Column(JSONText)
    remarks = db.Column(db.Text)
    photos = db.Column(JSONText)
    extra_pages = db.Column(JSONText)
    updated_by = db.Column(db.String(40))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "profileCode": self.profile_code,
            "resultGroups": self.result_groups or [],
            "remarks": self.remarks or "",
            "photos": self.photos or [],
            "extraPages": self.extra_pages or [],
            "updatedBy": self.updated_by or "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }


class ReportDocumentVersion(db.Model):
    """不可变报告文件版本。正式报告与内部审核包分别编号和留存。"""
    __tablename__ = "report_document_versions"
    __table_args__ = (
        db.UniqueConstraint("report_no", "output_kind", "version_no", name="uq_report_document_version"),
    )
    id = db.Column(db.Integer, primary_key=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    output_kind = db.Column(db.String(20), nullable=False, default="official")
    version_no = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="generated")
    profile_code = db.Column(db.String(80), nullable=False)
    composition = db.Column(JSONText)
    snapshot = db.Column(JSONText)
    warnings = db.Column(JSONText)
    source_hash = db.Column(db.String(64), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    docx_file_id = db.Column(db.Integer, db.ForeignKey("stored_files.id"), index=True)
    pdf_file_id = db.Column(db.Integer, db.ForeignKey("stored_files.id"), index=True)
    docx_data = db.Column(LargeBinary().with_variant(LONGBLOB(), 'mysql', 'mariadb'))
    pdf_data = db.Column(LargeBinary().with_variant(LONGBLOB(), 'mysql', 'mariadb'))
    created_by = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    docx_file = db.relationship("StoredFile", foreign_keys=[docx_file_id])
    pdf_file = db.relationship("StoredFile", foreign_keys=[pdf_file_id])

    def meta(self, current_source_hash=""):
        return {
            "id": self.id,
            "reportNo": self.report_no,
            "outputKind": self.output_kind,
            "versionNo": self.version_no,
            "versionLabel": f"V{self.version_no}",
            "status": self.status,
            "profileCode": self.profile_code,
            "composition": self.composition or [],
            "warnings": self.warnings or [],
            "sourceHash": self.source_hash,
            "sha256": self.sha256,
            "hasDocx": bool(self.docx_file_id or self.docx_data),
            "hasPdf": bool(self.pdf_file_id or self.pdf_data),
            "stale": bool(current_source_hash and current_source_hash != self.source_hash),
            "createdBy": self.created_by or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
        }


class ReportRenderJob(db.Model):
    """持久化生成任务，前端轮询状态，服务重启后可明确显示失败原因。"""
    __tablename__ = "report_render_jobs"
    id = db.Column(db.String(36), primary_key=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    output_kind = db.Column(db.String(20), nullable=False, default="official")
    status = db.Column(db.String(20), nullable=False, default="queued")
    progress = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.Text, default="")
    version_id = db.Column(db.Integer)
    requested_by = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "reportNo": self.report_no,
            "outputKind": self.output_kind,
            "status": self.status,
            "progress": self.progress,
            "message": self.message or "",
            "versionId": self.version_id,
            "requestedBy": self.requested_by or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "completedAt": self.completed_at.isoformat(timespec="seconds") if self.completed_at else "",
        }


class OperationAudit(db.Model):
    """关键写操作审计日志，记录操作者、对象、修改前后值与执行结果。"""
    __tablename__ = "operation_audits"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False, default="business")
    action = db.Column(db.String(100), nullable=False)
    object_type = db.Column(db.String(60), nullable=False)
    object_id = db.Column(db.String(100), nullable=False)
    trace_id = db.Column(
        db.String(64), nullable=False, default=lambda: uuid4().hex, index=True
    )
    user_id = db.Column(db.Integer)
    account = db.Column(db.String(40))
    user_name = db.Column(db.String(40))
    ip_address = db.Column(db.String(80))
    before_data = db.Column(JSONText)
    after_data = db.Column(JSONText)
    success = db.Column(db.Boolean, default=True)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "action": self.action,
            "objectType": self.object_type,
            "objectId": self.object_id,
            "traceId": self.trace_id,
            "account": self.account or "",
            "userName": self.user_name or "",
            "ipAddress": self.ip_address or "",
            "before": self.before_data,
            "after": self.after_data,
            "success": bool(self.success),
            "message": self.message or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
        }


class AiSearchDocument(db.Model):
    """Database-portable search projection. Sensitive source fields never enter this table."""

    __tablename__ = "ai_search_documents"
    __table_args__ = (
        db.UniqueConstraint("entity_type", "entity_id", name="uq_ai_search_document_entity"),
    )

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    entity_id = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text)
    status = db.Column(db.String(60), index=True)
    department = db.Column(db.String(120), index=True)
    route = db.Column(db.String(300))
    source_updated_at = db.Column(db.DateTime)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    terms = db.relationship(
        "AiSearchTerm",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AiSearchTerm(db.Model):
    """Weighted normalized terms backed only by ordinary BTree indexes."""

    __tablename__ = "ai_search_terms"
    __table_args__ = (
        db.UniqueConstraint("document_id", "term", name="uq_ai_search_term_document"),
    )

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("ai_search_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term = db.Column(db.String(160), nullable=False, index=True)
    weight = db.Column(db.Integer, nullable=False, default=1)
    document = db.relationship("AiSearchDocument", back_populates="terms")


class AiIndexState(db.Model):
    """Worker watermark and diagnostics; one row per index namespace."""

    __tablename__ = "ai_index_state"

    key = db.Column(db.String(40), primary_key=True)
    last_audit_id = db.Column(db.Integer, nullable=False, default=0)
    rebuild_version = db.Column(db.String(80))
    backlog = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text)
    last_started_at = db.Column(db.DateTime)
    last_finished_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AiSearchDictionary(db.Model):
    """Administrator-managed aliases used by the portable AI search index."""

    __tablename__ = "ai_search_dictionary"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    canonical = db.Column(db.String(160), nullable=False)
    aliases = db.Column(JSONText)
    entity_types = db.Column(JSONText)
    weight = db.Column(db.Integer, nullable=False, default=4)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_row(self):
        return {
            "id": self.id,
            "code": self.code,
            "canonical": self.canonical,
            "aliases": list(self.aliases or []),
            "entityTypes": list(self.entity_types or []),
            "weight": int(self.weight or 0),
            "active": bool(self.active),
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }


class DataMigrationBatch(db.Model):
    """Immutable/resumable source-to-DM migration ledger."""

    __tablename__ = "data_migration_batches"

    batch_id = db.Column(db.String(80), primary_key=True)
    source_sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="running")
    last_table = db.Column(db.String(120))
    manifest = db.Column(JSONText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Instrument(db.Model):
    """仪器：维护状态，支持以指定时间查询有效性（规格 2.6）。"""
    __tablename__ = "instruments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    department = db.Column(db.String(40))
    site = db.Column(db.String(80))
    controlled = db.Column(db.Boolean, default=True)
    validities = db.relationship("InstrumentValidity", backref="instrument", cascade="all, delete-orphan")

    def valid_at(self, when):
        for v in self.validities:
            if v.valid_from <= when <= v.valid_to:
                return v
        return None


class InstrumentValidity(db.Model):
    __tablename__ = "instrument_validities"
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey("instruments.id"), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="有效")  # 检定/校准状态
    note = db.Column(db.String(120))


class Qualification(db.Model):
    """资质：CNAS/CMA 授权，每次更新保留快照（规格 2.6）。"""
    __tablename__ = "qualifications"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)  # CNAS / CMA
    department = db.Column(db.String(40))
    site = db.Column(db.String(80))
    scope = db.Column(db.String(200))
    snapshots = db.relationship("QualificationSnapshot", backref="qualification", cascade="all, delete-orphan")

    def valid_at(self, when):
        snap = None
        for s in sorted(self.snapshots, key=lambda x: x.effective_from):
            if s.effective_from <= when:
                snap = s
        return snap


class QualificationSnapshot(db.Model):
    __tablename__ = "qualification_snapshots"
    id = db.Column(db.Integer, primary_key=True)
    qualification_id = db.Column(db.Integer, db.ForeignKey("qualifications.id"), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=False)
    scope = db.Column(db.String(200))
    status = db.Column(db.String(20), default="有效")


class Standard(db.Model):
    """标准：维护状态（属于 CNAS/CMA、是否过期），支持历史快照查询（规格 2.6）。"""
    __tablename__ = "standards"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(160), unique=True, nullable=False)
    name = db.Column(db.String(400))
    auth_kind = db.Column(db.String(60))  # CNAS / CMA / CNAS+CMA
    department = db.Column(db.String(200))
    category = db.Column(db.String(120))
    status = db.Column(db.String(20), default="现行")  # 现行/作废/被替代
    expired = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, index=True)
    controlled_items = db.relationship("StdLibraryItem", back_populates="standard")

    def to_row(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name or "",
            "authKind": self.auth_kind or "",
            "department": self.department or "",
            "category": self.category or "",
            "status": self.status or "现行",
            "expired": bool(self.expired),
        }


class StdLibraryItem(db.Model):
    """检测标准基础信息库（质量体系）：完整登记 + 使用部门授权（图1）。"""
    __tablename__ = "std_library_items"
    id = db.Column(db.Integer, primary_key=True)
    standard_id = db.Column(db.Integer, db.ForeignKey("standards.id"), index=True)
    controlled_no = db.Column(db.String(40))            # 受控号
    code = db.Column(db.String(160), index=True)        # 标准编号
    name = db.Column(db.String(400))                    # 标准名称
    parameters = db.Column(db.Text, default="")         # 检测参数（；分隔，随标准一起导入维护）
    auth_kind = db.Column(db.String(60))                # 标准资质类别（一单一库+CNAS+CMA 等）
    out_of_scope = db.Column(db.Boolean, default=False)  # 是否在资质范围外
    category = db.Column(db.String(120))                # 类别
    location = db.Column(db.String(120))                # 存放地点
    issue_count = db.Column(db.String(20))              # 发放数量
    issuer = db.Column(db.String(60))                   # 发放人
    use_depts = db.Column(db.Text)                      # 使用部门（；分隔）
    impl_date = db.Column(db.String(20))                # 实施日期
    void_date = db.Column(db.String(20))                # 作废日期
    delay_days = db.Column(db.String(20))               # 延期时间(天)
    replace_no = db.Column(db.String(160))              # 替换标准号
    is_english = db.Column(db.Boolean, default=False)   # 是否英文标准
    is_onsite_standard = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    remark = db.Column(db.Text)                         # 备注
    deleted_at = db.Column(db.DateTime, index=True)
    standard = db.relationship("Standard", back_populates="controlled_items")

    def to_row(self):
        today = date.today().isoformat()
        if self.out_of_scope:
            status = "资质范围外"
        elif self.void_date and self.void_date <= today:
            status = "已作废"
        elif self.impl_date and self.impl_date > today:
            status = "待实施"
        else:
            status = "现行"
        return {
            "id": self.id, "controlledNo": self.controlled_no, "code": self.code, "name": self.name,
            "parameters": self.parameters or "",
            "authKind": self.auth_kind, "outOfScope": self.out_of_scope, "category": self.category,
            "location": self.location, "issueCount": self.issue_count, "issuer": self.issuer,
            "useDepts": [d for d in (self.use_depts or "").split(";") if d],
            "implDate": self.impl_date, "voidDate": self.void_date, "delayDays": self.delay_days,
            "replaceNo": self.replace_no, "isEnglish": self.is_english, "remark": self.remark,
            "isOnsiteStandard": bool(self.is_onsite_standard),
            "status": status,
        }


class CapabilityImportBatch(db.Model):
    """CNAS 官方附件的一次不可变导入快照。"""

    __tablename__ = "capability_import_batches"
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(260), nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="review", index=True)
    attachment_count = db.Column(db.Integer, nullable=False, default=0)
    chinese_page_count = db.Column(db.Integer, nullable=False, default=0)
    summary = db.Column(JSONText)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activated_at = db.Column(db.DateTime)

    entries = db.relationship(
        "CapabilityEntry",
        backref="batch",
        cascade="all, delete-orphan",
    )


class CapabilityEntry(db.Model):
    """标准、对象、项目/参数、场所和限制条件的最小 CNAS 能力关系。"""

    __tablename__ = "capability_entries"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("capability_import_batches.id"),
        nullable=False,
        index=True,
    )
    standard_item_id = db.Column(
        db.Integer,
        db.ForeignKey("std_library_items.id"),
        index=True,
    )
    capability_type = db.Column(db.String(20), nullable=False, index=True)
    certificate_no = db.Column(db.String(40), nullable=False, index=True)
    site = db.Column(db.String(80), nullable=False, index=True)
    section_path = db.Column(db.String(400))
    object_seq = db.Column(db.String(40))
    object_name = db.Column(db.String(400), nullable=False)
    item_seq = db.Column(db.String(40))
    item_name = db.Column(db.String(400), nullable=False, index=True)
    standard_code = db.Column(db.String(200), nullable=False, index=True)
    standard_name = db.Column(db.String(600))
    method_clause = db.Column(db.String(600))
    restriction = db.Column(db.Text)
    effective_date = db.Column(db.Date)
    expires_on = db.Column(db.Date)
    source_file = db.Column(db.String(300), nullable=False)
    source_page = db.Column(db.Integer, nullable=False)
    source_row = db.Column(db.Integer, nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False)
    raw_cells = db.Column(JSONText)
    mapping_status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    active = db.Column(db.Boolean, nullable=False, default=False, index=True)

    standard_item = db.relationship("StdLibraryItem")
    departments = db.relationship("Department", secondary=capability_departments)

    def to_row(self):
        from .applications.quality_resources.testing_locations import capability_address, capability_accreditation
        return {
            "id": self.id,
            "batchId": self.batch_id,
            "capabilityType": self.capability_type,
            "address": capability_address(self),
            "accreditation": capability_accreditation(self),
            "certificateNo": self.certificate_no,
            "site": self.site,
            "sectionPath": self.section_path or "",
            "objectSeq": self.object_seq or "",
            "objectName": self.object_name,
            "itemSeq": self.item_seq or "",
            "itemName": self.item_name,
            "standardCode": self.standard_code,
            "standardName": self.standard_name or "",
            "methodClause": self.method_clause or "",
            "restriction": self.restriction or "",
            "effectiveDate": self.effective_date.isoformat() if self.effective_date else "",
            "expiresOn": self.expires_on.isoformat() if self.expires_on else "",
            "sourceFile": self.source_file,
            "sourcePage": self.source_page,
            "sourceRow": self.source_row,
            "mappingStatus": self.mapping_status,
            "active": bool(self.active),
            "departments": [row.name for row in self.departments],
        }


class ComplianceAcknowledgement(db.Model):
    """合同评审、报告审核、批准各自生成的不可修改合规确认记录。"""

    __tablename__ = "compliance_acknowledgements"
    __table_args__ = (
        db.UniqueConstraint(
            "report_no",
            "stage",
            "preflight_version",
            name="uq_compliance_ack_report_stage_version",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    stage = db.Column(db.String(30), nullable=False, index=True)
    preflight_version = db.Column(db.String(64), nullable=False, index=True)
    issues = db.Column(JSONText, nullable=False)
    acknowledged_issue_ids = db.Column(JSONText, nullable=False)
    requested_seal = db.Column(db.String(80))
    final_seal = db.Column(db.String(80))
    opinion = db.Column(db.Text)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor_account = db.Column(db.String(40), nullable=False)
    actor_name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class EquipmentItem(db.Model):
    """设备台账（质量体系）：仪器设备基本信息 + 检定/使用等（图4）。"""
    __tablename__ = "equipment_items"
    id = db.Column(db.Integer, primary_key=True)
    edit_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": edit_version}
    archive_no = db.Column(db.String(60), index=True)   # 档案号
    name = db.Column(db.String(400))                    # 仪器设备名称
    spec = db.Column(db.String(200))                    # 规格型号
    factory_no = db.Column(db.String(160))              # 仪器出厂号
    maker = db.Column(db.String(200))                   # 生产厂家
    cal_unit = db.Column(db.String(200))                # 检定/测试单位
    dept = db.Column(db.String(80), index=True)         # 所属科室
    place = db.Column(db.String(160))                   # 放置单位
    last_cal_date = db.Column(db.String(20))            # 最近检定/测试日期
    period = db.Column(db.String(40))                   # 周期
    plan_cal_date = db.Column(db.String(20))            # 计划检定/测试日期
    actual_cal_date = db.Column(db.String(20))          # 实际检定/测试日期
    meas_range = db.Column(db.String(160))              # 量程
    accuracy = db.Column(db.String(160))                # 准确度
    keeper = db.Column(db.String(60))                   # 仪器保管人
    buy_date = db.Column(db.String(20))                 # 购入日期
    buy_price = db.Column(db.String(40))                # 购入价格
    use_record = db.Column(db.String(160))              # 使用记录
    # manual 是 MySQL 8.4 保留字；显式引用列名以保持旧库字段兼容。
    manual = db.Column("manual", db.String(120), quote=True)  # 说明书
    cert = db.Column(db.String(120))                    # 合格证
    certificate_no = db.Column(db.String(160))          # 检定/校准证书编号（非合格证）
    accept_doc = db.Column(db.String(120))              # 验收单
    status = db.Column(db.String(40), index=True)       # 设备状态
    equip_type = db.Column(db.String(60))               # 设备类型（表单项）
    cal_person = db.Column(db.String(60))               # 检定人（表单项）
    valid_until = db.Column(db.String(20))              # 有效期（表单项）
    remark = db.Column(db.Text)                         # 备注
    deleted_at = db.Column(db.DateTime, index=True)

    def manual_status(self):
        value = (self.status or "").strip()
        if any(token in value for token in ("停用", "报废", "失效", "维修")):
            return "停用/报废"
        return "可用"

    def is_long_term(self):
        value = (self.period or "").strip()
        return any(token in value for token in ("长期", "永久", "不定期"))

    def effective_status(self, on_date=None):
        if self.manual_status() == "停用/报废":
            return "停用/报废"
        if self.is_long_term():
            return "可用"
        reference = on_date or date.today()
        value = (self.valid_until or self.plan_cal_date or "").strip()
        try:
            next_date = datetime.strptime(value[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return "限制使用"
        return "可用" if next_date >= reference else "限制使用"

    def test_interval_error(self, start, end):
        from .equipment_eligibility import evaluate_interval
        result = evaluate_interval(self, start, end)
        return result['message'] if result['level'] == 'block' else ''

    def to_row(self, full=False, on_date=None):
        base = {
            "editVersion": self.edit_version,
            "id": self.id, "archiveNo": self.archive_no, "name": self.name, "spec": self.spec,
            "dept": self.dept, "status": self.effective_status(on_date),
            "manualStatus": self.manual_status(), "keeper": self.keeper,
            "lastCalDate": self.last_cal_date, "actualCalDate": self.actual_cal_date,
            "period": self.period, "planCalDate": self.plan_cal_date,
            "validUntil": self.valid_until,
        }
        if not full:
            return base
        base.update({
            "factoryNo": self.factory_no, "maker": self.maker, "calUnit": self.cal_unit,
            "place": self.place, "period": self.period, "actualCalDate": self.actual_cal_date,
            "range": self.meas_range, "accuracy": self.accuracy, "buyDate": self.buy_date,
            "buyPrice": self.buy_price, "useRecord": self.use_record, "manual": self.manual,
            "cert": self.cert, "acceptDoc": self.accept_doc, "equipType": self.equip_type,
            "certificateNo": self.certificate_no,
            "calPerson": self.cal_person, "validUntil": self.valid_until, "remark": self.remark,
        })
        return base


class EquipmentCalibrationRecord(db.Model):
    """Immutable calibration/master-data maintenance trail for an equipment item."""
    __tablename__ = "equipment_calibration_records"
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment_items.id"), nullable=False, index=True)
    source = db.Column(db.String(30), nullable=False, default="single_update")
    changed_fields = db.Column(JSONText)
    before_data = db.Column(JSONText)
    after_data = db.Column(JSONText)
    changed_by_account = db.Column(db.String(40))
    changed_by_name = db.Column(db.String(60))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_row(self):
        return {
            "id": self.id,
            "source": self.source,
            "changedFields": self.changed_fields or [],
            "before": self.before_data or {},
            "after": self.after_data or {},
            "changedByAccount": self.changed_by_account or "",
            "changedByName": self.changed_by_name or "",
            "changedAt": self.changed_at.isoformat(timespec="seconds") if self.changed_at else "",
        }


class EquipmentUsageRecord(db.Model):
    """Report-linked usage record captured when detection data is saved."""
    __tablename__ = "equipment_usage_records"
    __table_args__ = (
        db.UniqueConstraint("equipment_id", "report_no", name="uq_equipment_usage_report"),
    )
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment_items.id"), nullable=False, index=True)
    report_no = db.Column(db.String(40), nullable=False, index=True)
    sample_no = db.Column(db.String(40))
    project = db.Column(db.Text)
    used_from = db.Column(db.String(20))
    used_to = db.Column(db.String(20))
    used_by_account = db.Column(db.String(40))
    used_by_name = db.Column(db.String(60))
    status_at_use = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_row(self):
        return {
            "id": self.id,
            "reportNo": self.report_no,
            "sampleNo": self.sample_no or "",
            "project": self.project or "",
            "usedFrom": self.used_from or "",
            "usedTo": self.used_to or "",
            "usedByAccount": self.used_by_account or "",
            "usedByName": self.used_by_name or "",
            "statusAtUse": self.status_at_use or "",
            "createdAt": self.created_at.isoformat(timespec="seconds") if self.created_at else "",
            "updatedAt": self.updated_at.isoformat(timespec="seconds") if self.updated_at else "",
        }


class Personnel(db.Model):
    """质量体系-人员登记：人员信息 + 部门分配（可工作的部门范围）+ 流程权限分配。"""
    __tablename__ = "personnel"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), index=True)          # 姓名
    code = db.Column(db.String(60), index=True)          # 编号（账号）
    gender = db.Column(db.String(8))                     # 性别
    education = db.Column(db.String(40))                 # 文化程度
    title = db.Column(db.String(80))                     # 职称/资格
    major = db.Column(db.String(80))                     # 所学专业
    grad_time = db.Column(db.String(20))                 # 毕业时间
    position = db.Column(db.String(80))                  # 岗位/职务
    # 更正申请审批职位：department_director / institute_leader / 空。
    approval_position = db.Column(db.String(32), default="", index=True)
    test_scope = db.Column(db.Text)                      # 检测/业务范围
    check_scope = db.Column(db.Text)                     # 检查/业务范围
    remark = db.Column(db.Text)                          # 备注
    dept = db.Column(db.String(80), index=True)          # 所在部门
    birth_date = db.Column(db.String(20))                # 出生日期
    id_no = db.Column(db.String(40))                     # 身份证号
    mobile = db.Column(db.String(20))                    # 手机号（登录联系/e签宝实名账号）
    ethnicity = db.Column(db.String(20))                 # 民族
    native_place = db.Column(db.String(60))              # 籍贯
    political = db.Column(db.String(40))                 # 政治情况
    school = db.Column(db.String(120))                   # 毕业院校
    work_start_time = db.Column(db.String(20))           # 参加工作时间
    join_time = db.Column(db.String(20))                 # 来单位时间
    assigned_depts = db.Column(db.Text)                  # 部门分配（；分隔，可工作部门范围）
    permissions = db.Column(db.Text)                     # 流程权限（；分隔：委托/样品/合同评审/数据录入/审核/批准…）
    deleted_at = db.Column(db.DateTime, index=True)

    def to_row(self, full=False):
        base = {
            "id": self.id, "name": self.name, "code": self.code, "dept": self.dept,
            "title": self.title, "position": self.position,
            "approvalPosition": self.approval_position or "", "mobile": self.mobile or "",
            "assignedDepts": [d for d in (self.assigned_depts or "").split(";") if d],
            "permissions": [p for p in (self.permissions or "").split(";") if p],
        }
        if not full:
            return base
        base.update({
            "gender": self.gender, "education": self.education, "major": self.major,
            "gradTime": self.grad_time, "testScope": self.test_scope, "checkScope": self.check_scope,
            "remark": self.remark, "birthDate": self.birth_date,
            "ethnicity": self.ethnicity, "nativePlace": self.native_place, "political": self.political,
            "school": self.school, "workStartTime": self.work_start_time, "joinTime": self.join_time,
        })
        return base


# 深模块按领域拆分，仍从 app.models 暴露以兼容现有调用方。
from .data_models.eln import (  # noqa: E402,F401
    ElnLaunchCode,
    ElnOriginalRecord,
    ElnProjectConfig,
    ElnRecordRevision,
    ElnRecordTemplate,
    ElnTaskPolicy,
)
from .data_models.equipment_scheme import EquipmentScheme  # noqa: E402,F401
from .data_models.files import StoredFile  # noqa: E402,F401
from .data_models.esign import (  # noqa: E402,F401
    EsignIdentityBinding,
    EsignReminderLog,
    ReportEsignFlow,
    ReportEsignSigner,
)
from .data_models.public_portal import (  # noqa: E402,F401
    ExternalAccount,
    ExternalCustomerDocument,
    ExternalEntrustApplication,
    ExternalEntrustEvent,
    ExternalPortalNotification,
    ExternalScheme,
    ExternalShipment,
)
from .data_models.reference_imports import (  # noqa: E402,F401
    LegacyImportBatch,
    LegacyImportConflict,
    LegacyImportRow,
)
from .data_models.system_config import (  # noqa: E402,F401
    CustomTemplate,
    SystemConfigSetting,
)
