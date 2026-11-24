import { createRouter, createWebHashHistory } from 'vue-router'
import { installRouterGuards } from './guards'
import { commissionRoutes } from './modules/commissions'
import { sampleRoutes } from './modules/samples'
import { testingRoutes } from './modules/testing'
import { reportRoutes } from './modules/reports'
import { managementRoutes } from './modules/management'
import { authRoutes } from './modules/auth'
import { workspaceRoutes } from './modules/workspace'
import { errorRoutes } from './modules/errors'
import { originalPlatformRoutes } from './modules/originalPlatform'
import { clearRegistrationListState, isRegistrationChild, takeRegistrationReturnScroll } from '../services/commissions/registrationListState'

export const router = createRouter({
  history: createWebHashHistory(),
  scrollBehavior: (to, from) => {
    const restored = takeRegistrationReturnScroll(to.fullPath)
    if (restored) return restored
    // Query-only updates preserve registration and print-page scroll positions.
    if (/^\/(?:commissions\/(registration|review|query|changes|cancellation-approval)|samples\/(inbound|outbound|disposal|flow)|testing\/(assignment|sample-pickup|task-query|data-entry))(?:\/|$)/.test(to.path) && from.path === to.path) return false
    // First save promotes the open commission form to its saved URL in place.
    if (/^\/commissions\/registration\/(commissions|samples)\/new$/.test(from.path) && to.path.startsWith(from.path.slice(0, -3)) && /\/[^/]+\/edit$/.test(to.path)) return false
    return { top: 0 }
  },
  routes: [...originalPlatformRoutes, ...authRoutes, ...workspaceRoutes, ...sampleRoutes, ...testingRoutes, ...reportRoutes, ...commissionRoutes, ...managementRoutes, ...errorRoutes],
})

installRouterGuards(router)
router.afterEach((to, _from, failure) => {
  if (!failure && to.path !== '/commissions/registration' && !isRegistrationChild(to.path)) clearRegistrationListState()
})
