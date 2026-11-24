import { AppError, problem } from '../src/services/common/errors'
import { demoActors } from '../src/services/storage/demoActors'
import type { OutboundReceipt } from '../src/types/samples/outbound'

export function stockField(data: Record<string, unknown>, key: string, label: string, limit = 100, required = true) {
  const value = data[key]
  if (typeof value !== 'string' || value.length > limit || required && !value.trim()) throw problem('VALIDATION', `请检查${label}。`, key)
  return value.trim()
}
export function stockDate(data: Record<string, unknown>, label: string) {
  const value = stockField(data, 'date', label, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw problem('VALIDATION', `请填写有效的${label}。`, 'date')
  return value
}
export function parseStockReceipt(input: unknown, operation: '入库' | '出库'): OutboundReceipt {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', `请填写样品${operation}信息。`)
  const data = input as Record<string, unknown>
  const account = stockField(data, 'account', '样品管理员工号'), name = stockField(data, 'name', '样品管理员姓名')
  const manager = demoActors.find(user => user.id === account)
  if (!manager || manager.name !== name) throw new AppError('VALIDATION', '样品管理员工号与姓名不匹配，请核对后重新提交。', { fieldErrors: { account: '请核对管理员工号。', name: '工号与姓名不匹配，请核对后重新提交。' } })
  return { account: manager.id, name: manager.name, date: stockDate(data, operation === '入库' ? '入库日期' : '出库时间') }
}
