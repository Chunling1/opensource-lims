import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
import type { RegistrationSampleRow } from './registration'

export const cancellationRoot = '/commissions/cancellation-approval'
export function cancellationDate(value: string) { return value ? new Date(value).toLocaleDateString('sv-SE') : '—' }
export const cancellationStates = ['申请中', '申请通过', '申请不通过'] as const
export type CancellationState = typeof cancellationStates[number]
export type CancellationDecision = 'approved' | 'rejected'
export const canApproveCancellation = (actor: Actor) => actor.roles.some(role => ['admin', 'approver'].includes(role))
export interface CancellationQuery {
  from?: string; to?: string; result?: CancellationState | ''; page?: number; pageSize?: number; ids?: string[]
  sort?: 'code' | 'appliedAt' | 'approvedAt'; direction?: 'asc' | 'desc'
}
export interface CancellationRow extends RegistrationSampleRow {
  approvalResult: CancellationState; applicant: string; applicationReason: string; appliedAt: string
  approver: string; rejectionReason: string; approvedAt: string
}
export interface CancellationSubmission { version: number; decision: CancellationDecision; reason: string }
export const cancellationColumns = [
  { key: 'approvalResult', label: '审批结果', default: true },
  { key: 'commissionCode', label: '委托编号', default: true },
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'testPlan', label: '检测方案', default: false, truncate: 20, fullTitle: true },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 14, fullTitle: true },
  { key: 'applicant', label: '申请人', default: true },
  { key: 'applicationReason', label: '申请原因', default: true, truncate: 20, fullTitle: true },
  { key: 'appliedAt', label: '申请日期', default: true, sort: 'appliedAt' },
  { key: 'approver', label: '审批人', default: false },
  { key: 'rejectionReason', label: '审批不通过原因', default: false, truncate: 20, fullTitle: true },
  { key: 'approvedAt', label: '审批日期', default: false, sort: 'approvedAt' },
] as const satisfies readonly TableColumn<Extract<keyof CancellationRow, string>>[]
export type CancellationColumnKey = typeof cancellationColumns[number]['key']
