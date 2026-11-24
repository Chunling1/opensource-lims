import { shallowRef } from 'vue'
import { getSessionToken, platformRequest, setToken } from './http'
import { AppError } from '../common/errors'
export interface Profile {
  erpPermissions?: string[]
  uiPreferences?: Record<string, Record<string, any>>
  account: string; userName: string; roleKey: string; roleName: string; homePath: string
  dataScope: { department: string; scopeType: 'all' | 'department' | 'self' | 'authorization' | 'department_project'; description: string }
  permissions: string[]; actionPermissions: string[]; projectPermissions?: { project: string; step: string }[]
  personal?: { phone: string; email: string; avatar: string; departmentName: string; position: string; jobTitle: string; certificateNumber: string };
  features?: { fullPlatformAuthority?: boolean; businessDataCorrection?: boolean; businessReadOnly?: boolean; deploymentRole?: string; environmentLabel?: string }
}
export const profile = shallowRef<Profile>()
export const captcha = () => platformRequest<{ captchaId: string; image: string; expiresInSeconds: number }>('/api/auth/captcha', { anonymous: true })
export async function login(input: { account: string; password: string; captchaId: string; captcha: string }) {
  const result = await platformRequest<Profile & { token: string }>('/api/auth/login', { method: 'POST', body: input, anonymous: true })
  if (!result.token || !Array.isArray(result.permissions)) throw new Error('登录返回契约异常')
  setToken(result.token); profile.value = result; return result
}
let pendingProfile: { token: string; promise: Promise<Profile> } | undefined
export async function refreshProfile() {
  const requestToken = getSessionToken()
  if (pendingProfile?.token === requestToken) return pendingProfile.promise
  const promise = (async () => {
    const value = await platformRequest<Profile>('/api/auth/profile')
    if (!requestToken || requestToken !== getSessionToken()) throw new AppError('UNAUTHORIZED', '登录会话已变更，请重新打开页面。')
    return profile.value = value
  })()
  pendingProfile = { token: requestToken, promise }
  try { return await promise }
  finally { if (pendingProfile?.promise === promise) pendingProfile = undefined }
}
export async function changePassword(input: { account: string; oldPassword: string; newPassword: string; captchaId: string; captcha: string }) {
  await platformRequest('/api/auth/change-password', { method: 'POST', body: input }); logout()
}
export function logout() { setToken(''); profile.value = undefined }
export function permission(code: string) { return !!profile.value?.permissions.includes(code) }
