export type BusinessArea = 'inspection' | 'online' | 'experiment'

export type PageType =
  | 'dashboard'
  | 'standard'
  | 'report'
  | 'contract_review'
  | 'sample_inbound'
  | 'sample_outbound'
  | 'sample_register'
  | 'entrust_change'
  | 'change_form'
  | 'data_entry'
  | 'portal'
  | 'approval'
  | 'integration'
  | 'template'
  | 'collection'
  | 'notification'
  | 'auth'
  | 'org'
  | 'std_library'
  | 'equipment_ledger'
  | 'personnel'
  | 'project_config'
  | 'eln_gateway'
  | 'bim_cad_lab'
  | 'esign'
  | 'esign_settings'
  | 'template_mapping'

export interface PageConfig {
  key: string
  name: string
  path: string
  type: PageType
  permission: string
  hidden?: boolean // 仅生成路由、不在侧栏/页签展示（如工作流内部节点，经待办进入）
}

export interface ModuleConfig {
  area: BusinessArea
  areaName: string
  key: string
  name: string
  path: string
  permission: string
  pages: PageConfig[]
}

const page = (
  area: BusinessArea,
  moduleKey: string,
  key: string,
  name: string,
  type: PageType = 'standard',
  hidden = false,
): PageConfig => ({
  key,
  name,
  type,
  path: `/${area}/${moduleKey}/${key}`,
  permission: `${moduleKey}.${key}.view`,
  hidden,
})

export const modules: ModuleConfig[] = [
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'dashboard',
    name: '首页',
    path: '/inspection/dashboard',
    permission: 'dashboard.view',
    pages: [
      {
        key: 'home',
        name: '首页',
        path: '/inspection/dashboard',
        type: 'dashboard',
        permission: 'dashboard.view',
      },
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'entrust',
    name: '委托管理',
    path: '/inspection/entrust',
    permission: 'entrust.view',
    pages: [
      page('inspection', 'entrust', 'registration', '委托登记'),
      page('inspection', 'entrust', 'sample_register', '样品登记', 'sample_register'),
      page('inspection', 'entrust', 'contract_review', '合同评审', 'contract_review'),
      page('inspection', 'entrust', 'query', '委托查询'),
      page('inspection', 'entrust', 'change', '委托更改', 'change_form'),
      page('inspection', 'entrust', 'void_approval', '作废审批'),
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'sample',
    name: '样品管理',
    path: '/inspection/sample',
    permission: 'sample.view',
    pages: [
      page('inspection', 'sample', 'inbound', '样品入库', 'sample_inbound'),
      page('inspection', 'sample', 'outbound', '样品出库', 'sample_outbound'),
      page('inspection', 'sample', 'change', '样品更改', 'change_form'),
      page('inspection', 'sample', 'disposal', '样品处置'),
      page('inspection', 'sample', 'flow_query', '样品流转查询'),
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'testing',
    name: '检测管理',
    path: '/inspection/testing',
    permission: 'testing.view',
    pages: [
      // 菜单保留：检测任务查询 / 检测数据录入 / 检测数据更改；其余为工作流内部节点（路由保留，经待办进入）
      page('inspection', 'testing', 'assignment', '检测任务分配', 'standard', true),
      page('inspection', 'testing', 'sample_pickup', '检测样品领取', 'standard', true),
      page('inspection', 'testing', 'task_query', '检测任务查询'),
      page('inspection', 'testing', 'data_entry', '检测数据录入', 'data_entry'),
      page('inspection', 'testing', 'data_check', '检测数据校核', 'standard', true),
      // 检测数据更改：与检测数据录入同页，列「检测更改中」单据，提交为「检测更改完成」
      page('inspection', 'testing', 'data_change', '检测数据更改', 'data_entry'),
      page('inspection', 'testing', 'completed_sample_handling', '检毕样品处理', 'standard', true),
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'report',
    name: '报告管理',
    path: '/inspection/report',
    permission: 'report.view',
    pages: [
      page('inspection', 'report', 'review', '报告审核', 'report'),
      page('inspection', 'report', 'approval', '报告批准', 'report'),
      page('inspection', 'report', 'print', '报告签发', 'report'),
      {
        key: 'signing', name: '我的签署', path: '/inspection/report/signing',
        type: 'esign', permission: 'report.view',
      },
      page('inspection', 'report', 'archive', '报告归档', 'report'),
      page('inspection', 'report', 'release', '报告发放', 'report'),
      page('inspection', 'report', 'query', '报告查询', 'report'),
      page('inspection', 'report', 'change_request', '报告更改申请', 'report'),
      // 工作流内部节点：合同评审在委托管理中，经待办进入。
      page('inspection', 'report', 'contract_review', '合同评审', 'contract_review', true),
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'quality',
    name: '质量体系',
    path: '/inspection/quality',
    permission: 'quality.view',
    pages: [
      page('inspection', 'quality', 'equipment_ledger', '设备台账', 'equipment_ledger'),
      page('inspection', 'quality', 'standard_library', '检测标准基础信息库', 'std_library'),
    ],
  },
  {
    area: 'inspection',
    areaName: '检测管理信息服务',
    key: 'system',
    name: '系统管理',
    path: '/inspection/system',
    permission: 'system.view',
    pages: [
      page('inspection', 'system', 'org', '组织机构', 'org'),
      {
        key: 'personnel_registration',
        name: '人员登记',
        path: '/inspection/quality/personnel_registration',
        type: 'personnel',
        permission: 'quality.personnel_registration.view',
      },
      page('inspection', 'system', 'custom_project', '检测项目自定义', 'project_config'),
      {
        key: 'esign_settings',
        name: '电子签章设置',
        path: '/inspection/system/esign_settings',
        type: 'esign_settings',
        permission: 'system.view',
      },
      {
        key: 'template_mapping',
        name: '模板与字段映射',
        path: '/inspection/system/template_mapping',
        type: 'template_mapping',
        permission: 'system.view',
      },
    ],
  },
]

export const businessAreas = [
  { key: 'inspection' as const, name: '检测管理信息服务', path: '/inspection/dashboard' },
]

export function findModuleByPath(path: string) {
  return modules.find((module) => path === module.path || module.pages.some((pageItem) => pageItem.path === path))
}

export function findPageByPath(path: string) {
  for (const module of modules) {
    const pageItem = module.pages.find((item) => item.path === path)
    if (pageItem) return pageItem
    if (module.path === path) return module.pages[0]
  }
  return modules[0].pages[0]
}
