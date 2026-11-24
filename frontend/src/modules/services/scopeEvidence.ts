import { request } from './http'

export interface ScopePreview {
  sourceSha256: string
  manifestSha256: string
  parserVersion: string
  counts: Record<string, number>
  standardClasses: Record<string, number>
  cnasItemCount: number
  pairedItemCount: number
  consistentCandidateCount: number
  pairedWithDifferences: number
  unconfirmedCmaItemCount: number
  readyForStaging: boolean
  readyForActivation: boolean
  activationBlockers: string[]
  batchId?: number
  status?: string
  reused?: boolean
}

export function previewScopeEvidence(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<ScopePreview>('/api/admin/scope-evidence/preview', { method: 'POST', body })
}

export function stageScopeEvidence(file: File, manifestSha256: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('manifestSha256', manifestSha256)
  body.append('confirmStagingOnly', '1')
  return request<ScopePreview>('/api/admin/scope-evidence/stage', { method: 'POST', body })
}
