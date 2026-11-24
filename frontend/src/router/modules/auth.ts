import type { RouteRecordRaw } from 'vue-router'

export const authRoutes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('../../views/auth/LoginView.vue'), meta: { title: '用户登录', layout: 'standalone', public: true, guestOnly: true } },
  { path: '/forgot-password', component: () => import('../../views/auth/ForgotPasswordView.vue'), meta: { title: '忘记密码', layout: 'standalone', public: true } },
  { path: '/change-password', redirect: { path: '/profile/edit', query: { tab: 'password' } } },
  { path: '/logout', redirect: '/login', beforeEnter: () => { return '/login' } },
]

export function loginReturn(value: unknown) {
  if (typeof value !== 'string' || !/^\/(?!\/)/.test(value) || /[\\\r\n]/.test(value)) return '/dashboard'
  let decoded: string
  try { decoded = decodeURIComponent(value) } catch { return '/dashboard' }
  if (/[\\\r\n]/.test(decoded) || decoded.startsWith('//') || /^\/(?:login|logout|forgot-password|change-password|errors|forbidden)(?:[/?#]|$)/.test(decoded)) return '/dashboard'
  return value
}
