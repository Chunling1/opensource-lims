import type { RegistrationCommissionRow, RegistrationSampleRow } from '../../types/commissions/registration'

import type { TableColumn } from '../../types/common/table'
import { parseTableColumns, tableCellText } from '../common/table'

// Fixed display/export order; route settings control visibility only.
export const commissionColumns = [
  { key: 'contract', label: '合同编号', default: false },
  { key: 'code', label: '委托编号', default: true, required: true, sort: 'code' },
  { key: 'owner', label: '委托经办人', default: true },
  { key: 'customer', label: '委托单位', default: true, wrap: true },
  { key: 'name', label: '样品/工程名称', default: true, wrap: true },
  { key: 'status', label: '委托状态', default: true },
  { key: 'commissionDate', label: '委托日期', default: true, sort: 'commissionDate' },
  { key: 'receivableAmount', label: '应收费用', default: true, money: true },
  { key: 'contact', label: '委托人', default: false },
  { key: 'constructionUnit', label: '建设单位', default: false, wrap: true },
  { key: 'constructionCompany', label: '施工单位', default: false, wrap: true },
] as const satisfies readonly TableColumn<Extract<keyof RegistrationCommissionRow, string>>[]
export type CommissionColumnKey = typeof commissionColumns[number]['key']
export const defaultCommissionColumns = commissionColumns.filter(column => column.default).map(column => column.key)
export function parseCommissionColumns(value: unknown, legacyContract?: unknown): CommissionColumnKey[] {
  if (typeof value !== 'string' && legacyContract === '1') return parseTableColumns(commissionColumns.map(column => ({ ...column, default: column.default || column.key === 'contract' })), value)
  return parseTableColumns(commissionColumns, value)
}
export function commissionCell(row: RegistrationCommissionRow, key: CommissionColumnKey): string {
  return tableCellText(row[key], commissionColumns.find(column => column.key === key)! as TableColumn)
}

export const sampleColumns = [
  { key: 'code', label: '样品编号', default: true, required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'commissionOwner', label: '委托经办人', default: false },
  { key: 'owner', label: '样品登记人', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'name', label: '样品/工程名称', default: true, wrap: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 20, fullTitle: true },
  { key: 'dataStatus', label: '数据状态', default: true },
  { key: 'testPlan', label: '检测方案', default: false, wrap: true },
  { key: 'customer', label: '委托单位', default: true, wrap: true },
  { key: 'projectName', label: '项目名称', default: false, wrap: true },
  { key: 'standardPrice', label: '标准价格费用', default: false, money: true },
  { key: 'discountPrice', label: '折扣价格费用', default: false, money: true },
  { key: 'actualPrice', label: '实际价格费用', default: false, money: true },
  { key: 'attachmentCount', label: '附件', default: false },
] as const satisfies readonly TableColumn<Extract<keyof RegistrationSampleRow, string>>[]
export type SampleColumnKey = typeof sampleColumns[number]['key']
export function sampleCell(row: RegistrationSampleRow, key: SampleColumnKey): string {
  if (key === 'attachmentCount') return row.attachmentCount > 0 ? '有' : ''
  return tableCellText(row[key], sampleColumns.find(column => column.key === key)! as TableColumn)
}
