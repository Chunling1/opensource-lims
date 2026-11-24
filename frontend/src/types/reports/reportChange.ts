import type { TableColumn } from '../common/table'
import type { DemoAttachment } from '../commissions/registration'
export type ReportChangeSource = 'internal' | 'external'
export interface ExternalReportChange {
  handlerId: string; handlerName: string; isCommissionCustomer: boolean
  evidence: DemoAttachment[]
  allReturned: boolean
}
export const reportChangeStatuses = ['申请中', '待审批', '退回', '不通过', '审批通过'] as const
export const reportChangeTypes = ['委托信息更改', '检测数据更改', '委托信息更改和检测数据更改', '补充报告'] as const
export interface ReportChangeReference { sampleId: string; sampleVersion: number; releaseId: string; sampleCode?: string; reportCode?: string }
export interface ReportChangeDraft {
  sampleId: string; sampleVersion: number; releaseId: string
  reports?: ReportChangeReference[]
  external?: ExternalReportChange
  changeType: typeof reportChangeTypes[number]
  responsibility: string; before: string; after: string; reason: string; charge: boolean; amount: number
}
export interface ReportChangeRecord extends ReportChangeDraft {
  source?: ReportChangeSource
  id: string; version: number; code: string; departmentId: string; department: string; applicantId: string; applicant: string
  appliedAt: string; status: typeof reportChangeStatuses[number]; sampleCode: string; reportCode: string; withdrawalReason: string
  deletedAt?: string
  events: { at: string; actorId: string; actor: string; action: string; reason: string }[]
}
export interface ReportChangeRow extends ReportChangeRecord { canEdit: boolean; canWithdraw: boolean; canDelete: boolean }
export interface ReportChangeQuery {
  from?: string; to?: string; code?: string; departmentId?: string; applicant?: string; sampleCode?: string; status?: string
  sort?: 'code' | 'appliedAt' | 'sampleCode'; direction?: 'asc' | 'desc'; page?: number; pageSize?: number; ids?: string[]
}
export interface ReportChangePage { items: ReportChangeRow[]; total: number; page: number; pageSize: number }
export interface ReportChangeCandidate { id: string; version: number; releaseId: string; code: string; reportCode: string; name: string; contractCode: string; commissionCode: string; commissionId: string }
export interface ReportChangeCandidateQuery { keyword?: string; commissionCode?: string; reportCode?: string }
export const reportChangeColumns = [
  { key: 'code', label: '申请单号', required: true, sort: 'code' },
  { key: 'department', label: '申请部门' }, { key: 'applicant', label: '申请人', default: true },
  { key: 'appliedAt', label: '申请时间', default: true, sort: 'appliedAt' }, { key: 'status', label: '审批状态', default: true },
  { key: 'sampleCode', label: '样品编号', default: true, sort: 'sampleCode' }, { key: 'reportCode', label: '原报告编号', default: true },
  { key: 'responsibility', label: '更改责任方' },
  { key: 'before', label: '更改前内容', truncate: 20, fullTitle: true },
  { key: 'after', label: '更改后内容', truncate: 20, fullTitle: true },
  { key: 'reason', label: '更改原因', default: true, truncate: 20, fullTitle: true },
  { key: 'charge', label: '是否需要收费' }, { key: 'amount', label: '收费金额', money: true },
  { key: 'withdrawalReason', label: '撤回原因', truncate: 20, fullTitle: true },
] as const satisfies readonly TableColumn<keyof ReportChangeRow>[]
