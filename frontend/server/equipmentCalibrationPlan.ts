import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { calibrationPlanColumns, calibrationPlanFields, type CalibrationPlanRow, type CalibrationPlanValues } from '../src/types/quality/equipmentCalibrationPlan'
import { registrationCsv } from './registrationDomain'
import { tableCellText } from '../src/services/common/table'
import { overallPlanOperators, overallPlanSearchFields } from '../src/types/quality/equipmentOverallPlan'
import type { EquipmentLedgerRow } from '../src/types/quality/equipmentLedger'

function initialValues(device: EquipmentLedgerRow): CalibrationPlanValues {
  return { model: device.model, accuracy: device.accuracy, range: device.range, manufacturer: device.manufacturer, serial: device.serial, department: device.department, cycle: device.cycle, testDate: device.plannedTestDate || device.lastTestDate, organization: device.testOrganization, validDate: '', fee: null, notes: '' }
}

const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
export function seedEquipmentCalibrationPlans(state: RegistrationState, now = new Date()) {
  const plans = state.equipmentCalibrationPlans ||= {}
  for (const [index, device] of (state.equipmentLedger || []).entries()) {
    if (plans[device.id]) continue
    const testDate = device.plannedTestDate, submitted = index % 3 === 0 && !!testDate && testDate <= now.toISOString().slice(0, 10)
    const values: CalibrationPlanValues = {
      ...initialValues(device), testDate, cycle: '12个月',
      organization: ['市计量测试研究院（演示）', '省计量科学研究院（演示）', '第三方计量检测中心（演示）'][index % 3]!,
      validDate: testDate ? `${Number(testDate.slice(0, 4)) + 1}${testDate.slice(4)}` : '', fee: 180 + index * 35,
      notes: submitted ? '演示记录：已检定，可继续修改。' : '演示记录：未检定，可测试保存和提交。',
    }
    plans[device.id] = { version: 1, submitted, values, submissions: submitted ? [{ version: 1, submittedAt: `${testDate}T08:00:00.000Z`, values: structuredClone(values) }] : [] }
  }
}
export function createEquipmentCalibrationPlans(deps: RegistrationDependencies) {
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || !user.roles.some(role => (write ? ['admin', 'quality'] : ['admin', 'quality', 'reviewer', 'approver']).includes(role))) throw new AppError('FORBIDDEN', '无权执行计量器具周期检定计划操作。')
    return user
  }
  function detail(id: unknown): CalibrationPlanRow {
    const user = actor(), state = deps.read!()!, device = state.equipmentLedger?.find(item => item.id === id)
    if (!device || user.scope !== 'all' && device.departmentId !== user.departmentId) throw new AppError('NOT_FOUND', '设备不存在或无权访问，请刷新列表。')
    const plan = state.equipmentCalibrationPlans?.[device.id]
    return { ...initialValues(device), ...plan?.values, id: device.id, code: device.code, name: device.name, status: device.status, version: plan?.version || 0, equipmentVersion: device.version || 1, submitted: plan?.submitted || false }
  }
  function query(input: Record<string, unknown>, all = false) {
    const user = actor(), field = input.field ?? 'code', operator = input.operator ?? 'contains', value = input.value ?? ''
    if (!overallPlanSearchFields.some(item => item.key === field) || !overallPlanOperators.some(item => item.key === operator) || typeof value !== 'string' || value.length > 200) throw new AppError('VALIDATION', '查询条件有误。')
    const from = input.from ?? '', to = input.to ?? '', requestedPage = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (typeof from !== 'string' || typeof to !== 'string' || from && !validDate(from) || to && !validDate(to) || from && to && from > to) throw new AppError('VALIDATION', '请检查检定日期范围。')
    if (typeof requestedPage !== 'number' || !Number.isSafeInteger(requestedPage) || requestedPage < 1 || typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize)) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100))) throw new AppError('VALIDATION', '所选设备有误。')
    const ids = input.ids as string[] | undefined
    const search = value.trim().toLocaleLowerCase(), numeric = (text: string) => /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)
    const items = (deps.read!()!.equipmentLedger || []).filter(device => (user.scope === 'all' || device.departmentId === user.departmentId) && (!ids || ids.includes(device.id))).map(device => detail(device.id)).filter(row => {
      if (from && (!row.testDate || row.testDate < from) || to && (!row.testDate || row.testDate > to)) return false
      if (!search) return true
      const content = String(row[field as keyof CalibrationPlanRow]).trim().toLocaleLowerCase()
      if (operator === 'contains') return content.includes(search)
      if (operator === 'eq') return numeric(content) && numeric(search) ? Number(content) === Number(search) : content === search
      if (!content || numeric(search) && !numeric(content)) return false
      const comparison = numeric(content) && numeric(search) ? Number(content) - Number(search) : content.localeCompare(search, 'zh-CN', { numeric: true })
      return operator === 'gt' ? comparison > 0 : operator === 'gte' ? comparison >= 0 : operator === 'lt' ? comparison < 0 : comparison <= 0
    }).sort((a, b) => a.code.localeCompare(b.code, 'zh-CN', { numeric: true }))
    const page = Math.min(requestedPage, Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>, submit = false) {
    actor(true)
    const current = detail(input.id)
    
    if (!input.values || typeof input.values !== 'object' || Array.isArray(input.values)) throw new AppError('VALIDATION', '计划字段有误。')
    const raw = input.values as Record<string, unknown>, values = {} as CalibrationPlanValues
    for (const field of calibrationPlanFields) {
      const value = raw[field.key]
      if (field.key === 'fee') {
        if (value !== null && (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 999999999 || Math.abs(value * 100 - Math.round(value * 100)) > 0.00001)) throw problem('VALIDATION', '请填写非负金额，最多保留两位小数。', 'fee')
        values.fee = value as number | null
      } else {
        if (typeof value !== 'string' || value.trim().length > 1000) throw problem('VALIDATION', `${field.label}最多 1000 个字符。`, field.key)
        values[field.key] = value.trim()
        if ('date' in field && value && !validDate(value)) throw problem('VALIDATION', '请填写有效的日期。', field.key)
      }
    }
    if (values.testDate && values.validDate && values.validDate < values.testDate) throw problem('VALIDATION', '有效日期不能早于检定日期。', 'validDate')
    if (submit) {
      const errors: Record<string, string> = {}
      for (const [key, label] of [['testDate', '检定日期'], ['organization', '检定单位']] as const) if (!values[key]) errors[key] = `请填写${label}。`
      if (Object.keys(errors).length) throw new AppError('VALIDATION', '请完善检定信息。', { fieldErrors: errors })
    }
    const state = structuredClone(deps.read!()!), plans = state.equipmentCalibrationPlans ||= {}
    const previous = plans[current.id], version = current.version + 1
    const submissions = structuredClone(previous?.submissions || [])
    if (submit) submissions.push({ version, submittedAt: new Date().toISOString(), values: structuredClone(values) })
    plans[current.id] = { version, submitted: submit, values, submissions }
    deps.write!(state)
    return detail(current.id)
  }
  return { query, detail, save, export: (input: Record<string, unknown>) => registrationCsv([calibrationPlanColumns.map(column => column.label), ...query(input, true).items.map(row => calibrationPlanColumns.map(column => tableCellText(row[column.key], { money: 'money' in column && column.money })))]) }
}
