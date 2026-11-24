import { AppError, type ErrorCode } from '../common/errors'

const KEY = 'lims-next.platform.token.v1'
let token = (() => { try { return sessionStorage.getItem(KEY) || '' } catch { return '' } })()
export const hasSession = () => !!token
export const getSessionToken = () => token
export function notifyConnectionInterrupted(requestToken: string) {
  if (requestToken && requestToken === token) window.dispatchEvent(new Event('lims:connection-interrupted'))
}
export function setToken(value: string) {
  token = value
  try { value ? sessionStorage.setItem(KEY, value) : sessionStorage.removeItem(KEY) } catch { /* memory-only session */ }
}
export class PlatformError extends AppError {
  constructor(public platformCode: number | string, message: string, public data: unknown, status = 200) {
    const map: Record<string, ErrorCode> = { '400': 'BAD_REQUEST', '401': 'UNAUTHORIZED', '403': 'FORBIDDEN', '404': 'NOT_FOUND', '409': 'VERSION_CONFLICT', '422': 'VALIDATION', '429': 'RATE_LIMITED', '500': 'INTERNAL', '502': 'UNAVAILABLE', '503': 'UNAVAILABLE', '504': 'UNAVAILABLE', '2': 'LOCKED' }
    const code = status >= 400 ? map[String(status)] || (status >= 500 ? 'INTERNAL' : 'BAD_REQUEST') : map[String(platformCode)] || 'BUSINESS_RULE'
    const safeMessage = code === 'INTERNAL' ? '暂时无法完成操作，请稍后重试。' : code === 'UNAVAILABLE' ? '服务暂不可用，请稍后重试。' : message
    super(code, safeMessage, { status: status === 200 && Number(platformCode) >= 400 && Number(platformCode) <= 599 ? Number(platformCode) : status })
  }
}
export interface RequestOptions { method?: string; body?: unknown; signal?: AbortSignal; blob?: boolean; anonymous?: boolean }
export async function platformRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!path.startsWith('/api/') || /[\\\r\n]/.test(path)) throw new AppError('BAD_REQUEST', '接口地址不合法。')
  const headers = new Headers()
  const requestToken = options.anonymous ? '' : token
  if (requestToken) headers.set('Authorization', `Bearer ${requestToken}`)
  const multipart = options.body instanceof FormData
  if (options.body !== undefined && !multipart) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(path, { method: options.method || 'GET', credentials: 'same-origin', headers,
      signal: options.signal ?? AbortSignal.timeout(30000),
      ...(path === '/api/auth/profile' ? { cache: 'no-store' } : {}),
      ...(options.body !== undefined ? { body: multipart ? options.body as FormData : JSON.stringify(options.body) } : {}) })
  } catch (cause) {
    if (options.signal?.aborted) throw cause
    notifyConnectionInterrupted(requestToken)
    throw new AppError('NETWORK', '平台接口连接失败，请稍后重试。', { cause })
  }
  if ([502, 503, 504].includes(response.status)) notifyConnectionInterrupted(requestToken)
  if (response.status === 401 && requestToken && requestToken === token) {
    setToken(''); window.dispatchEvent(new Event('lims-next:unauthorized'))
  }
  const json = response.headers.get('content-type')?.includes('application/json')
  if (response.ok && options.blob && !json) return await response.blob() as T
  const payload = json ? await response.json() : null
  if (String(payload?.code) === '401' && requestToken && requestToken === token) {
    setToken(''); window.dispatchEvent(new Event('lims-next:unauthorized'))
  }
  if (!response.ok || !payload || payload.code !== 0) {
    if (!payload && response.ok) throw new AppError('UNAVAILABLE', '平台返回了非接口内容，请检查代理和部署路径。')
    throw new PlatformError(payload?.code ?? response.status, payload?.message || `平台接口请求失败（${response.status}）。`, payload?.data, response.status)
  }
  if (options.blob) throw new AppError('UNAVAILABLE', '平台未返回预期的文件内容。')
  return payload.data as T
}
