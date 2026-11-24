// Names and order follow the 样品管理 section of docs/菜单.txt.
export const samplePageRoles = ['samples', 'commissions', 'testing', 'reviewer', 'approver']
export const samplePages = [
  { label: '样品入库', to: '/samples/inbound', icon: 'ti ti-inbox' },
  { label: '样品出库', to: '/samples/outbound', icon: 'ti ti-package-export' },
  { label: '样品处置', to: '/samples/disposal', icon: 'ti ti-trash' },
  { label: '样品流转查询', to: '/samples/flow', icon: 'ti ti-route' },
] as const
