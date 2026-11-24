import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { InboundQuery, PlanSelectionState } from '../samples/inbound'
import type { FlowRow } from '../samples/flow'

export const completionStates = ['样品待处理', '样品已处理'] as const
export type SampleCompletionAction = 'process' | 'undo'
export type SampleCompletionSubmission = { action: 'process'; result: string } | { action: 'undo' }
export interface SampleCompletionReceipt {
  result: string; customerRequirement: string; retentionTime: string
  processedAt: string; processedBy: { id: string; name: string }
}
export interface SampleCompletionInfo {
  status: typeof completionStates[number]; processedAt?: string
  receipt?: SampleCompletionReceipt; history?: SampleCompletionReceipt[]
}
export interface SampleCompletionQuery extends Omit<InboundQuery, 'status' | 'site'> {
  processingStatus?: string; disposalStatus?: string
}
export const completionDisposalEnabled = (status?: string) => status !== '样品待处理'
export const completionDateEnabled = (status?: string) => status === '样品已处理'
export interface SampleCompletionRow extends FlowRow {
  processingStatus: string; processingTime: string; canProcess: boolean; canUndoProcess: boolean
}
export interface SampleCompletionPage extends RegistrationPage<SampleCompletionRow> { planSelection: PlanSelectionState }
export const sampleCompletionColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'processingStatus', label: '处理状态', default: true },
  { key: 'testPlanName', label: '检测方案', default: true, truncate: 16, fullTitle: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 16, fullTitle: true },
  { key: 'inboundPerson', label: '入库人', default: false },
  { key: 'inboundDate', label: '入库时间', default: false },
  { key: 'outboundPerson', label: '出库人', default: false },
  { key: 'outboundDate', label: '出库时间', default: false },
  { key: 'collectionPerson', label: '领样人', default: false },
  { key: 'collectionDate', label: '领样时间', default: false },
  { key: 'retentionTime', label: '留置时间', default: true },
  { key: 'customerRequirement', label: '客户处置要求', default: true, truncate: 12, fullTitle: true },
  { key: 'disposalResult', label: '处置结果', default: true, truncate: 14, fullTitle: true },
  { key: 'disposalDate', label: '处置时间', default: true },
  { key: 'disposalPerson', label: '处置人', default: false },
  { key: 'disposalStatus', label: '处置状态', default: true },
] as const satisfies readonly TableColumn<Extract<keyof SampleCompletionRow, string>>[]
