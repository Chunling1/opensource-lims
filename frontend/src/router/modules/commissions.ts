import type { RouteRecordRaw } from 'vue-router'
import { commissionPages } from '../navigation/commissionNavigation'

const commissionPageComponents = {
  '/commissions/registration': () => import('../../views/commissions/RegistrationView.vue'),
  '/commissions/review': () => import('../../views/commissions/ContractReviewView.vue'),
  '/commissions/query': () => import('../../views/commissions/CommissionQueryView.vue'),
  '/commissions/changes': () => import('../../views/commissions/CommissionChangesView.vue'),
  '/commissions/cancellation-approval': () => import('../../views/commissions/CancellationApprovalView.vue'),
} satisfies Record<typeof commissionPages[number]['to'], RouteRecordRaw['component']>

export const commissionRoutes: RouteRecordRaw[] = [
  { path: '/commissions/registration/samples/bulk-edit', component: () => import('../../views/commissions/RegistrationBulkCommissionView.vue'), meta: { title: '批量修改委托信息', permissionModule: 'commissions' } },
  { path: '/commissions/registration/:kind(commissions|samples)/:id/print', component: () => import('../../views/commissions/RegistrationPrintView.vue'), meta: { title: '打印委托单', permissionModule: 'commissions' } },
  { path: '/commissions/registration/:kind(commissions|samples)/:id/edit', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '修改登记资料', permissionModule: 'commissions', viewKey: 'registration-record' } },
  { path: '/commissions/registration/:kind(commissions|samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '登记资料', permissionModule: 'commissions', viewKey: 'registration-record' } },
  { path: '/commissions/review/:kind(commissions|samples)/new', redirect: '/commissions/review' },
  { path: '/commissions/review/:kind(commissions|samples)/new/edit', redirect: '/commissions/review' },
  { path: '/commissions/review/:kind(samples)/:id/assess', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '评审样品', permissionModule: 'commissions', viewKey: 'review-record' } },
  { path: '/commissions/review/samples/bulk-edit', component: () => import('../../views/commissions/RegistrationBulkCommissionView.vue'), meta: { title: '批量修改委托信息', permissionModule: 'commissions' } },
  { path: '/commissions/review/:kind(commissions|samples)/:id/print', component: () => import('../../views/commissions/RegistrationPrintView.vue'), meta: { title: '打印委托单', permissionModule: 'commissions' } },
  { path: '/commissions/review/:kind(commissions|samples)/:id/edit', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '修改登记资料', permissionModule: 'commissions', viewKey: 'review-record' } },
  { path: '/commissions/review/:kind(commissions|samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '登记资料', permissionModule: 'commissions', viewKey: 'review-record' } },
  { path: '/commissions/query/samples/bulk-edit', redirect: '/commissions/query' },
  { path: '/commissions/query/:kind(commissions|samples)/new', redirect: '/commissions/query' },
  { path: '/commissions/query/:kind(commissions|samples)/new/edit', redirect: '/commissions/query' },
  { path: '/commissions/query/:kind(commissions|samples)/:id/edit', redirect: to => ({ path: `/commissions/query/${to.params.kind}/${to.params.id}`, query: to.query }) },
  { path: '/commissions/query/:kind(samples)/:id/assess', redirect: to => ({ path: `/commissions/query/samples/${to.params.id}`, query: to.query }) },
  { path: '/commissions/query/:kind(commissions|samples)/:id/print', component: () => import('../../views/commissions/RegistrationPrintView.vue'), meta: { title: '打印委托单', permissionModule: 'commissions' } },
  { path: '/commissions/query/:kind(commissions|samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '委托查询详情', permissionModule: 'commissions', viewKey: 'query-record' } },
  { path: '/commissions/changes/:kind(samples)/new', redirect: '/commissions/changes' },
  { path: '/commissions/changes/:kind(samples)/new/edit', redirect: '/commissions/changes' },
  { path: '/commissions/changes/:kind(samples)/:id/edit', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '更改样品', permissionModule: 'commissions', viewKey: 'change-record' } },
  { path: '/commissions/changes/:kind(samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '样品详情', permissionModule: 'commissions', viewKey: 'change-record' } },
  ...commissionPages.map(page => ({ path: page.to, component: commissionPageComponents[page.to], meta: { title: page.label, permissionModule: page.module } })),
]
