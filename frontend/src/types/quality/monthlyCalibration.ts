import type { EquipmentLedgerQuery } from './equipmentLedger'

export interface MonthlyCalibrationQuery extends Pick<EquipmentLedgerQuery, 'code' | 'name' | 'manufacturer' | 'serial' | 'departmentId' | 'ownDepartment' | 'sort' | 'direction' | 'page' | 'pageSize' | 'ids'> {
  year: number
  month: number
}
