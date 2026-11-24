import type { TableColumn } from '../common/table'
import { inboundColumns, type InboundQuery, type InboundRow, type PlanSelectionState } from './inbound'
import type { RegistrationPage } from '../commissions/registration'

export const flowStates = ['样品已入库', '样品已出库', '样品已领取', '检测已完成', '样品待处置', '样品已处置'] as const
export const flowDateFields = [
  { key: 'inbound', label: '入库时间', stage: 0, column: 'inboundDate' }, { key: 'outbound', label: '出库时间', stage: 1, column: 'outboundDate' },
  { key: 'collection', label: '领样时间', stage: 2, column: 'collectionDate' }, { key: 'disposal', label: '处置时间', stage: 5, column: 'disposalDate' },
] as const
export type FlowDateKey = typeof flowDateFields[number]['key']
export interface FlowDateRange { from: string; to: string }
export function flowDateEnabled(key: FlowDateKey, status?: string) {
  if (!status) return false
  const idx = (flowStates as readonly string[]).indexOf(status)
  const field = flowDateFields.find(item => item.key === key)
  return idx >= 0 && !!field && field.stage <= idx
}
export interface FlowQuery extends InboundQuery { dates?: Partial<Record<FlowDateKey, FlowDateRange>> }
export interface SampleFlowInfo { collection?: { name: string; date: string; account?: string; recordedAt?: string; recordedBy?: { id: string; name: string } }; restock?: { name: string; date: string }; customerSignature?: string }
export interface FlowRow extends InboundRow {
  flowStatus: string; inboundPerson: string; inboundDate: string; outboundPerson: string; outboundDate: string
  restockPerson: string; restockDate: string; collectionPerson: string; collectionDate: string; customerSignature: string
}
export interface FlowPage extends RegistrationPage<FlowRow> { planSelection: PlanSelectionState }
export const flowColumns = [
  inboundColumns[0],
  inboundColumns[1],
  inboundColumns.find(column => column.key === 'reportCode')!,
  { key: 'testPlanName', label: '检测方案', default: true, truncate: 14, fullTitle: true },
  { ...inboundColumns.find(column => column.key === 'name')!, default: false },
  { key: 'inboundPerson', label: '入库人', default: false, truncate: 12, fullTitle: true },
  { key: 'inboundDate', label: '入库时间', default: true },
  { key: 'outboundPerson', label: '出库人', default: false, truncate: 12, fullTitle: true },
  { key: 'outboundDate', label: '出库时间', default: true },
  { key: 'restockPerson', label: '回库人', default: false, truncate: 12, fullTitle: true },
  { key: 'restockDate', label: '回库时间', default: false },
  { key: 'collectionPerson', label: '领样人', default: false, truncate: 12, fullTitle: true },
  { key: 'collectionDate', label: '领样时间', default: true },
  { key: 'retentionTime', label: '留置时间', default: false },
  { key: 'customerRequirement', label: '客户处置要求', default: true, truncate: 12, fullTitle: true },
  { key: 'disposalResult', label: '处置结果', default: false, truncate: 14, fullTitle: true },
  { key: 'disposalDate', label: '处置时间', default: false },
  { key: 'disposalPerson', label: '处置人', default: false, truncate: 12, fullTitle: true },
  { key: 'disposalStatus', label: '处置状态', default: true },
  { ...inboundColumns.find(column => column.key === 'contractCode')!, default: false },
  ...inboundColumns.slice(inboundColumns.findIndex(column => column.key === 'customer')).map(column => ({ ...column, default: false })),
] as const satisfies readonly TableColumn<Extract<keyof FlowRow, string>>[]
