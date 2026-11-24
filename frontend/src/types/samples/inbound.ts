import type { TableColumn } from '../common/table'
import type { OutboundAction } from './outbound'
import type { DisposalAction, DisposalFields } from './disposal'
import type { RegistrationPage, RegistrationSampleRow } from '../commissions/registration'
export interface PlanSelection { groupIds: string[]; planIds: string[]; excludedPlanIds: string[] }
export const emptyPlanSelection = (): PlanSelection => ({ groupIds: [], planIds: [], excludedPlanIds: [] })
export interface PlanSelectionState {
  selection: PlanSelection; count: number; total: number; previews: { id: string; name: string }[]
  groups: Record<string, { checked: boolean; indeterminate: boolean }>
  populated?: { count: number; total: number; groups: PlanSelectionState['groups'] }
}
export interface PlanSelectionToggle { kind: 'group' | 'plan' | 'all'; id: string; checked: boolean; populatedOnly?: boolean }
export interface PlanSelectionCatalogue {
  groups: { id: string }[]
  plans: { id: string; parentId: string; name: string }[]
  populatedPlanIds?: string[]
}
export interface PlanSelectionContext extends PlanSelectionState { catalogue: PlanSelectionCatalogue }
export const inboundStates = ['样品入库中', '样品入库完成'] as const
export type InboundAction = 'receive' | 'undo'
export const inboundLocations = ['检测室', '样品室', '标养室'] as const
export const inboundConditions = ['正常', '异常'] as const
export interface InboundReceipt {
  account: string; name: string; date: string
  location: typeof inboundLocations[number]; condition: typeof inboundConditions[number]; notes: string
}
export interface SavedInboundReceipt extends InboundReceipt { recordedAt: string; recordedBy: { id: string; name: string } }
export interface InboundQuery {
  code?: string; status?: string; from?: string; to?: string; site?: string; plans?: PlanSelection
  page?: number; pageSize?: number; sort?: 'code' | 'commissionDate'; direction?: 'asc' | 'desc'; ids?: string[]
}
export interface InboundRow extends RegistrationSampleRow, Partial<DisposalFields> {
  outboundActions?: OutboundAction[]
  disposalActions?: DisposalAction[]
  commissionDate: string; site: string; groupNumber: string; contractCode: string
  customerAddress: string; contact: string; phone: string; manufacturer: string; notes: string; mailingAddress: string
}
export interface InboundPage extends RegistrationPage<InboundRow> { sites: string[]; planSelection: PlanSelectionState }
export const inboundColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'dataStatus', label: '数据状态', default: true },
  { key: 'testPlanName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 14, fullTitle: true },
  { key: 'commissionDate', label: '委托日期', default: true, sort: 'commissionDate' },
  { key: 'owner', label: '样品登记人', default: true },
  { key: 'contractCode', label: '合同编号', default: false },
  { key: 'customer', label: '委托单位', default: true, truncate: 18, fullTitle: true },
  { key: 'customerAddress', label: '委托单位地址', default: false, truncate: 18, fullTitle: true },
  { key: 'contact', label: '委托人', default: false, truncate: 12, fullTitle: true },
  { key: 'phone', label: '委托人电话', default: false },
  { key: 'manufacturer', label: '生产单位', default: false, truncate: 18, fullTitle: true },
  { key: 'notes', label: '备注', default: false, truncate: 18, fullTitle: true },
  { key: 'mailingAddress', label: '邮寄地址', default: false, truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<Extract<keyof InboundRow, string>>[]
