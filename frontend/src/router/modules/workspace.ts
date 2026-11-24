import type { RouteRecordRaw } from 'vue-router'
import { workbenches } from '../../types/dashboard'

export const workspaceRoutes: RouteRecordRaw[] = [
  { path: '/profile', component: () => import('../../views/workspace/ProfileView.vue'), meta: { title: '个人资料' } },
  { path: '/profile/edit', component: () => import('../../views/workspace/ProfileSettingsView.vue'), meta: { title: '编辑个人资料' } },
  ...[...workbenches, { id: 'general', title: '业务工作台' }].map(item => ({ path: `/dashboard/${item.id}`, component: () => import('../../views/workspace/DashboardView.vue'), meta: { title: item.title, workbench: item.id } })),
  { path: '/', redirect: '/dashboard' },
  ...[ ['dashboard', '工作台'], ['work', '我的待办'] ].map(([path, title]) => ({ path: `/${path}`, component: () => import('../../views/workspace/DashboardView.vue'), meta: { title } })),
  { path: '/identity', component: () => import('../../platformSession').then(m => m.SessionDetails), meta: { title: '账号信息' } },
  { path: '/notifications', redirect: { path: '/platform-availability', query: { destination: '/notifications' } } },
  { path: '/platform-availability', component: () => import('../../platformAvailabilityPage').then(m => m.PlatformAvailabilityPage), meta: { title: '入口状态' } },
]
