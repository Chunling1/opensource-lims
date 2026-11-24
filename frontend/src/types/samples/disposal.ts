import type { TableColumn } from '../common/table'
import { inboundColumns, type InboundRow, type InboundQuery } from './inbound'

export const disposalStates = ['样品待处置', '样品已处置'] as const
export const disposalRequirements = ['中心处置', '客户取回'] as const
export const disposalSearchFields = [
  { value: 'code', label: '样品编号' }, { value: 'reportCode', label: '报告编号' },
  { value: 'contractCode', label: '合同编号' }, { value: 'commissionCode', label: '委托编号' },
  { value: 'name', label: '样品/工程名称' }, { value: 'customer', label: '委托单位名称' },
  { value: 'customerAddress', label: '委托单位地址' }, { value: 'contact', label: '委托人' },
  { value: 'phone', label: '委托人电话' }, { value: 'manufacturer', label: '生产单位' },
  { value: 'notes', label: '备注' }, { value: 'mailingAddress', label: '邮寄地址' },
] as const
export interface DisposalQuery extends InboundQuery {
  searchField?: typeof disposalSearchFields[number]['value']; keyword?: string; requirement?: string
}

export type DisposalAction = 'dispose' | 'undo'
export interface DisposalReceipt { result: string; name: string; date: string }
export type DisposalSubmission = { action: 'dispose'; receipt: DisposalReceipt } | { action: 'undo' }
export interface SavedDisposalReceipt extends DisposalReceipt { customerRequirement: string; recordedAt: string; recordedBy: { id: string; name: string } }
export interface DisposalInfo {
  retentionTime?: string
  receipt?: SavedDisposalReceipt
  history?: SavedDisposalReceipt[]
}
export interface DisposalFields {
  testPlanName: string; retentionTime: string; customerRequirement: string
  disposalResult: string; disposalDate: string; disposalPerson: string; disposalStatus: string
}
export const disposalColumns = [
  inboundColumns[0], inboundColumns[1],
  inboundColumns.find(column => column.key === 'reportCode')!,
  { key: 'testPlanName', label: '检测方案', default: true, truncate: 14, fullTitle: true },
  inboundColumns.find(column => column.key === 'name')!,
  { key: 'retentionTime', label: '留置时间', default: true },
  { key: 'customerRequirement', label: '客户处置要求', default: true, truncate: 12, fullTitle: true },
  { key: 'disposalResult', label: '处置结果', default: true, truncate: 14, fullTitle: true },
  { key: 'disposalDate', label: '处置时间', default: true },
  { key: 'disposalPerson', label: '处置人', default: false, truncate: 12, fullTitle: true },
  { key: 'disposalStatus', label: '处置状态', default: true },
  ...inboundColumns.slice(inboundColumns.findIndex(column => column.key === 'contractCode')).map(column => ({ ...column, default: false })),
] as const satisfies readonly TableColumn<Extract<keyof InboundRow, string>>[]
