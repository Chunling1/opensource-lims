import { request } from './http'

export interface ElnRecordStatus {
  id: string
  status: 'DRAFT' | 'PENDING_REVIEW' | 'REVIEWING' | 'REVIEW_REJECTED' | 'FINALIZED' | 'CANCELED'
  revisionNo: number
  template: { code: string; name: string; version: string }
  creator: { id: number; account: string; name: string }
  reviewer?: { id: number; account: string; name: string } | null
  reviewComment?: string
  finalizedAt?: string
}

export interface ElnReportStatus {
  enabled: boolean
  projectId: number | null
  required: boolean
  blocker: string
  canLaunch: boolean
  records: ElnRecordStatus[]
}

export interface ElnDraftPatch {
  path: 'recordNo' | 'result' | 'conclusion' | 'resultStatus' | 'unqualifiedParams' | 'remark'
  value: unknown
  source: string
  revisionNo: number
}

export function fetchElnStatus(reportNo: string) {
  return request<ElnReportStatus>(`/api/eln/reports/${encodeURIComponent(reportNo)}/status`)
}

export function createElnLaunch(reportNo: string) {
  return request<{ url: string; expiresIn: number }>('/api/eln/launch', {
    method: 'POST',
    body: JSON.stringify({ reportNo }),
  })
}

export function createElnWorkspaceLaunch() {
  return request<{ url: string; expiresIn: number }>('/api/eln/launch', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function fetchElnDraft(reportNo: string) {
  return request<{ recordId: string | null; contentHash?: string; patches: ElnDraftPatch[] }>(
    `/api/eln/reports/${encodeURIComponent(reportNo)}/draft`,
  )
}
