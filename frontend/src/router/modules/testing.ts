import type { RouteRecordRaw } from 'vue-router'
import { testingPages } from '../navigation/testingNavigation'

const testingPageComponents = {
  '/testing/assignment': () => import('../../views/testing/TestingAssignmentView.vue'),
  '/testing/sample-pickup': () => import('../../views/testing/TestingSamplePickupView.vue'),
  '/testing/task-query': () => import('../../views/testing/TestingTaskQueryView.vue'),
  '/testing/data-entry': () => import('../../views/testing/TestingDataEntryView.vue'),
  '/testing/data-check': () => import('../../views/testing/TestingDataCheckView.vue'),
  '/testing/sample-copy': () => import('../../views/testing/TestingSampleCopyView.vue'),
  '/testing/data-query': () => import('../../views/testing/TestingDataQueryView.vue'),
  '/testing/data-changes': () => import('../../views/commissions/CommissionChangesView.vue'),
  '/testing/sample-completion': () => import('../../views/testing/TestingSampleCompletionView.vue'),
} satisfies Record<typeof testingPages[number]['to'], RouteRecordRaw['component']>

export const testingRoutes: RouteRecordRaw[] = [
  { path: '/testing/data-changes/:id/report', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { changeMode: true, reportOnly: true }, meta: { title: '报告填写', permissionModule: 'tasks' } },
  { path: '/testing/data-changes/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { changeMode: true }, meta: { title: '检测数据更改', permissionModule: 'tasks' } },
  { path: '/testing/data-query/:id/print', component: () => import('../../views/testing/TaskPrintView.vue'), meta: { title: '打印任务单', permissionModule: 'tasks' } },
  { path: '/testing/data-query/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { queryMode: true }, meta: { title: '查看检测数据', permissionModule: 'tasks' } },
  { path: '/testing/data-check/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { checkMode: true }, meta: { title: '数据校核', permissionModule: 'tasks' } },
  { path: '/testing/data-entry/:id/report', component: () => import('../../views/testing/DataEntryRecordView.vue'), props: { reportOnly: true }, meta: { title: '报告填写', permissionModule: 'tasks' } },
  { path: '/testing/data-entry/:id', component: () => import('../../views/testing/DataEntryRecordView.vue'), beforeEnter: to => {
    if (to.query.tab !== 'report') return
    const { tab: _tab, ...query } = to.query
    return { path: `${to.path}/report`, query, replace: true }
  }, meta: { title: '检测数据录入', permissionModule: 'tasks' } },
  { path: '/testing/assignment/:id/print', component: () => import('../../views/testing/TaskPrintView.vue'), meta: { title: '打印任务单', permissionModule: 'tasks' } },
  { path: '/testing/task-query/:id/print', component: () => import('../../views/testing/TaskPrintView.vue'), meta: { title: '打印任务单', permissionModule: 'tasks' } },
  ...testingPages.map(page => ({
    path: page.to,
    component: testingPageComponents[page.to],
    props: page.to === '/testing/data-changes' ? { testingMode: true } : undefined,
    meta: { title: page.label, permissionModule: page.module },
  })),
]
