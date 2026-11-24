import { correctionPage } from '../services/platform/correctionAccess'
import type { Router } from 'vue-router'
import { navigationError, failedDestination } from '../stores/errorState'
import { AppError, safeReturn } from '../services/common/errors'

import { allowedWorkbench } from '../types/dashboard'
import { currentActor, refreshIdentity } from '../stores/session'
import { hasSession } from '../services/platform/http'
import { profile, refreshProfile } from '../services/platform/auth'
import { requiredPermission } from '../services/platform/permissions'
import { pageAvailability } from '../services/platform/availability'
export function installRouterGuards(router: Router) {
  router.beforeEach(async to => {
    if (['/login', '/forgot-password', '/identity', '/forbidden', '/not-found'].includes(to.path) || to.path.startsWith('/errors/')) return
    if (!hasSession()) return {path:'/login',query:{redirect:to.fullPath}}
    if (!profile.value) { try { await refreshProfile() } catch { return '/identity' } }
    if (to.meta.workbench) { await refreshIdentity(true); if(!allowedWorkbench(currentActor.value,String(to.meta.workbench))) return '/forbidden' }
    if (correctionPage(to.path)) return
    if (to.path === '/inspection/quality/erp_content') return profile.value?.features?.businessDataCorrection ? undefined : '/forbidden'
    if (['/profile', '/profile/edit', '/change-password', '/dashboard', '/work', '/', '/platform-availability'].includes(to.path) || to.path.startsWith('/dashboard/')) return
    if (to.matched.some(record => record.path.includes(':pathMatch'))) return
    const availability = pageAvailability(to.path)
    if (availability.status === 'removed') return { path: '/platform-availability', query: { destination: to.path } }
    const required = requiredPermission(to.path)
    if (required && !profile.value?.permissions.includes(required)) return '/forbidden'
    if (availability.status === 'pending') return { path: '/platform-availability', query: { destination: to.path } }
    if (!required) return '/forbidden'
  })
  router.onError((cause, to) => {
    failedDestination.value = safeReturn(to.fullPath)
    navigationError.value = new AppError('RESOURCE_LOAD', '页面资源加载失败，请重试；如仍失败，请保留输入后手动刷新页面。', { cause })
  })
  router.afterEach((to, _from, failure) => {
    if (!failure) { navigationError.value = undefined; failedDestination.value = '' }
    document.title = `${String(to.meta.title ?? '工作空间')} · LIMS`
  })
}
