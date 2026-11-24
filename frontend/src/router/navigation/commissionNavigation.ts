// Based on docs/菜单.txt; the review label follows the latest requested wording.
export const commissionPages = [
  { label: '委托登记', to: '/commissions/registration', icon: 'ti ti-file-plus', module: 'commissions' },
  { label: '合同评审', to: '/commissions/review', icon: 'ti ti-file-check', module: 'commissions' },
  { label: '委托查询', to: '/commissions/query', icon: 'ti ti-search', module: 'commissions' },
  { label: '委托更改', to: '/commissions/changes', icon: 'ti ti-edit', module: 'commissions' },
  { label: '作废审批', to: '/commissions/cancellation-approval', icon: 'ti ti-circle-x', module: 'commissions' },
] as const
