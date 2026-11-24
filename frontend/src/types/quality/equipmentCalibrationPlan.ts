import type { TableColumn } from '../common/table'
import type { OverallPlanQuery } from './equipmentOverallPlan'
export const calibrationPlanFields = [
  { key: 'model', label: '规格型号' }, { key: 'accuracy', label: '精度' }, { key: 'range', label: '量程' },
  { key: 'manufacturer', label: '生产厂家', wide: true }, { key: 'serial', label: '出厂编号' },
  { key: 'department', label: '使用部门' }, { key: 'cycle', label: '检定周期' },
  { key: 'testDate', label: '检定日期', date: true }, { key: 'organization', label: '检定单位' },
  { key: 'fee', label: '检定费用', money: true }, { key: 'validDate', label: '有效日期', date: true },
  { key: 'notes', label: '备注', area: true, full: true },
] as const
export type CalibrationPlanTextKey = Exclude<typeof calibrationPlanFields[number]['key'], 'fee'>
export type CalibrationPlanValues = Record<CalibrationPlanTextKey, string> & { fee: number | null }
export interface CalibrationPlanRecord { version: number; submitted: boolean; values: CalibrationPlanValues; submissions: { version: number; submittedAt: string; values: CalibrationPlanValues }[] }
export interface CalibrationPlanRow extends CalibrationPlanValues { id: string; code: string; name: string; status: string; version: number; equipmentVersion: number; submitted: boolean }
export interface CalibrationPlanQuery extends OverallPlanQuery { from?: string; to?: string }
export interface CalibrationPlanPage { items: CalibrationPlanRow[]; total: number; page: number; pageSize: number }
export interface CalibrationPlanSubmission { id: string; version: number; equipmentVersion: number; values: CalibrationPlanValues }
export const calibrationPlanColumns = ([
  { key: 'code', label: '设备编号', required: true }, { key: 'name', label: '设备名称', truncate: 18, fullTitle: true },
  { key: 'model', label: '规格型号' }, { key: 'manufacturer', label: '制造厂', truncate: 18, fullTitle: true },
  { key: 'serial', label: '出厂编号' }, { key: 'department', label: '使用部门' }, { key: 'cycle', label: '检定周期' },
  { key: 'testDate', label: '检定日期' }, { key: 'organization', label: '检定单位', truncate: 18, fullTitle: true },
  { key: 'validDate', label: '有效日期' }, { key: 'fee', label: '检定费用', money: true },
  { key: 'notes', label: '备注', truncate: 24, fullTitle: true },
] as const).map(column => ({ ...column, default: ['code', 'name', 'model', 'department', 'cycle', 'testDate', 'validDate'].includes(column.key) })) satisfies readonly TableColumn<keyof CalibrationPlanRow>[]
