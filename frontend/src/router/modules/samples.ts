import { samplePages, samplePageRoles } from '../navigation/sampleNavigation'
import type { RouteRecordRaw } from 'vue-router'

const samplePageComponents = {
  '/samples/inbound': () => import('../../views/samples/SampleInboundView.vue'),
  '/samples/outbound': () => import('../../views/samples/SampleOutboundView.vue'),
  '/samples/disposal': () => import('../../views/samples/SampleDisposalView.vue'),
  '/samples/flow': () => import('../../views/samples/SampleFlowView.vue'),
} satisfies Record<typeof samplePages[number]['to'], RouteRecordRaw['component']>

export const sampleRoutes: RouteRecordRaw[] = [
  { path: '/samples/inbound/:kind(samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '样品详情', permissionRoles: samplePageRoles, viewKey: 'inbound-record' } },
  { path: '/samples/outbound/:kind(samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '样品详情', permissionRoles: samplePageRoles, viewKey: 'outbound-record' } },
  { path: '/samples/disposal/:kind(samples)/:id', component: () => import('../../views/commissions/RegistrationRecordView.vue'), meta: { title: '样品详情', permissionRoles: samplePageRoles, viewKey: 'disposal-record' } },
  ...samplePages.map(page => ({ path: page.to, component: samplePageComponents[page.to], meta: { title: page.label, permissionRoles: samplePageRoles } })),
]
