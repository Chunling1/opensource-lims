import type { NavigationItem } from './navigation'

// Names, nesting and order follow the 报告管理 section of docs/菜单.txt.
export const reportPages: NavigationItem[] = [
  { label: '报告审核', to: '/reports/review', icon: 'ti ti-circle-check', module: 'reports' },
  { label: '报告批准', to: '/reports/approval', icon: 'ti ti-shield-check', module: 'reports' },
  { label: '报告签发', to: '/reports/print', icon: 'ti ti-printer', module: 'reports' },
  { label: '我的签署', to: '/reports/signing', icon: 'ti ti-writing', module: 'reports' },
  { label: '报告归档', to: '/reports/archive', icon: 'ti ti-archive', module: 'reports' },
  { label: '报告发放', to: '/reports/distribution', icon: 'ti ti-send', module: 'reports' },
  { label: '报告查询', to: '/reports/query', icon: 'ti ti-search', module: 'reports' },
  { label: '报告更改申请', to: '/reports/changes', icon: 'ti ti-edit', module: 'reports', children: [
    { label: '内部申请', to: '/reports/changes/internal', icon: 'ti ti-file-pencil', module: 'reports' },
    { label: '外部申请', to: '/reports/changes/external', icon: 'ti ti-file-pencil', module: 'reports' },
  ] },
]
