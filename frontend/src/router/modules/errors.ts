import type { RouteRecordRaw } from 'vue-router'
import ErrorView from '../../views/errors/ErrorView.vue'

// Keep error pages available even when a lazy-loaded business chunk fails.
export const errorRoutes: RouteRecordRaw[] = [
  { path: '/forbidden', component: ErrorView, meta: { title: '无权访问', errorStatus: 403 } },
  { path: '/errors/:code(400|401|403|404|500|503)', component: ErrorView, meta: { title: '错误提示', layout: 'workspace' } },
  { path: '/errors/:code(400|401|403|404|500|503)/standalone', component: ErrorView, meta: { title: '错误提示', layout: 'standalone' } },
  { path: '/:pathMatch(.*)*', component: ErrorView, meta: { title: '页面不存在', errorStatus: 404 } },
]
