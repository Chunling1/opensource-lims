import { AppError, type ErrorCode } from '../common/errors'
import { platformRequest, setToken, getSessionToken, PlatformError } from '../platform/http'
import { profile, logout } from '../platform/auth'
import { refreshIdentity } from '../../stores/session'
import type { Profile } from '../platform/auth'
import type { CaptchaImage, CaptchaType, LoginState } from '../../types/auth'
import { validateNewPassword } from './passwordPolicy'

export class AuthRequestError extends AppError {
  constructor(code: ErrorCode, message: string, fields?: Record<string,string>, readonly captchaRequired?: boolean) { super(code,message,{fieldErrors:fields}) }
}
export const authClientUid = crypto.randomUUID()
export const rememberedAccount = () => { try { return localStorage.getItem('lims.login-account.v1') || '' } catch { return '' } }
export const queryLoginState = (account: string, signal?: AbortSignal) => platformRequest<LoginState>('/api/auth/login-state',{method:'POST',body:{account},anonymous:true,signal})
export async function signIn(account: string, password: string, remember: boolean, captchaVerification?: string) {
  const result = await platformRequest<Profile & { token: string }>('/api/auth/login',{method:'POST',anonymous:true,body:{account:account.trim(),password,captchaVerification,clientUid:authClientUid}})
  if (!result.token || !Array.isArray(result.permissions)) throw new AppError('UNAVAILABLE','登录返回信息不完整，请重试。')
  setToken(result.token);profile.value=result;await refreshIdentity(true)
  try { if(remember) localStorage.setItem('lims.login-account.v1',account.trim());else localStorage.removeItem('lims.login-account.v1') } catch { /* Optional preference. */ }
}
export const signOut = () => logout()
export async function changeAccountPassword(account: string, oldPassword: string, newPassword: string, confirmation: string, captchaVerification?: string) {
  validateNewPassword(newPassword, confirmation)
  if(!getSessionToken() && !captchaVerification) throw new AppError('VALIDATION','请先完成安全验证。')
  try {
    await platformRequest('/api/auth/change-password',{method:'POST',body:{account,oldPassword,newPassword,captchaVerification,clientUid:authClientUid}})
  } catch (error) {
    if (error instanceof PlatformError && error.platformCode === 1) {
      const field = error.message === '原密码错误' ? 'oldPassword'
        : error.message === '新密码不能与原密码相同' || error.message === '密码至少 8 位，必须包含大写英文、小写英文、数字和特殊字符' ? 'newPassword' : undefined
      if (field) throw new AppError('VALIDATION', error.message, { fieldErrors: { [field]: error.message } })
    }
    throw error
  }
  logout()
}
async function captcha<T>(action: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try { response=await fetch(`/api/auth/aj-captcha/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:signal??AbortSignal.timeout(15000),credentials:'same-origin',cache:'no-store'}) }
  catch(error) { if(signal?.aborted) throw error;throw new AppError('NETWORK','无法连接安全验证服务，请重试。') }
  const result=await response.json()
  if(!response.ok || result.repCode!=='0000' || !result.repData) throw new AppError('VALIDATION',result.repMsg || '安全验证失败，请刷新重试。')
  return result.repData as T
}
export const getCaptcha = (account: string,captchaType: CaptchaType,signal?: AbortSignal) => captcha<CaptchaImage>('get',{account,captchaType,clientUid:authClientUid},signal)
export const checkCaptcha = (account: string,token: string,pointJson: string,captchaType: CaptchaType,signal?: AbortSignal) => captcha<{expiresAt:number}>('check',{account,token,pointJson,captchaType,clientUid:authClientUid},signal)
