import type { RouteRecordRaw } from 'vue-router'
import { reportPages } from '../navigation/reportNavigation'
import { flattenNavigation } from '../navigation/navigation'

const reportPageComponents: Record<string, RouteRecordRaw['component']> = {
  '/reports/check': () => import('../../views/reports/ReportStageView.vue'),
  '/reports/review': () => import('../../views/reports/ReportStageView.vue'),
  '/reports/approval': () => import('../../views/reports/ReportStageView.vue'),
  '/reports/print': () => import('../../views/reports/ReportLifecycleView.vue'),
  '/reports/signing': () => import('../../views/reports/ReportLifecycleView.vue'),
  '/reports/archive': () => import('../../views/reports/ReportLifecycleView.vue'),
  '/reports/query': () => import('../../views/reports/ReportQueryView.vue'),
  '/reports/changes/internal': () => import('../../views/reports/ReportInternalChangesView.vue'),
  '/reports/changes/external': () => import('../../views/reports/ReportInternalChangesView.vue'),
}

export const reportRoutes: RouteRecordRaw[] = [
  { path: '/reports/query/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { queryMode: true, reportQueryMode: true }, meta: { title: '查看检测数据', permissionModule: 'reports' } },
  { path: '/reports/archive/:id/print-task', component: () => import('../../views/testing/TaskPrintView.vue'), meta: { title: '打印任务单', permissionModule: 'reports' } },
  { path: '/reports/archive/:id/print-commission', component: () => import('../../views/commissions/RegistrationPrintView.vue'), meta: { title: '打印委托书', permissionModule: 'reports' } },
  { path: '/reports/check/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { checkMode: true, reportCheckMode: true }, meta: { title: '报告校核', permissionModule: 'reports' } },
  { path: '/reports/review/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { checkMode: true, reportCheckMode: true, reportStage: 'review' }, meta: { title: '报告审核', permissionModule: 'reports' } },
  { path: '/reports/approval/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { checkMode: true, reportCheckMode: true, reportStage: 'approval' }, meta: { title: '报告批准', permissionModule: 'reports' } },
  ...flattenNavigation(reportPages, true).map(page => page.to === '/reports/distribution' ? {path: page.to, redirect: '/inspection/report/release'} : page.children ? {
  path: page.to, redirect: page.children[0]!.to,
} : {
  path: page.to,
  component: reportPageComponents[page.to]!,
  meta: { title: page.label, permissionModule: page.module },
}),
]
