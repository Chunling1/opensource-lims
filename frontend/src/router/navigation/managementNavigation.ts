import type { NavigationGroup } from './navigation'

// Names, order and nesting follow docs/菜单.txt. These pages intentionally have no business content.
export const managementGroups: NavigationGroup[] = [
  { id: 'customers', label: '客户管理', section: 'management', icon: 'ti ti-users-group', children: [
    { label: "账号管理", to: "/customers/accounts", icon: "ti ti-users-group", module: "customers" },
    { label: "工程登记", to: "/customers/projects", icon: "ti ti-users-group", module: "customers" },
    { label: "工程备案", to: "/customers/registration", icon: "ti ti-users-group", module: "customers" },
    { label: "客户单位", to: "/customers/organizations", icon: "ti ti-users-group", children: [
      { label: "委托单位", to: "/customers/organizations/principals", icon: "ti ti-users-group", module: "customers" },
    ] },
    { label: "客户人员", to: "/customers/contacts", icon: "ti ti-users-group", children: [
      { label: "委托人", to: "/customers/contacts/clients", icon: "ti ti-users-group", module: "customers" },
      { label: "见证人", to: "/customers/contacts/witnesses", icon: "ti ti-users-group", module: "customers" },
    ] },
    { label: "工程部位", to: "/customers/project-parts", icon: "ti ti-users-group", module: "customers" },
    { label: "生产厂家", to: "/customers/manufacturers", icon: "ti ti-users-group", module: "customers" },
  ] },
  { id: 'quality', label: '质量体系', section: 'management', icon: 'ti ti-shield-check', children: [
    { label: "人员管理", to: "/quality/personnel", icon: "ti ti-shield-check", children: [
      { label: "人员登记", to: "/quality/personnel/registration", icon: "ti ti-shield-check", module: "personnel" },
      { label: "上岗证信息", to: "/quality/personnel/certificates", icon: "ti ti-shield-check", module: "personnel" },
      { label: "人员查询", to: "/quality/personnel/query", icon: "ti ti-shield-check", module: "personnel" },
    ] },
    { label: "仪器设备管理", to: "/quality/equipment", icon: "ti ti-shield-check", children: [
      { label: "设备台账", to: "/quality/equipment/ledger", icon: "ti ti-shield-check", module: "equipment" },
      { label: "设备台账[部门]", to: "/quality/equipment/department-ledger", icon: "ti ti-shield-check", module: "equipment" },
      { label: "月检定计划", to: "/quality/equipment/monthly-calibration", icon: "ti ti-shield-check", module: "equipment" },
      { label: "月检定计划[部门]", to: "/quality/equipment/department-monthly-calibration", icon: "ti ti-shield-check", module: "equipment" },
      { label: "设备分组定义", to: "/quality/equipment/groups", icon: "ti ti-shield-check", module: "equipment" },
      { label: "设备管理计划", to: "/quality/equipment/plans", icon: "ti ti-shield-check", children: [
        { label: "设备总体计划", to: "/quality/equipment/plans/overall", icon: "ti ti-shield-check", module: "equipment" },
        { label: "设备期间核查计划", to: "/quality/equipment/plans/interim", icon: "ti ti-shield-check", module: "equipment" },
        { label: "计量器具周期检定计划", to: "/quality/equipment/plans/calibration", icon: "ti ti-shield-check", module: "equipment" },
      ] },
      { label: "领用与归还", to: "/quality/equipment/loans", icon: "ti ti-shield-check", module: "equipment" },
      { label: "领用与归还记录", to: "/quality/equipment/loan-records", icon: "ti ti-shield-check", module: "equipment" },
      { label: "供应商及评价", to: "/quality/equipment/suppliers", icon: "ti ti-shield-check", module: "suppliers" },
      { label: "标准物质登记", to: "/quality/equipment/reference-materials", icon: "ti ti-shield-check", module: "inventory" },
      { label: "设备类型", to: "/quality/equipment/types", icon: "ti ti-shield-check", module: "equipment" },
      { label: "易耗品", to: "/quality/equipment/consumables", icon: "ti ti-shield-check", module: "inventory" },
      { label: "设备维护费用", to: "/quality/equipment/maintenance-costs", icon: "ti ti-shield-check", module: "equipment" },
    ] },
    { label: "文件管理", to: "/quality/documents", icon: "ti ti-shield-check", children: [
      { label: "文件基础信息库", to: "/quality/documents/library", icon: "ti ti-shield-check", module: "documents" },
      { label: "质量监控计划", to: "/quality/documents/monitoring", icon: "ti ti-shield-check", module: "documents" },
    ] },
    { label: "检测标准管理", to: "/quality/standards", icon: "ti ti-shield-check", children: [
      { label: "标准分组定义", to: "/quality/standards/groups", icon: "ti ti-shield-check", module: "documents" },
      { label: "检测标准基础信息库", to: "/quality/standards/library", icon: "ti ti-shield-check", module: "documents" },
      { label: "检测标准基础信息库[科室]", to: "/quality/standards/department-library", icon: "ti ti-shield-check", module: "documents" },
    ] },
    { label: "检测试验环境", to: "/quality/environment", icon: "ti ti-shield-check", module: "qualityCases" },
    { label: "日常事务申请", to: "/quality/requests", icon: "ti ti-shield-check", module: "dailyRequests" },
    { label: "日常事务审批", to: "/quality/approvals", icon: "ti ti-shield-check", module: "dailyApprovals" },
  ] },
  { id: 'system', label: '系统管理', section: 'management', icon: 'ti ti-settings', children: [
    { label: "系统维护", to: "/system/maintenance", icon: "ti ti-settings", children: [
      { label: "数据初始化", to: "/system/maintenance/initialization", icon: "ti ti-settings", module: "settings" },
      { label: "异常数据处理", to: "/system/maintenance/exceptions", icon: "ti ti-settings", module: "settings" },
      { label: "超期和预警计算", to: "/system/maintenance/alerts", icon: "ti ti-settings", module: "settings" },
      { label: "发布公告", to: "/system/maintenance/announcements", icon: "ti ti-settings", module: "settings" },
      { label: "系统数据维护", to: "/system/maintenance/data", icon: "ti ti-settings", module: "settings" },
    ] },
    { label: "系统设置", to: "/system/settings", icon: "ti ti-settings", children: [
      { label: "系统运行参数设置", to: "/system/settings/parameters", icon: "ti ti-settings", module: "settings" },
      { label: "系统风格设置", to: "/system/settings/style", icon: "ti ti-settings", module: "settings" },
      { label: "编号格式定义", to: "/system/settings/numbering", icon: "ti ti-settings", module: "settings" },
      { label: "审批设置", to: "/system/settings/approvals", icon: "ti ti-settings", module: "settings" },
      { label: "检测项目流程自定义", to: "/system/settings/project-workflows", icon: "ti ti-settings", module: "settings" },
      { label: "数据字典", to: "/system/settings/dictionaries", icon: "ti ti-settings", module: "settings" },
      { label: "报告设置", to: "/system/settings/reports", icon: "ti ti-settings", module: "settings" },
    ] },
    { label: "检测项目", to: "/system/projects", icon: "ti ti-settings", children: [
      { label: "检测项目分类树管理", to: "/system/projects/categories", icon: "ti ti-settings", module: "settings" },
      { label: "检测项目自定义", to: "/system/projects/custom", icon: "ti ti-settings", module: "settings" },
      { label: "检测项目综合设置", to: "/system/projects/comprehensive", icon: "ti ti-settings", module: "settings" },
      { label: "检测项目分类设置", to: "/system/projects/classification", icon: "ti ti-settings", children: [
        { label: "基本信息", to: "/system/projects/classification/basic", icon: "ti ti-settings", module: "settings" },
        { label: "承诺时间", to: "/system/projects/classification/deadlines", icon: "ti ti-settings", module: "settings" },
        { label: "操作控制", to: "/system/projects/classification/controls", icon: "ti ti-settings", module: "settings" },
        { label: "录入默认", to: "/system/projects/classification/defaults", icon: "ti ti-settings", module: "settings" },
        { label: "试验设备", to: "/system/projects/classification/equipment", icon: "ti ti-settings", module: "settings" },
        { label: "试验环境", to: "/system/projects/classification/environment", icon: "ti ti-settings", module: "settings" },
        { label: "检测参数", to: "/system/projects/classification/parameters", icon: "ti ti-settings", module: "settings" },
        { label: "组号分配", to: "/system/projects/classification/numbering", icon: "ti ti-settings", module: "settings" },
      ] },
      { label: "同步项目设置", to: "/system/projects/synchronization", icon: "ti ti-settings", module: "settings" },
    ] },
    { label: "短信管理", to: "/system/sms", icon: "ti ti-settings", children: [
      { label: "发送短信", to: "/system/sms/send", icon: "ti ti-settings", module: "settings" },
      { label: "短信查询", to: "/system/sms/query", icon: "ti ti-settings", module: "settings" },
      { label: "短信设置", to: "/system/sms/settings", icon: "ti ti-settings", module: "settings" },
    ] },
    { label: "机构管理", to: "/system/institutions", icon: "ti ti-settings", children: [
      { label: "站点管理", to: "/system/institutions/stations", icon: "ti ti-settings", module: "settings" },
      { label: "检测场所", to: "/system/institutions/sites", icon: "ti ti-settings", module: "settings" },
    ] },
    { label: "组织机构管理", to: "/system/organization", icon: "ti ti-settings", module: "settings" },
    { label: "用户管理", to: "/system/users", icon: "ti ti-settings", module: "settings" },
    { label: "工作日历管理", to: "/system/calendar", icon: "ti ti-settings", module: "settings" },
    { label: "日志查询", to: "/system/logs", icon: "ti ti-settings", children: [
      { label: "操作日志", to: "/system/logs/operations", icon: "ti ti-settings", module: "settings" },
      { label: "授权日志", to: "/system/logs/authorizations", icon: "ti ti-settings", module: "settings" },
    ] },
  ] },
]
