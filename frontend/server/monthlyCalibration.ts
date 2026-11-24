import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { createEquipmentLedger } from './equipmentLedger'

export function createMonthlyCalibration(deps: RegistrationDependencies) {
  const ledger = createEquipmentLedger(deps)
  function query(input: Record<string, unknown>) {
    const { year, month } = input
    if (typeof year !== 'number' || !Number.isInteger(year) || year < 1000 || year > 9999 || typeof month !== 'number' || !Number.isInteger(month) || month < 1 || month > 12) throw new AppError('VALIDATION', '请选择有效的年份和月份。')
    const prefix = `${year}-${String(month).padStart(2, '0')}`
    // Fix the plan date range on the server; unrelated ledger filters cannot override it.
    return {
      ...Object.fromEntries(['code', 'name', 'manufacturer', 'serial', 'departmentId', 'ownDepartment', 'sort', 'direction', 'page', 'pageSize', 'ids'].map(key => [key, input[key]])),
      dateField: 'plannedTestDate', from: `${prefix}-01`, to: `${prefix}-${new Date(Date.UTC(year, month, 0)).getUTCDate()}`,
    }
  }
  return { query: (input: Record<string, unknown>) => ledger.query(query(input)), export: (input: Record<string, unknown>) => ledger.export(query(input)) }
}
