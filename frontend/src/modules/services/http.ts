import { beginListRead, isListRead } from './listReadState'
import { readSessionToken, saveSessionToken } from './sessionToken'
import { AppError } from '../../services/common/errors'
import { notifyConnectionInterrupted } from '../../services/platform/http'
export interface ApiResponse<T> {
  code: number | string
  message: string
  data: T
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: number | string = -1,
    public readonly data: unknown = null,
  ) {
    super(message)
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

// OAuth2 访问令牌（登录后写入），业务请求自动附带 Bearer 头
export function setAccessToken(token: string) {
  saveSessionToken(token)
}
export function clearAccessToken() {
  saveSessionToken('')
}

function notifyAuthorizationChange(status: number, code: number | string, requestToken: string) {
  // A late response belongs to the credentials sent with that request, not a
  // replacement session established while the request was in flight.
  if (typeof window === 'undefined' || !requestToken || requestToken !== readSessionToken()) return
  if (status === 401 || String(code) === '401') {
    clearAccessToken()
    window.dispatchEvent(new CustomEvent('lims:session-invalidated'))
    return
  }
  if (status === 403 || String(code) === '403') {
    window.dispatchEvent(new CustomEvent('lims:permissions-stale'))
  }
}

// 原始 fetch（带 Bearer 头），用于二进制下载/预览，调用方自行处理 Response
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  const requestToken = readSessionToken()
  if (requestToken) headers.Authorization = `Bearer ${requestToken}`
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers }).catch(error => {
    if (error instanceof TypeError || error instanceof Error && error.name === 'TimeoutError') notifyConnectionInterrupted(requestToken)
    throw error
  })
  if ([502, 503, 504].includes(response.status)) notifyConnectionInterrupted(requestToken)
  if (response.status === 401 || response.status === 403) {
    notifyAuthorizationChange(response.status, response.status, requestToken)
  }
  return response
}

export async function request<T>(path: string, init: RequestInit = {}, timeoutMs?: number): Promise<T> {
  const finish = beginListRead(path, init.method)
  const requestToken = readSessionToken()
  const readOnly = (init.method ?? 'GET').toUpperCase() === 'GET' || isListRead(path, init.method)
  const deadline = timeoutMs ?? (readOnly ? 30_000 : undefined)
  const timeout = deadline === undefined ? undefined : AbortSignal.timeout(deadline)
  const signal = init.signal && timeout ? AbortSignal.any([init.signal, timeout]) : init.signal ?? timeout
  try {
    const data = await performRequest<T>(path, { ...init, signal }, requestToken)
    finish()
    return data
  } catch (error) {
    const unreachable = !init.signal?.aborted && (timeout?.aborted || error instanceof TypeError)
    const failure = unreachable
      ? new AppError('NETWORK', timeout?.aborted ? '请求超时，请核对当前状态后重试。' : '网络连接中断，请检查连接。', { cause: error })
      : error
    if (unreachable || error instanceof ApiError && [502, 503, 504].includes(error.status)) notifyConnectionInterrupted(requestToken)
    finish(failure)
    throw failure
  }
}

async function performRequest<T>(path: string, init: RequestInit, requestToken: string): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  // FormData 的 boundary 必须由浏览器生成，不能手工覆盖 Content-Type。
  if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (requestToken) headers.Authorization = `Bearer ${requestToken}`

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })

  if (!response.ok && response.status !== 200) {
    // 401 等：尝试解析后端统一错误体
    if (response.status === 401) notifyAuthorizationChange(401, 401, requestToken)
    let message = `接口请求失败：${response.statusText}`
    let code: number | string = -1
    let data: unknown = null
    try {
      const body = (await response.json()) as ApiResponse<unknown>
      if (body?.message) message = body.message
      code = body?.code ?? code
      data = body?.data ?? data
    } catch {
      if (init.signal?.aborted) throw init.signal.reason
    }
    notifyAuthorizationChange(response.status, code, requestToken)
    throw new ApiError(message, response.status, code, data)
  }

  const payload = (await response.json()) as ApiResponse<T>
  if (payload.code !== 0) {
    notifyAuthorizationChange(response.status, payload.code, requestToken)
    throw new ApiError(payload.message, response.status, payload.code, payload.data)
  }

  return payload.data
}
