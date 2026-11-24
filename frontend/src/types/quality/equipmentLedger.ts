import type { TableColumn } from '../common/table'

export const equipmentStates = ['可用', '停用', '限制使用', '报废'] as const
export type EquipmentStatus = typeof equipmentStates[number]
export const equipmentStatusClasses: Record<EquipmentStatus, string> = {
  可用: 'bg-light text-body', 停用: 'bg-danger-subtle text-danger', 限制使用: 'bg-warning-subtle text-warning-emphasis', 报废: 'bg-info-subtle text-info-emphasis',
}
export const equipmentDateFields = [
  { key: 'lastTestDate', label: '最近检定/测试日期' }, { key: 'plannedTestDate', label: '计划检定/测试日期' },
  { key: 'actualTestDate', label: '实际检定/测试日期' }, { key: 'purchasedAt', label: '购入日期' },
] as const
export interface EquipmentLedgerRow {
  version?: number
  id: string; code: string; name: string; model: string; serial: string; manufacturer: string; testOrganization: string
  status: EquipmentStatus; departmentId: string; department: string; location: string; lastTestDate: string; cycle: string
  plannedTestDate: string; actualTestDate: string; notes: string; range: string; accuracy: string; keeper: string
  purchasedAt: string; price: number | null; usageRecordCount: number; manualCount: number; certificateCount: number; acceptanceCount: number
}
export const equipmentLedgerColumns = [
  { key: 'code', label: '设备编号', required: true, sort: 'code' },
  { key: 'name', label: '仪器设备名称', default: true, truncate: 18, fullTitle: true },
  { key: 'model', label: '规格型号', default: true }, { key: 'serial', label: '仪器出厂号', default: true },
  { key: 'manufacturer', label: '生产厂家', default: true, truncate: 18, fullTitle: true },
  { key: 'testOrganization', label: '检定/测试单位', truncate: 18, fullTitle: true },
  { key: 'status', label: '设备状态', default: true }, { key: 'department', label: '所属部门', default: true },
  { key: 'location', label: '放置单位' }, { key: 'lastTestDate', label: '最近检定/测试日期', sort: 'lastTestDate' },
  { key: 'cycle', label: '周期' }, { key: 'plannedTestDate', label: '计划检定/测试日期', sort: 'plannedTestDate' },
  { key: 'actualTestDate', label: '实际检定/测试日期', sort: 'actualTestDate' },
  { key: 'notes', label: '备注', truncate: 24, fullTitle: true },
  { key: 'range', label: '量程' }, { key: 'accuracy', label: '准确度' }, { key: 'keeper', label: '仪器保管人' },
  { key: 'purchasedAt', label: '购入日期', sort: 'purchasedAt' }, { key: 'price', label: '购入价格', money: true },
  { key: 'usageRecordCount', label: '使用记录' }, { key: 'manualCount', label: '说明书' },
  { key: 'certificateCount', label: '合格证' }, { key: 'acceptanceCount', label: '验收单' },
] as const satisfies readonly TableColumn<keyof EquipmentLedgerRow>[]
export type EquipmentLedgerColumn = typeof equipmentLedgerColumns[number]['key']
export interface EquipmentLedgerQuery {
  code?: string; name?: string; manufacturer?: string; serial?: string; departmentId?: string; status?: string
  dateField?: typeof equipmentDateFields[number]['key'] | ''; from?: string; to?: string; ownDepartment?: boolean; unassociated?: boolean
  sort?: string; direction?: 'asc' | 'desc'; page?: number; pageSize?: number; ids?: string[]
}
export interface EquipmentLedgerPage { items: EquipmentLedgerRow[]; total: number; page: number; pageSize: number; departments: { id: string; name: string }[] }
