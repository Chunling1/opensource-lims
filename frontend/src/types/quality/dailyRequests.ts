import type { DemoAttachment } from '../commissions/registration'
import type { TableColumn } from '../common/table'
import type { Actor } from '../lims'
export const canApplyDailyRequests = (actor: Actor) => actor.active !== false && !!actor.id && actor.roles.length > 0
export const canApproveDailyRequests = (actor: Actor) => canApplyDailyRequests(actor) && actor.roles.some(role => ['admin', 'approver'].includes(role))
export type DailyApprovalOperation = 'approve' | 'revoke' | 'void'
export type DailyRequestMode = 'new' | 'edit' | 'view' | 'withdraw' | 'delete' | DailyApprovalOperation
export const dailyRequestItems = ['加盖中心公章', '加盖检测合同章', '领取营业执照复印件', '领取关系说明', '领取中心资质', '盖检测中心章', '盖院公章', '其他'] as const
export const dailyRequestStatuses = ['申请中', '待审批', '退回', '不通过', '审批通过', '已作废'] as const
export interface DailyRequestDraft { reason: string; items: string[]; other: string; copies: number | null; files: DemoAttachment[] }
export interface DailyRequestRecord extends DailyRequestDraft {
  id: string; version: number; code: string; departmentId: string; department: string; applicantId: string; applicant: string
  appliedAt: string; status: typeof dailyRequestStatuses[number]; withdrawalReason: string; deletedAt?: string
  approval?: { result: '审批通过' | '不通过'; opinion: string; actorId: string; actor: string; at: string }
  voidReason?: string
  events: { at: string; actorId: string; actor: string; action: string; reason: string }[]
}
export interface DailyRequestRow extends DailyRequestRecord { matters: string; canEdit: boolean; canWithdraw: boolean; canDelete: boolean; canApprove: boolean; canRevoke: boolean; canVoid: boolean }
export interface DailyRequestQuery { from?: string; to?: string; code?: string; departmentId?: string; applicant?: string; reason?: string; item?: string; status?: string; page?: number; pageSize?: number; ids?: string[] }
export interface DailyRequestPage { items: DailyRequestRow[]; total: number; page: number; pageSize: number }
export const dailyRequestColumns = [
  { key: 'code', label: '申请单号', required: true },
  { key: 'department', label: '申请部门', default: true },
  { key: 'applicant', label: '申请人', default: true },
  { key: 'reason', label: '办理事由', default: true, truncate: 24, fullTitle: true },
  { key: 'matters', label: '办理事项', default: true, truncate: 24, fullTitle: true },
  { key: 'copies', label: '份数', default: true },
  { key: 'appliedAt', label: '申请时间', default: true },
  { key: 'status', label: '审批状态', default: true },
  { key: 'withdrawalReason', label: '撤回原因', truncate: 24, fullTitle: true },
] as const satisfies readonly TableColumn<keyof DailyRequestRow>[]
