"""Target modular-monolith registry.

The registry describes *logical* ownership.  It does not move a table, change
an ORM mapping or authorize a runtime write.  Existing legacy writers remain a
known migration concern; new modular code must depend on the declared owner
through a Command, Query or Event contract instead of importing a legacy
implementation directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Layer = Literal["platform", "domain", "extension"]


@dataclass(frozen=True)
class ModuleContract:
    """One logical module in the target modular monolith."""

    module_id: str
    layer: Layer
    target_package: str
    purpose: str
    owns_tables: tuple[str, ...] = ()
    reads_modules: tuple[str, ...] = ()
    command_surface: tuple[str, ...] = ()
    query_surface: tuple[str, ...] = ()
    event_surface: tuple[str, ...] = ()
    prohibitions: tuple[str, ...] = ()
    legacy_sources: tuple[str, ...] = ()


_IDENTITY_TABLES = (
    "departments",
    "permissions",
    "projects",
    "project_steps",
    "users",
    "user_permissions",
    "user_action_permissions",
    "user_project_permissions",
    "department_permissions",
    "department_project_step_permissions",
    "department_project_permissions",
    "user_standard_denials",
    "user_data_departments",
    "user_data_sites",
)

_REPORT_TABLES = (
    "reports",
    "report_attachments",
    "report_template_profiles",
    "report_document_contents",
    "report_document_versions",
    "report_render_jobs",
    "compliance_acknowledgements",
)

_QUALITY_TABLES = (
    "instruments",
    "instrument_validities",
    "qualifications",
    "qualification_snapshots",
    "standards",
    "std_library_items",
    "capability_import_batches",
    "capability_entries",
    "capability_departments",
    "equipment_items",
    "equipment_schemes",
    "equipment_calibration_records",
    "equipment_usage_records",
    "personnel",
)

_CUSTOMER_TABLES = (
    "external_accounts",
    "external_schemes",
    "external_entrust_applications",
    "external_entrust_events",
    "external_customer_documents",
    "external_shipments",
    "external_portal_notifications",
)

_ELN_TABLES = (
    "eln_project_configs",
    "eln_record_templates",
    "eln_launch_codes",
    "eln_task_policies",
    "eln_original_records",
    "eln_record_revisions",
)

_AI_TABLES = (
    "ai_search_documents",
    "ai_search_terms",
    "ai_index_state",
    "ai_search_dictionary",
)


MODULE_REGISTRY: dict[str, ModuleContract] = {
    "platform_identity": ModuleContract(
        module_id="platform_identity",
        layer="platform",
        target_package="app.platform.identity",
        purpose="身份、功能权限、数据范围、部门上限和项目步骤授权的唯一策略入口。",
        owns_tables=_IDENTITY_TABLES,
        command_surface=("manage_user", "grant_department_scope", "grant_project_step"),
        query_surface=("current_actor", "business_scope", "project_step_access"),
        event_surface=("identity.permission_changed", "identity.scope_changed"),
        prohibitions=(
            "用户管理权限不得隐式扩大业务数据范围",
            "不得把前端缓存当作授权事实",
        ),
        legacy_sources=("app.authorization_scope", "app.blueprints.admin"),
    ),
    "workflow_core": ModuleContract(
        module_id="workflow_core",
        layer="platform",
        target_package="app.platform.workflow",
        purpose="统一状态转换、办理可见性、撤回规则和待办投影；不拥有领域业务表。",
        reads_modules=("platform_identity", "audit_trace"),
        command_surface=("transition", "withdraw", "return_for_change"),
        query_surface=("visible_work_items", "allowed_transitions"),
        event_surface=("workflow.transitioned", "workflow.withdrawn"),
        prohibitions=("不得绕过领域校验直接更新状态",),
        legacy_sources=("app.status_machine", "app.project_workflow"),
    ),
    "audit_trace": ModuleContract(
        module_id="audit_trace",
        layer="platform",
        target_package="app.platform.audit",
        purpose="事务内记录操作者、动作、原因、前后值、时间和 traceId。",
        owns_tables=("operation_audits",),
        reads_modules=("platform_identity",),
        command_surface=("record_operation",),
        query_surface=("operation_history", "completion_owner"),
        event_surface=("audit.recorded",),
        prohibitions=("业务模块不得修改既有审计记录",),
        legacy_sources=("app.audit",),
    ),
    "file_vault": ModuleContract(
        module_id="file_vault",
        layer="platform",
        target_package="app.platform.file_vault",
        purpose="文件持久化、元数据、完整性、所有权和安全读取的统一入口。",
        owns_tables=("stored_files",),
        reads_modules=("platform_identity", "audit_trace"),
        command_surface=("store_file", "mark_file_deleted"),
        query_surface=("read_owned_file", "file_metadata"),
        event_surface=("file.stored", "file.deleted"),
        prohibitions=("不得由业务模块直接拼接或删除存储路径",),
        legacy_sources=("app.functions.stored_files",),
    ),
    "business_numbering": ModuleContract(
        module_id="business_numbering",
        layer="platform",
        target_package="app.platform.numbering",
        purpose="单调、不复用的委托、样品、报告和外部申请编号。",
        owns_tables=("business_number_sequences",),
        reads_modules=("audit_trace",),
        command_surface=("allocate_number",),
        query_surface=("peek_number",),
        event_surface=("number.allocated",),
        prohibitions=("不得通过删除业务记录回退或复用编号",),
        legacy_sources=("app.numbering",),
    ),
    "entrust_contract": ModuleContract(
        module_id="entrust_contract",
        layer="domain",
        target_package="app.domains.entrust",
        purpose="委托登记、合同评审和正式委托快照。",
        owns_tables=("entrusts",),
        reads_modules=(
            "platform_identity", "workflow_core", "audit_trace",
            "business_numbering", "quality_resources",
        ),
        command_surface=(
            "complete_entrust",
            "review_contract",
            "create_external_portal_entrust",
        ),
        query_surface=("entrust_query", "entrust_snapshot"),
        event_surface=("entrust.completed", "contract.reviewed"),
        prohibitions=("后续模块不得修改已形成的委托快照",),
        legacy_sources=("app.blueprints.entrust",),
    ),
    "sample_logistics": ModuleContract(
        module_id="sample_logistics",
        layer="domain",
        target_package="app.domains.sample",
        purpose="样品登记、入库、领取、回库、处置和移动端流转。",
        reads_modules=(
            "platform_identity", "workflow_core", "audit_trace", "file_vault",
            "entrust_contract", "report_lifecycle",
        ),
        command_surface=("register_sample", "receive_sample", "pick_up_sample", "return_sample"),
        query_surface=("sample_work_queue", "sample_lifecycle"),
        event_surface=("sample.registered", "sample.received", "sample.picked_up"),
        prohibitions=(
            "当前 Report 表承载样品状态是待消除的遗留耦合",
            "不得绕过 workflow_core 直接推进报告状态",
        ),
        legacy_sources=("app.blueprints.samples",),
    ),
    "testing_records": ModuleContract(
        module_id="testing_records",
        layer="domain",
        target_package="app.domains.testing",
        purpose="检测任务、数据草稿、完成校验和正式原始记录。",
        reads_modules=(
            "platform_identity", "workflow_core", "audit_trace", "file_vault",
            "sample_logistics", "quality_resources", "report_lifecycle",
        ),
        command_surface=("save_test_draft", "complete_test_data", "submit_original_record"),
        query_surface=("assigned_test_tasks", "test_record"),
        event_surface=("testing.started", "testing.completed", "record.submitted"),
        prohibitions=(
            "普通保存不得执行完成阶段三库校验",
            "不得由 ELN 直接修改报告流程状态",
        ),
        legacy_sources=("app.blueprints.reports",),
    ),
    "report_lifecycle": ModuleContract(
        module_id="report_lifecycle",
        layer="domain",
        target_package="app.domains.report",
        purpose="报告内容、审核、批准、打印、发放、归档和正式文档版本。",
        owns_tables=_REPORT_TABLES,
        reads_modules=(
            "platform_identity", "workflow_core", "audit_trace", "file_vault",
            "business_numbering", "entrust_contract", "testing_records",
            "quality_resources",
        ),
        command_surface=("review_report", "approve_report", "print_report", "release_report", "archive_report"),
        query_surface=("report_work_queue", "report_query", "report_document"),
        event_surface=("report.reviewed", "report.approved", "report.released"),
        prohibitions=(
            "不恢复报告校核节点",
            "非拥有模块不得直接写 reports 状态字段",
        ),
        legacy_sources=("app.blueprints.reports", "app.report_documents"),
    ),
    "quality_resources": ModuleContract(
        module_id="quality_resources",
        layer="domain",
        target_package="app.domains.quality",
        purpose="标准、能力、设备、人员及合规只读投影。",
        owns_tables=_QUALITY_TABLES,
        reads_modules=("platform_identity", "audit_trace", "file_vault"),
        command_surface=("maintain_standard", "maintain_capability", "maintain_equipment"),
        query_surface=("authorized_standards", "capability_check", "equipment_validity"),
        event_surface=("standard.changed", "equipment.restricted"),
        prohibitions=("质量资源查询不得自行扩大部门授权",),
        legacy_sources=("app.blueprints.quality", "app.standard_control"),
    ),
    "finance_billing": ModuleContract(
        module_id="finance_billing",
        layer="domain",
        target_package="app.domains.finance",
        purpose="计价、收款、确认、开票、结算和退款。",
        owns_tables=("finance_bills",),
        reads_modules=("platform_identity", "workflow_core", "audit_trace", "entrust_contract"),
        command_surface=("price", "register_payment", "issue_invoice", "settle", "refund"),
        query_surface=("finance_work_queue", "finance_query"),
        event_surface=("finance.invoiced", "finance.settled"),
        prohibitions=("办理列表不得借查询参数查看其他节点状态",),
        legacy_sources=("app.blueprints.finance", "app.finance_service"),
    ),
    "customer_service": ModuleContract(
        module_id="customer_service",
        layer="extension",
        target_package="app.adapters.portal",
        purpose="客户自助委托、进度、文件、物流和通知聚合。",
        owns_tables=_CUSTOMER_TABLES,
        reads_modules=(
            "platform_identity", "audit_trace", "file_vault", "quality_resources",
            "entrust_contract", "report_lifecycle", "finance_billing",
        ),
        command_surface=("submit_external_application", "accept_external_application"),
        query_surface=("customer_workspace", "customer_progress"),
        event_surface=("customer.application_submitted",),
        prohibitions=("不得直接写正式委托、报告或财务状态",),
        legacy_sources=("app.blueprints.public_portal",),
    ),
    "eln_adapter": ModuleContract(
        module_id="eln_adapter",
        layer="extension",
        target_package="app.adapters.eln",
        purpose="ELN 会话、模板、原始记录版本和检测任务适配。",
        owns_tables=_ELN_TABLES,
        reads_modules=(
            "platform_identity", "audit_trace", "file_vault", "testing_records",
            "quality_resources",
        ),
        command_surface=("save_eln_record", "submit_eln_record"),
        query_surface=("eln_tasks", "eln_record_history"),
        event_surface=("eln.record_submitted", "eln.record_reviewed"),
        prohibitions=("不得直接修改 Report、Entrust 或样品流程状态",),
        legacy_sources=("app.blueprints.eln", "app.blueprints.eln_integration"),
    ),
    "intelligence": ModuleContract(
        module_id="intelligence",
        layer="extension",
        target_package="app.adapters.ai",
        purpose="权限内索引、搜索、语音和只读业务分析。",
        owns_tables=_AI_TABLES,
        reads_modules=(
            "platform_identity", "audit_trace", "entrust_contract", "sample_logistics",
            "testing_records", "report_lifecycle", "quality_resources", "finance_billing",
        ),
        query_surface=("search", "read_only_analysis"),
        event_surface=("ai.indexed",),
        prohibitions=(
            "不得保存、完成、审核、批准或推进任何核心业务流程",
            "不得直接连接或批量外传业务数据库",
        ),
        legacy_sources=("app.blueprints.ai", "app.functions.ai_index", "app.functions.ai_analysis"),
    ),
    "integration_adapters": ModuleContract(
        module_id="integration_adapters",
        layer="extension",
        target_package="app.adapters.integrations",
        purpose="外部ERP、短信、邮件、WPS、迁移和其他外部系统防腐层。",
        owns_tables=(
            "data_migration_batches", "legacy_import_batches",
            "legacy_import_rows", "legacy_import_conflicts",
        ),
        reads_modules=(
            "platform_identity", "audit_trace", "file_vault", "entrust_contract",
            "sample_logistics", "testing_records", "report_lifecycle",
            "quality_resources", "finance_billing",
        ),
        command_surface=("dispatch_integration_command",),
        query_surface=("integration_status",),
        event_surface=("integration.received", "integration.failed"),
        prohibitions=("外部回调不得绕过正式业务 Command",),
        legacy_sources=("app.data_models.reference_imports"),
    ),
    "experiments": ModuleContract(
        module_id="experiments",
        layer="extension",
        target_package="app.adapters.experiments",
        purpose="BIM/CAD/OCR 等隔离实验能力。",
        reads_modules=("platform_identity", "audit_trace", "file_vault"),
        command_surface=("run_experiment",),
        query_surface=("experiment_result",),
        event_surface=("experiment.completed",),
        prohibitions=("实验结果不得直接形成检测结论或推进业务流程",),
        legacy_sources=("app.blueprints.bim_cad",),
    ),
}


# Direct imports that are forbidden once code enters the modular adapter root
# (``app.adapters``).  Legacy source paths above remain facts, not exemptions
# for new code.
FORBIDDEN_LEGACY_ADAPTER_IMPORTS = frozenset({
    "app.authorization_scope",
    "app.status_machine",
    "app.audit",
    "app.numbering",
    "app.functions.stored_files",
})


# Core state stays owned by its domain.  Extensions may request a Command, but
# they may never assign these fields directly.
CORE_STATE_FIELDS: dict[str, frozenset[str]] = {
    "agreements": frozenset({"status"}),
    "entrusts": frozenset({"status"}),
    "reports": frozenset({
        "status", "sample_status", "sample_reg_state", "archive_state", "voided",
    }),
    "finance_bills": frozenset({"status", "version"}),
}


EXTENSION_CORE_WRITE_RULES: dict[str, tuple[str, ...]] = {
    "customer_service": (
        "may write only external_* tables directly",
        "must use entrust_contract commands for formal entrust creation",
    ),
    "eln_adapter": (
        "may write only eln_* tables directly",
        "must use testing_records commands and never set reports.status",
    ),
    "intelligence": (
        "may write only ai_search_* and ai_index_state derived tables",
        "has no core business Command capability",
    ),
    "integration_adapters": (
        "must translate callbacks into owner-module commands",
        "must not update core status columns directly",
    ),
    "experiments": (
        "must keep results isolated until a human-approved business command",
        "must not update core status columns directly",
    ),
}


def module_contract(module_id: str) -> ModuleContract:
    """Return the authoritative contract for *module_id*."""

    return MODULE_REGISTRY[module_id]


def table_owner_map() -> dict[str, str]:
    """Map every registered ORM table to its single logical owner.

    Duplicate ownership is intentionally rejected instead of silently using
    the last declaration.
    """

    result: dict[str, str] = {}
    for module in MODULE_REGISTRY.values():
        for table in module.owns_tables:
            if table in result:
                raise ValueError(
                    f"table {table!r} has multiple owners: "
                    f"{result[table]!r}, {module.module_id!r}"
                )
            result[table] = module.module_id
    return result


def table_reader_map() -> dict[str, frozenset[str]]:
    """Return modules allowed to read each registered table."""

    owners = table_owner_map()
    readers: dict[str, set[str]] = {
        table: {owner} for table, owner in owners.items()
    }
    for module in MODULE_REGISTRY.values():
        for dependency in module.reads_modules:
            for table in MODULE_REGISTRY[dependency].owns_tables:
                readers[table].add(module.module_id)
    return {table: frozenset(values) for table, values in readers.items()}


def registry_payload() -> dict[str, object]:
    """JSON-friendly representation for manifests and architecture reports."""

    return {
        "schemaVersion": "architecture-registry.v1",
        "architecture": "modular-monolith",
        "modules": {
            key: asdict(value) for key, value in MODULE_REGISTRY.items()
        },
        "tableOwners": table_owner_map(),
        "tableReaders": {
            table: sorted(values) for table, values in table_reader_map().items()
        },
        "coreStateFields": {
            table: sorted(values) for table, values in CORE_STATE_FIELDS.items()
        },
        "extensionCoreWriteRules": EXTENSION_CORE_WRITE_RULES,
    }


__all__ = [
    "CORE_STATE_FIELDS",
    "EXTENSION_CORE_WRITE_RULES",
    "FORBIDDEN_LEGACY_ADAPTER_IMPORTS",
    "MODULE_REGISTRY",
    "ModuleContract",
    "module_contract",
    "registry_payload",
    "table_owner_map",
    "table_reader_map",
]
