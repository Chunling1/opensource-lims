import { AppError } from '../src/services/common/errors'
import { tableCellText } from '../src/services/common/table'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import { equipmentDateFields, equipmentLedgerColumns, equipmentStates, type EquipmentLedgerQuery, type EquipmentLedgerRow } from '../src/types/quality/equipmentLedger'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { equipmentOptions } from './dataEntryEquipment'
import { registrationCsv } from './registrationDomain'

export function seedEquipmentLedger(now = new Date()): EquipmentLedgerRow[] {
  const base = registrationDepartments.flatMap(d => equipmentOptions({ departmentId: d.id }))
  const date = (months: number, day: number) => new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + months, day)).toISOString().slice(0, 10)
  return Array.from({ length: 24 }, (_, i) => {
    const source = base[i], departmentId = source?.departmentId || (i >= 21 ? '' : i % 2 ? 'lab2' : 'lab')
    const plannedMonth = i < 12 ? 0 : i < 18 ? -1 : 1
    return {
      id: source?.id || `ledger-equipment-${i + 1}`, code: source?.code || `DEMO-${String(i + 1).padStart(3, '0')}`,
      name: source?.name || `${['电子天平', '干燥箱', '分光光度计', '游标卡尺'][i % 4]}（示例${i + 1}）`, model: source?.model || '演示通用型',
      serial: source?.serial || `EQ-${String(i + 1).padStart(4, '0')}`, manufacturer: source?.manufacturer || '演示设备厂商',
      testOrganization: '演示计量检测中心', status: i < 3 ? '可用' : equipmentStates[i % 4]!, departmentId,
      department: registrationDepartments.find(d => d.id === departmentId)?.name || '', location: !departmentId ? '设备暂存区' : departmentId === 'lab' ? '中心实验室' : '第二实验室',
      lastTestDate: date(plannedMonth - 12, i % 20 + 1), cycle: '12个月', plannedTestDate: date(plannedMonth, i % 20 + 1), actualTestDate: date(plannedMonth - 12, i % 20 + 1),
      notes: '', range: '以仪器铭牌为准', accuracy: '以检定证书为准', keeper: '演示保管人', purchasedAt: date(-15, i % 20 + 1),
      price: (i + 1) * 1200, usageRecordCount: 0, manualCount: 0, certificateCount: 0, acceptanceCount: 0,
    }
  })
}
function parse(input: Record<string, unknown>): EquipmentLedgerQuery {
  const q: EquipmentLedgerQuery = {}
  for (const key of ['code', 'name', 'manufacturer', 'serial', 'departmentId', 'status', 'from', 'to'] as const) {
    if (input[key] === undefined) continue
    if (typeof input[key] !== 'string' || input[key].length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    q[key] = input[key].trim()
  }
  for (const key of ['ownDepartment', 'unassociated'] as const) {
    if (input[key] !== undefined && typeof input[key] !== 'boolean') throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    q[key] = input[key] === true
  }
  if (q.status && !equipmentStates.some(s => s === q.status) || q.departmentId && !registrationDepartments.some(d => d.id === q.departmentId)) throw new AppError('BAD_REQUEST', '不支持的查询选项。')
  const dateField = input.dateField ?? (q.from || q.to ? 'lastTestDate' : '')
  const field = equipmentDateFields.find(f => f.key === dateField)
  if (dateField !== '' && !field) throw new AppError('BAD_REQUEST', '日期类型有误。')
  q.dateField = field?.key || ''
  if (!q.dateField) { q.from = undefined; q.to = undefined }
  const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
  if (q.from && !validDate(q.from) || q.to && !validDate(q.to) || q.from && q.to && q.from > q.to) throw new AppError('VALIDATION', '请检查日期范围。')
  q.page = input.page === undefined ? 1 : Number(input.page); q.pageSize = input.pageSize === undefined ? 10 : Number(input.pageSize)
  if (input.page !== undefined && typeof input.page !== 'number' || input.pageSize !== undefined && typeof input.pageSize !== 'number' || !Number.isSafeInteger(q.page) || q.page < 1 || ![10, 20, 50].includes(q.pageSize)) throw new AppError('BAD_REQUEST', '分页参数有误。')
  const sort = input.sort ?? 'code'
  if (!['code', ...equipmentDateFields.map(f => f.key)].includes(String(sort)) || input.direction !== undefined && !['asc', 'desc'].includes(String(input.direction))) throw new AppError('BAD_REQUEST', '排序参数有误。')
  q.sort = String(sort); q.direction = input.direction === 'desc' ? 'desc' : 'asc'
  if (input.ids !== undefined) {
    if (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '所选记录有误。')
    q.ids = [...new Set(input.ids as string[])]
  }
  return q
}
export function createEquipmentLedger(deps: RegistrationDependencies) {
  function query(input: Record<string, unknown>, all = false) {
    const actor = deps.actor()
    if (deps.locked?.() || !actor.roles.some(r => ['admin', 'quality', 'reviewer', 'approver'].includes(r))) throw new AppError('FORBIDDEN', '无权访问设备台账。')
    const q = parse(input), state = deps.read!()!
    const dateField = q.dateField, key = q.sort as 'code' | typeof equipmentDateFields[number]['key'], direction = q.direction === 'desc' ? -1 : 1
    const rows = (state.equipmentLedger || []).filter(row => (actor.scope === 'all' || row.departmentId === actor.departmentId)
      && (!q.ownDepartment || row.departmentId === actor.departmentId) && (!q.departmentId || row.departmentId === q.departmentId)
      && (!q.status || row.status === q.status) && (!q.unassociated || !row.departmentId) && (!q.ids || q.ids.includes(row.id))
      && ['code', 'name', 'manufacturer', 'serial'].every(k => { const field = k as 'code' | 'name' | 'manufacturer' | 'serial'; return !q[field] || row[field].toLocaleLowerCase().includes(q[field]!.toLocaleLowerCase()) })
      && (!dateField || ((!q.from || !!row[dateField] && row[dateField] >= q.from) && (!q.to || !!row[dateField] && row[dateField] <= q.to))))
      .sort((a, b) => (!a[key] !== !b[key] ? a[key] ? -1 : 1 : (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction))
    const page = Math.min(q.page!, Math.max(1, Math.ceil(rows.length / q.pageSize!)))
    return { items: all ? rows : rows.slice((page - 1) * q.pageSize!, page * q.pageSize!), total: rows.length, page, pageSize: q.pageSize!, departments: registrationDepartments.filter(d => actor.scope === 'all' || d.id === actor.departmentId) }
  }
  return { query, export: (input: Record<string, unknown>) => registrationCsv([equipmentLedgerColumns.map(c => c.label), ...query(input, true).items.map(row => equipmentLedgerColumns.map(c => tableCellText(row[c.key], { money: 'money' in c && c.money })))]) }
}
