import type { EquipmentLedgerRow } from './equipmentLedger'
import type { TableColumn } from '../common/table'
export const overallPlanSections = [
  { label: '量值溯源', fields: [{ key: 'traceMethod', label: '量值溯源方法' }, { key: 'traceOrganization', label: '量值溯源机构' }, { key: 'traceCycle', label: '量值溯源周期' }] },
  { label: '期间核查', fields: [{ key: 'checkRequired', label: '是否要期间核查' }, { key: 'checkMethod', label: '期间核查方法' }, { key: 'checkInterval', label: '期间核查间隔' }] },
  { label: '', fields: [{ key: 'useConditions', label: '使用条件' }] },
  { label: '维护', fields: [{ key: 'maintenanceItems', label: '维护项目' }, { key: 'maintenanceInterval', label: '维护时间间隔' }] },
  { label: '', fields: [{ key: 'controlMeasures', label: '控制措施' }] },
] as const
export const overallPlanFields = overallPlanSections.flatMap(section => [...section.fields])
export type OverallPlanKey = typeof overallPlanFields[number]['key']
export type OverallPlanValues = Record<OverallPlanKey, string>
export interface EquipmentOverallPlan { version: number; values: OverallPlanValues }
export const emptyOverallPlan = (): OverallPlanValues => ({ traceMethod: '', traceOrganization: '', traceCycle: '', checkRequired: '', checkMethod: '', checkInterval: '', useConditions: '', maintenanceItems: '', maintenanceInterval: '', controlMeasures: '' })
export interface OverallPlanRow extends Pick<EquipmentLedgerRow, 'id' | 'code' | 'name' | 'status' | 'model' | 'accuracy' | 'range'>, OverallPlanValues { version: number; equipmentVersion: number }
export const overallPlanSearchFields = [
  { key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'status', label: '设备状态' },
  { key: 'model', label: '规格型号' }, { key: 'accuracy', label: '精度' }, { key: 'range', label: '量程' },
] as const
export const overallPlanOperators = [
  { key: 'contains', label: '包含' }, { key: 'gt', label: '大于' }, { key: 'gte', label: '大于或等于' },
  { key: 'eq', label: '等于' }, { key: 'lt', label: '小于' }, { key: 'lte', label: '小于或等于' },
] as const
export interface OverallPlanQuery {
  field?: typeof overallPlanSearchFields[number]['key']; operator?: typeof overallPlanOperators[number]['key']; value?: string
  page?: number; pageSize?: number; ids?: string[]
}
export interface OverallPlanPage { items: OverallPlanRow[]; total: number; page: number; pageSize: number }
export interface OverallPlanTarget { id: string; version: number; equipmentVersion: number }
export interface OverallPlanSubmission { records: OverallPlanTarget[]; changes: Partial<OverallPlanValues> }
export const overallPlanColumns = [
  { key: 'code', label: '设备编号', required: true },
  ...overallPlanSearchFields.filter(field => field.key !== 'code').map(field => ({ ...field, default: ['name', 'status', 'model'].includes(field.key) })),
  ...overallPlanFields.map(field => ({ ...field, default: ['traceCycle', 'checkRequired', 'checkInterval', 'maintenanceInterval'].includes(field.key), truncate: 18, fullTitle: true })),
] as const satisfies readonly TableColumn<keyof OverallPlanRow>[]
