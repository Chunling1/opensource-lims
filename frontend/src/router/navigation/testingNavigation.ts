// Names and order follow the 检测管理 section of docs/菜单.txt.
export const testingPages = [
  { label: '检测任务分配', to: '/testing/assignment', icon: 'ti ti-checklist', module: 'tasks' },
  { label: '检测样品领取', to: '/testing/sample-pickup', icon: 'ti ti-package-export', module: 'tasks' },
  { label: '检测任务查询', to: '/testing/task-query', icon: 'ti ti-search', module: 'tasks' },
  { label: '检测数据录入', to: '/testing/data-entry', icon: 'ti ti-edit', module: 'tasks' },
  { label: '检测数据校核', to: '/testing/data-check', icon: 'ti ti-circle-check', module: 'tasks' },
  { label: '复制样品数据', to: '/testing/sample-copy', icon: 'ti ti-copy', module: 'tasks' },
  { label: '检测数据查询', to: '/testing/data-query', icon: 'ti ti-file-search', module: 'tasks' },
  { label: '检测数据更改', to: '/testing/data-changes', icon: 'ti ti-edit', module: 'tasks' },
  { label: '检毕样品处理', to: '/testing/sample-completion', icon: 'ti ti-flask', module: 'tasks' },
] as const
