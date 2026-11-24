// Optional saved facts populated by future workflow modules, never inferred from registration dates.
export const sampleWorkflowDateFields = [
  { key: 'testStartDate', label: '检测开始日期' },
  { key: 'testEndDate', label: '检测完成日期' },
  { key: 'checkDate', label: '校核日期' },
  { key: 'auditDate', label: '审核日期' },
  { key: 'approvalDate', label: '批准日期' },
  { key: 'reportDate', label: '报告日期' },
  { key: 'preparationDate', label: '制作日期' },
] as const
export type SampleWorkflowDateKey = typeof sampleWorkflowDateFields[number]['key']
export const sampleConclusions = [{ value: 'qualified', label: '合格' }, { value: 'unqualified', label: '不合格' }] as const
export type SampleConclusion = typeof sampleConclusions[number]['value']
export type SampleWorkflowData = Partial<Record<SampleWorkflowDateKey, string>> & { conclusion?: SampleConclusion; issueDate?: string; archiveDate?: string }
export interface SampleWorkflowQuery {
  dates?: Partial<Record<SampleWorkflowDateKey, { from: string; to: string }>>
  conclusion?: SampleConclusion
}
export type SampleWorkflowDateDraft = Record<SampleWorkflowDateKey, { enabled: boolean; from: string; to: string }>
export function workflowDateDraft(range: { from: string; to: string }): SampleWorkflowDateDraft {
  return Object.fromEntries(sampleWorkflowDateFields.map(({ key }) => [key, { enabled: false, ...range }])) as SampleWorkflowDateDraft
}
