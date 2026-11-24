import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import type { EquipmentLedgerRow } from '../src/types/quality/equipmentLedger'
import { equipmentConditionStates, type EquipmentCondition, availableEquipmentColumns, equipmentLoanColumns, equipmentLoanRecordColumns, canManageEquipmentLoans, type EquipmentLoanRecord, type EquipmentLoanRow, type LoanTab } from '../src/types/quality/equipmentLoans'
import { demoActors } from '../src/services/storage/demoActors'
import { registrationCsv } from './registrationDomain'
const validDate = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
const object = (value: unknown): Record<string, unknown> => { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('VALIDATION', '操作参数有误。'); return value as Record<string, unknown> }
function text(value: unknown, key: string, max = 1000) { if (typeof value !== 'string' || value.length > max) throw problem('VALIDATION', `请填写不超过 ${max} 个字符的内容。`, key); return value.trim() }
function newRecord(device: EquipmentLedgerRow, borrower: string, borrowedAt: string, notes: string, actorId: string, actorName: string): EquipmentLoanRecord {
  return { id: randomUUID(), version: 1, equipmentId: device.id, departmentId: device.departmentId, department: device.department, code: device.code, name: device.name, model: device.model, manufacturer: device.manufacturer, keeper: device.keeper,
    borrowerId: '', borrower, borrowedAt, borrowedStatus: '正常', notes, borrowedById: actorId, borrowedBy: actorName, createdAt: new Date().toISOString(),
    returner: '', returnedAt: '', returnedStatus: '', returnNotes: '', returnedById: '', returnedBy: '', updatedAt: '' }
}
export function seedEquipmentLoans(state: RegistrationState, now = new Date()) {
  if (state.equipmentLoans) return
  state.equipmentLoans = []
  const devices = (state.equipmentLedger || []).filter(device => device.status === '可用').slice(0, 4)
  const date = (offset: number) => new Date(now.getTime() + offset * 86400000).toISOString().slice(0, 10)
  devices.forEach((device, index) => {
    const record = newRecord(device, demoActors[0]!.name, date(-3), '演示领用记录', 'admin', demoActors[0]!.name)
    if (index >= 2) {
      Object.assign(record, { version: 2, returner: demoActors[0]!.name, returnedAt: date(-1), returnedStatus: index === 3 ? '异常' : '正常', returnNotes: '演示归还记录', returnedById: 'admin', returnedBy: demoActors[0]!.name, updatedAt: now.toISOString() })
    }
    state.equipmentLoans!.push(record)
  })
}
export function createEquipmentLoans(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canManageEquipmentLoans(user) : !user.roles.some(role => ['admin', 'quality', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行设备领用与归还操作。')
    return user
  }
  const inScope = (departmentId: string) => { const user = deps.actor(); return user.scope === 'all' || user.departmentId === departmentId }
  function device(id: unknown) {
    const row = read().equipmentLedger?.find(row => row.id === id)
    if (!row || !inScope(row.departmentId)) throw new AppError('NOT_FOUND', '设备不存在或无权访问，请刷新列表。')
    return row
  }
  function available(id: unknown): EquipmentLoanRow {
    const row = device(id)
    if (row.status !== '可用' || read().equipmentLoans?.some(record => record.equipmentId === id && !record.returnedAt)) throw new AppError('BUSINESS_RULE', `设备“${row.code}”已被领用或当前不可用，请刷新确认。`)
    return { ...newRecord(row, '', '', '', '', ''), returner: '', id: row.id, version: row.version || 1, equipmentVersion: row.version || 1, currentStatus: row.status, loanStatus: '未领用', createdAt: '' }
  }
  function detail(id: unknown): EquipmentLoanRow {
    actor()
    const record = read().equipmentLoans?.find(row => row.id === id)
    if (!record || !inScope(record.departmentId)) throw new AppError('NOT_FOUND', '领用记录不存在或无权访问。')
    const row = device(record.equipmentId)
    return { ...record, returner: record.returner ?? (record.returnedAt ? record.returnedBy : ''), equipmentVersion: row.version || 1, currentStatus: row.status, loanStatus: record.returnedAt ? '已归还' : '未归还' }
  }
  function ids(value: unknown) {
    if (!Array.isArray(value) || !value.length || value.length > 200 || value.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(value).size !== value.length) throw new AppError('VALIDATION', '请选择 1 至 200 条不重复的记录。')
    return value as string[]
  }
  function options() { actor(); return demoActors.filter(user => user.active !== false && inScope(user.departmentId)).map(({ id, name }) => ({ id, name })) }
  function context(input: Record<string, unknown>) {
    actor(true)
    if (input.mode !== 'borrow' && input.mode !== 'return') throw new AppError('VALIDATION', '操作类型有误。')
    const items = ids(input.ids).map(id => input.mode === 'borrow' ? available(id) : detail(id))
    const returned = items.find(row => row.returnedAt)
    if (returned) throw new AppError('BUSINESS_RULE', `设备“${returned.code}”已归还，请刷新确认。`)
    return { items }
  }
  function query(kind: LoanTab, input: Record<string, unknown>, all = false) {
    actor()
    const code = text(input.code ?? '', 'code', 200).toLocaleLowerCase(), name = text(input.name ?? '', 'name', 200).toLocaleLowerCase(), manufacturer = text(input.manufacturer ?? '', 'manufacturer', 200).toLocaleLowerCase()
    const status = input.status ?? 'open', page = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (!['all', 'open', 'returned'].includes(String(status)) || !Number.isSafeInteger(page) || Number(page) < 1 || ![10, 20, 50].includes(Number(pageSize)) || typeof pageSize !== 'number') throw new AppError('VALIDATION', '查询或分页参数有误。')
    const dateField = input.dateField ?? '', field = input.field ?? '', value = text(input.value ?? '', 'value', 200).toLocaleLowerCase()
    if (typeof dateField !== 'string' || typeof field !== 'string' || !['', 'borrowedAt', 'returnedAt'].includes(dateField) || !['', 'borrowedStatus', 'returnedStatus', 'code'].includes(field)) throw new AppError('VALIDATION', '查询字段有误。')
    if (dateField && (!validDate(input.from) || !validDate(input.to) || input.from > input.to)) throw new AppError('VALIDATION', '请选择有效的日期范围，开始日期不能晚于结束日期。')
    const selected = input.ids === undefined ? undefined : ids(input.ids)
    const state = read(), occupied = new Set((state.equipmentLoans || []).filter(row => !row.returnedAt).map(row => row.equipmentId))
    const devices = new Map((state.equipmentLedger || []).map(row => [row.id, row]))
    const rows = kind === 'available' ? (state.equipmentLedger || []).filter(row => inScope(row.departmentId) && row.status === '可用' && !occupied.has(row.id)).map(row => available(row.id))
      : (state.equipmentLoans || []).filter(row => inScope(row.departmentId) && devices.has(row.equipmentId) && inScope(devices.get(row.equipmentId)!.departmentId) && (status === 'all' || (status === 'returned') === !!row.returnedAt)).map(row => detail(row.id))
    const items = rows.filter(row => (!dateField || !!row[dateField as 'borrowedAt' | 'returnedAt'] && row[dateField as 'borrowedAt' | 'returnedAt'] >= String(input.from) && row[dateField as 'borrowedAt' | 'returnedAt'] <= String(input.to)) && (!field || row[field as 'borrowedStatus' | 'returnedStatus' | 'code'].toLocaleLowerCase().includes(value)) && (!selected || selected.includes(row.id)) && row.code.toLocaleLowerCase().includes(code) && row.name.toLocaleLowerCase().includes(name) && row.manufacturer.toLocaleLowerCase().includes(manufacturer))
      .sort((a, b) => kind === 'records' ? b.borrowedAt.localeCompare(a.borrowedAt) || b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id) : a.code.localeCompare(b.code, 'zh-CN', { numeric: true }))
    const current = Math.min(Number(page), Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((current - 1) * pageSize, current * pageSize), total: items.length, page: current, pageSize }
  }
  function targets(input: Record<string, unknown>, kind: 'borrow' | 'return') {
    if (!Array.isArray(input.records)) throw new AppError('VALIDATION', '请选择设备。')
    const records = input.records.map(object); ids(records.map(row => row.id))
    return records.map(raw => {
      const row = kind === 'borrow' ? available(raw.id) : detail(raw.id)
      if (row.returnedAt) throw new AppError('BUSINESS_RULE', `设备“${row.code}”已归还，不能重复归还。`)
      return { row, raw }
    })
  }
  function borrow(input: Record<string, unknown>) {
    const user = actor(true), rows = targets(input, 'borrow')
    if (!validDate(input.date)) throw problem('VALIDATION', '请选择有效的领用日期。', 'date')
    const borrower = text(input.borrower, 'borrower', 100)
    if (!borrower) throw problem('VALIDATION', '请填写领用人。', 'borrower')
    if (!equipmentConditionStates.includes(input.borrowedStatus as EquipmentCondition)) throw problem('VALIDATION', '请选择领取时的设备状态。', 'borrowedStatus')
    const notes = text(input.notes, 'notes'), state = structuredClone(read()), records = state.equipmentLoans ||= []
    for (const { row } of rows) {
      const device = state.equipmentLedger!.find(device => device.id === row.equipmentId)!
      records.push({ ...newRecord(device, borrower, input.date, notes, user.id, user.name), borrowedStatus: input.borrowedStatus as EquipmentCondition }); device.version = (device.version || 1) + 1
    }
    deps.write!(state); return { count: rows.length }
  }
  function returnDevices(input: Record<string, unknown>) {
    const user = actor(true), rows = targets(input, 'return')
    if (!validDate(input.date)) throw problem('VALIDATION', '请选择有效的归还日期。', 'date')
    const date = input.date
    for (const { row } of rows) {
      if (date < row.borrowedAt) throw problem('VALIDATION', `归还日期不能早于设备“${row.code}”的领用日期 ${row.borrowedAt}。`, 'date')
    }
    if (!equipmentConditionStates.includes(input.returnedStatus as EquipmentCondition)) throw problem('VALIDATION', '请选择归还时的设备状态。', 'returnedStatus')
    const returner = text(input.returner, 'returner', 100)
    if (!returner) throw problem('VALIDATION', '请填写归还人。', 'returner')
    const returnedStatus = input.returnedStatus as EquipmentCondition, notes = text(input.notes, 'notes')
    const state = structuredClone(read())
    for (const { row } of rows) {
      const record = state.equipmentLoans!.find(record => record.id === row.id)!, device = state.equipmentLedger!.find(device => device.id === record.equipmentId)!
      Object.assign(record, { version: record.version + 1, returnedAt: date, returner, returnedStatus, returnNotes: notes, returnedById: user.id, returnedBy: user.name, updatedAt: new Date().toISOString() })
      device.version = (device.version || 1) + 1
    }
    deps.write!(state); return { count: rows.length }
  }
  return { query, detail, context, options, borrow, returnDevices, exportHistory: (input: Record<string, unknown>) => {
    const columns = equipmentLoanRecordColumns
    return registrationCsv([columns.map(column => column.label), ...query('records', { ...input, status: 'all' }, true).items.map(row => columns.map(column => String(row[column.key] ?? '')))])
  }, export: (kind: LoanTab, input: Record<string, unknown>) => {
    const columns = kind === 'available' ? availableEquipmentColumns : equipmentLoanColumns
    return registrationCsv([columns.map(column => column.label), ...query(kind, input, true).items.map(row => columns.map(column => String(row[column.key] ?? '')))])
  } }
}
