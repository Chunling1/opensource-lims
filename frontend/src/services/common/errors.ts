export type ErrorCode = 'BAD_REQUEST' | 'UNAUTHORIZED' | 'FORBIDDEN' | 'NOT_FOUND' | 'VERSION_CONFLICT' | 'VALIDATION' | 'BUSINESS_RULE' | 'RATE_LIMITED' | 'INTERNAL' | 'UNAVAILABLE' | 'MAINTENANCE' | 'NETWORK' | 'RESOURCE_LOAD' | 'STORAGE_UNAVAILABLE' | 'STORAGE_WRITE' | 'LOCKED'
const statuses: Partial<Record<ErrorCode, number>> = { BAD_REQUEST: 400, UNAUTHORIZED: 401, FORBIDDEN: 403, NOT_FOUND: 404, VERSION_CONFLICT: 409, VALIDATION: 422, BUSINESS_RULE: 422, RATE_LIMITED: 429, INTERNAL: 500, UNAVAILABLE: 503, MAINTENANCE: 503 }
export class AppError extends Error {
  readonly code: ErrorCode
  readonly status?: number
  readonly fieldErrors?: Record<string, string>
  readonly diagnosticId: string
  readonly retryAt?: number
  constructor(code: ErrorCode, message: string, options: { status?: number; fieldErrors?: Record<string, string>; cause?: unknown; retryAt?: number } = {}) {
    super(message, { cause: options.cause }); this.name = 'AppError'; this.code = code
    this.status = options.status ?? statuses[code]; this.fieldErrors = options.fieldErrors
    this.retryAt = Number.isFinite(options.retryAt) ? options.retryAt : undefined
    this.diagnosticId = `ERR-${crypto.randomUUID().slice(0, 8).toUpperCase()}`
  }
}
export type ErrorValue = AppError | ''
// Expected input/state/access failures need an operation hint, not system diagnostics.
export const isOperationalError = (error?: AppError | '') => !!error && ['VALIDATION', 'BUSINESS_RULE', 'VERSION_CONFLICT', 'BAD_REQUEST', 'UNAUTHORIZED', 'FORBIDDEN', 'NOT_FOUND', 'LOCKED', 'RATE_LIMITED'].includes(error.code)
export const problem = (code: ErrorCode, message: string, field?: string) => new AppError(code, message, { fieldErrors: field ? { [field]: message } : undefined })
const normalized = new WeakMap<object, AppError>()
const diagnostics: { id: string; code: ErrorCode; at: string }[] = []
export function normalizeError(value: unknown): AppError {
  let error: AppError
  if (value instanceof AppError) error = value
  else {
    const object = value !== null && (typeof value === 'object' || typeof value === 'function') ? value as object : undefined
    error = (object && normalized.get(object)) || new AppError('INTERNAL', '暂时无法完成操作，请稍后重试。', { cause: value })
    if (object) normalized.set(object, error)
  }
  if (!diagnostics.some(d => d.id === error.diagnosticId)) {
    diagnostics.push({ id: error.diagnosticId, code: error.code, at: new Date().toISOString() })
    if (diagnostics.length > 50) diagnostics.shift()
  }
  return error
}
export function diagnosticSnapshot() { return diagnostics.map(d => ({ ...d })) }
export function errorForStatus(status: number) {
  const entries: Record<number, [ErrorCode, string]> = {
    400: ['BAD_REQUEST', '访问参数有误，请检查链接或返回列表。'], 401: ['UNAUTHORIZED', '当前登录已失效，请重新登录平台账号。'],
    403: ['FORBIDDEN', '当前身份无权访问此模块。'], 404: ['NOT_FOUND', '链接可能已失效，请返回工作台继续操作。'],
    500: ['INTERNAL', '暂时无法完成操作，请稍后重试。'], 503: ['MAINTENANCE', '系统正在维护，请稍后重新访问。'],
  }
  const [code, message] = entries[status] ?? entries[404]!
  return new AppError(code, message)
}
export function safeReturn(value: unknown, fallback = '/dashboard') {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || /[\\\r\n]/.test(value) || /^\/(errors|forbidden|not-found)(\/|\?|$)/.test(value)) return fallback
  return value
}
export const canRetry = (error: AppError) => !['BAD_REQUEST', 'UNAUTHORIZED', 'FORBIDDEN', 'NOT_FOUND', 'VALIDATION', 'BUSINESS_RULE', 'VERSION_CONFLICT', 'LOCKED'].includes(error.code)

