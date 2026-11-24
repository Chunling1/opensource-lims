import { AppError, type ErrorCode } from '../services/common/errors'

/** Translate the platform contract into the template's existing error states. */
export function platformError(value: unknown): AppError {
  if (value instanceof AppError) return value
  const error = value as { status?: number; code?: number | string; message?: string }
  const status = Number(error?.status === 200 ? error.code : error?.status)
  const codes: Record<number, ErrorCode> = { 400: 'BAD_REQUEST', 401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'VERSION_CONFLICT', 422: 'BUSINESS_RULE', 429: 'RATE_LIMITED', 500: 'INTERNAL', 502: 'UNAVAILABLE', 503: 'UNAVAILABLE', 504: 'UNAVAILABLE' }
  const code = codes[status] || (error?.status === 200 ? 'BUSINESS_RULE' : value instanceof TypeError ? 'NETWORK' : 'INTERNAL')
  const fallback = code === 'NETWORK' ? '网络连接失败，请检查连接后重试。' : code === 'UNAVAILABLE' ? '服务暂不可用，请稍后重试。' : '暂时无法完成操作，请稍后重试。'
  // Server internals must not leak through gateway/runtime errors.
  const message = status >= 500 || code === 'INTERNAL' || code === 'NETWORK' ? fallback : error?.message || fallback
  return new AppError(code, message, { status: Number.isFinite(status) ? status : undefined, cause: value })
}

export function reportPreviewError(value: unknown): AppError {
  const message = value instanceof Error ? value.message : ''
  // Existing records may predate persisted previews. Reading must not generate a
  // new report or disguise this expected business prerequisite as a system fault.
  if (message.startsWith('尚无当前受控正式版本')) return new AppError('BUSINESS_RULE', message, { cause: value })
  return platformError(value)
}
