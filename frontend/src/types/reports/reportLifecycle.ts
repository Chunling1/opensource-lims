import type { TableColumn } from '../common/table'

export type ReportForm = '纸质' | '电子'
export type SigningStatus = '待签章' | '签章中' | '待确认' | '签章失败' | '签章完成'
export type ReportQueue = 'print' | 'signing' | 'distribution' | 'archive'
export type ReportOperation = 'preview' | 'print' | 'attachments' | 'complete-print' | 'undo-print' | 'progress' | 'retry' | 'download' | 'distribute' | 'undo-distribute' | 'reprice' | 'archive' | 'undo-archive' | 'print-report' | 'print-task' | 'print-commission'
export interface FrozenReportFile { id: string; name: string; sha256: string; base64: string }
export interface SigningConfig { provider: string; sealId: string; signers: string[]; positions: { kind: 'signature' | 'seal'; page: number; x: number; y: number }[] }
export interface SigningTask {
  id: string; key: string; attempt: number; status: SigningStatus; externalId?: string
  signature: '待处理' | '已完成'; seal: '待处理' | '已完成'; error?: string; updatedAt: string
  attempts?: { attempt: number; key: string; externalId?: string; status: SigningStatus; error?: string; endedAt: string }[]
  events: { at: string; status: SigningStatus; message: string }[]
}
export interface DistributionReceipt { trackingNumber?: string; mailingAddress?: string; recipient: string; method: string; date: string; notes: string; at: string; actorId: string; actorName: string }
export interface ReportRelease {
  id: string; revision: number; form: ReportForm; approvedAt: string; approvedBy: { id: string; name: string }
  people: { checker: string; reviewer: string; approver: string }; sourceTaskId: string; original: FrozenReportFile; signed?: FrozenReportFile
  signingConfig?: SigningConfig; signing?: SigningTask; printStatus: '待打印' | '打印完成' | '不适用'
  distributionStatus: '未发放' | '已发放'; archiveStatus: '待归档' | '已归档'; receipt?: DistributionReceipt
  archive?: { date: string; at: string; actorId: string; actorName: string }
  supersededAt?: string; history: { at: string; actorId: string; actorName: string; action: string; reason: string }[]
}
export interface ReportLifecycleRow {
  id: string; version: number; releaseId: string; code: string; reportCode: string; name: string; customer: string; testPlan: string
  form: string; revision: number; approvedAt: string; printStatus: string; signingStatus: string; distributionStatus: string; archiveStatus: string
  recipient: string; distributionDate: string; actualPrice: number | null; unavailableReason: string
  actions: { id: ReportOperation; label: string; enabled: boolean; reason?: string }[]
}
export interface ReportLifecycleQuery { queue: ReportQueue; keyword?: string; form?: string; status?: string; from?: string; to?: string; page?: number; pageSize?: number }
export interface ReportLifecyclePage { items: ReportLifecycleRow[]; total: number; page: number; pageSize: number }
export const reportQueueTitles: Record<ReportQueue, string> = { print: '报告打印', signing: '报告签章', distribution: '报告发放', archive: '报告归档' }
export const reportOperationLabels: Record<ReportOperation, string> = { preview: '预览', print: '打印', attachments: '查看附件', 'complete-print': '打印完成', 'undo-print': '撤销打印完成', progress: '查看签章进度', retry: '重试签章', download: '下载报告', distribute: '发放', 'undo-distribute': '撤销发放', reprice: '重新计价', archive: '归档', 'undo-archive': '撤销归档', 'print-report': '打印报告', 'print-task': '打印任务单', 'print-commission': '打印委托书' }
export const reportOperationIcons: Record<ReportOperation, string> = { preview: 'ti ti-file-search', print: 'ti ti-printer', attachments: 'ti ti-paperclip', 'complete-print': 'ti ti-circle-check', 'undo-print': 'ti ti-arrow-back-up', progress: 'ti ti-clock', retry: 'ti ti-refresh', download: 'ti ti-download', distribute: 'ti ti-send', 'undo-distribute': 'ti ti-arrow-back-up', reprice: 'ti ti-currency-yen', archive: 'ti ti-archive', 'undo-archive': 'ti ti-arrow-back-up', 'print-report': 'ti ti-printer', 'print-task': 'ti ti-printer', 'print-commission': 'ti ti-printer' }
export const reportLifecycleColumns: TableColumn<keyof ReportLifecycleRow>[] = [
  { key: 'code', label: '样品编号', required: true }, { key: 'reportCode', label: '报告编号', default: true },
  { key: 'name', label: '样品/工程名称', default: true }, { key: 'form', label: '报告形式', default: true },
  { key: 'testPlan', label: '检测方案' }, { key: 'customer', label: '委托单位' }, { key: 'revision', label: '报告版本' },
  { key: 'approvedAt', label: '批准时间' }, { key: 'printStatus', label: '打印状态', default: true },
  { key: 'signingStatus', label: '签章状态', default: true }, { key: 'distributionStatus', label: '发放状态', default: true },
  { key: 'archiveStatus', label: '归档状态' }, { key: 'recipient', label: '接收人' }, { key: 'distributionDate', label: '发放日期' },
  { key: 'actualPrice', label: '实际价格费用', money: true }, { key: 'unavailableReason', label: '提示', default: true, wrap: true },
]
