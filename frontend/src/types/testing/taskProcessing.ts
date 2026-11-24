import type { DemoAttachment, DemoEvent, RegistrationPage } from '../commissions/registration'
import type { TableColumn } from '../common/table'

export interface TaskProcessingInput {
  requestId: string; account: string; name: string; date: string
  contactMethod: string; contactTarget: string; content: string; notes: string
}
export interface TaskProcessingRecord extends TaskProcessingInput {
  id: string; sampleId: string; sampleCode: string; sampleName: string; testPlan: string; version: number
  submittedAt: string; submittedBy: { id: string; name: string }
  attachments: DemoAttachment[]; events: DemoEvent[]
}
export type TaskProcessingRow = Omit<TaskProcessingRecord, 'requestId' | 'attachments' | 'events'> & { attachmentCount: number }
export interface TaskProcessingDetail extends TaskProcessingRow { canManageAttachments: boolean }
export interface TaskProcessingAttachments extends TaskProcessingDetail { attachments: DemoAttachment[] }
export interface TaskProcessingQuery { handler?: string; from?: string; to?: string; page?: number; pageSize?: number }
export interface TaskProcessingPage extends RegistrationPage<TaskProcessingRow> {
  sample: { id: string; code: string; name: string; testPlan: string }
  canCreate: boolean
}
export const taskProcessingColumns = [
  { key: 'sequence', label: '序号' },
  { key: 'testPlan', label: '检测方案', truncate: 14, fullTitle: true },
  { key: 'sampleName', label: '样品/工程名称', truncate: 14, fullTitle: true },
  { key: 'name', label: '处理人' }, { key: 'date', label: '处理时间' },
  { key: 'contactMethod', label: '联系方式', truncate: 14, fullTitle: true },
  { key: 'contactTarget', label: '沟通对象', truncate: 14, fullTitle: true },
  { key: 'content', label: '处理内容', truncate: 20, fullTitle: true },
  { key: 'notes', label: '备注', truncate: 20, fullTitle: true },
  { key: 'attachmentCount', label: '附件' },
] as const satisfies readonly TableColumn<keyof TaskProcessingRow | 'sequence'>[]
