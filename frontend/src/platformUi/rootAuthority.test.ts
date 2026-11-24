import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSessionStore } from '@/stores/session'
import type { AuthResponse } from '@/services/auth'
import { registrationActions } from './commissions/registrationPresentation'

beforeEach(() => setActivePinia(createPinia()))

function profile(full: boolean): AuthResponse {
  return {
    account: 'root-member', userName: '测试人员', roleKey: 'operator', roleName: '基础用户',
    homePath: '/', dataScope: { department: '示例检测科技有限公司', scopeType: 'all', description: '' },
    permissions: ['entrust.registration.view'], actionPermissions: [],
    features: { fullPlatformAuthority: full },
  }
}

it('uses the server authority flag for administrator operations without changing the stored role', () => {
  const session = useSessionStore()
  session.applyAuth(profile(true))
  expect(session.roleKey).toBe('operator')
  expect(registrationActions({ status: '委托完成', completionAccount: 'other' }, { session })[0].disabled).toBe(false)
  session.applyAuth(profile(false))
  expect(registrationActions({ status: '委托完成', completionAccount: 'other' }, { session })[0].disabled).toBe(true)
})

it('does not infer full authority from a department label or all-data scope and clears it on logout', () => {
  const session = useSessionStore()
  session.applyAuth({ ...profile(false), features: {} })
  expect(session.fullPlatformAuthority).toBe(false)
  session.applyAuth(profile(true))
  session.clear()
  expect(session.fullPlatformAuthority).toBe(false)
})
