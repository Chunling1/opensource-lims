import { ApiError, authedFetch, request } from './http'

export interface EsignBinding {
  id?: number
  userId: number
  personnelId?: number | null
  account: string
  userName: string
  legalName: string
  psnAccountMasked: string
  psnAccountKind?: 'mobile' | 'email'
  psnId: string
  status: 'unbound' | 'pending' | 'verified' | 'disabled' | 'invalid' | 'no_account'
  verifiedAt?: string
  lastCheckedAt?: string
  updatedAt?: string
}

export interface EsignSigner {
  id: number
  roleCode: 'chief' | 'reviewer' | 'approver'
  roleName: string
  userId: number
  account: string
  userName: string
  legalName: string
  bindingStatus: string
  signOrder: number
  status: string
  signedAt: string
  errorMessage: string
}

export interface EsignFlow {
  id: number
  reportNo: string
  documentVersionId: number
  attemptNo: number
  provider: string
  providerFlowId: string
  status: string
  sourceSha256: string
  signedSha256: string
  errorCode: string
  errorMessage: string
  canDownloadSealed?: boolean
  canConfirmSeal?: boolean
  canCancel?: boolean
  signingMode?: string
  flowKind?: 'person_signing' | 'organization_seal'
  organizationSeal?: {
    confirmation?: { userName: string; confirmedAt: string; sourceFlowId: number; sourceSha256: string }
    included?: boolean
    status?: string
    sealMode?: 'default' | 'assigned'
    normalSealPage?: string
    normalSealScope?: string
    acrossPageMode?: string
    completedAt?: string
  }
  hasSignedFile?: boolean
  positioning?: {
    businessStages?: { mode: string }
    mode?: 'keyword' | 'manual'
    status?: string
    errorCode?: string
    errorMessage?: string
    positions?: Record<string, { positionPage: string; positionX: number; positionY: number }>
  }
  dispatchedAt: string
  completedAt: string
  createdAt: string
  signers: EsignSigner[]
  myRole?: string
  myStatus?: string
  canSign?: boolean
}

export function fetchMyEsignBinding() {
  return request<EsignBinding>('/api/esign/me')
}

export function fetchMyEsignTasks() {
  return request<{ rows: EsignFlow[] }>('/api/esign/tasks').then((data) => data.rows)
}

export interface StageTask {
  id: number
  reportNo: string
  myRole: string
  providerFlowId: string | null
  errorMessage: string | null
}
export function fetchPendingStages() {
  return request<{ rows: StageTask[] }>('/api/esign/tasks/stage-pending').then(data => data.rows)
}

export function refreshMyEsignTask(flowId: number) {
  return request<EsignFlow>(`/api/esign/tasks/${flowId}/refresh`, { method: 'POST' })
}
export function resumeEsignStage(flowId: number) {
  return request<{ esignPrepareError?: string }>(`/api/esign/tasks/${flowId}/resume-stage`, { method: 'POST' })
}
export function fetchReportEsignFlow(reportNo: string) {
  return request<EsignFlow | null>(`/api/esign/reports/${encodeURIComponent(reportNo)}`)
}

export function prepareReportEsignFlow(reportNo: string) {
  return request<EsignFlow>(`/api/esign/reports/${encodeURIComponent(reportNo)}/prepare`, { method: 'POST' })
}

export function startOrganizationSeal(reportNo: string, sourceFlowId: number, sourceSha256: string) {
  return request<EsignFlow>(`/api/esign/reports/${encodeURIComponent(reportNo)}/organization-seal`, {
    method: 'POST', body: JSON.stringify({ confirmed: true, sourceFlowId, sourceSha256 }),
  })
}

export function dispatchEsignFlow(flowId: number) {
  return request<EsignFlow>(`/api/esign/flows/${flowId}/dispatch`, { method: 'POST' })
}

export function refreshEsignFlow(flowId: number) {
  return request<EsignFlow>(`/api/esign/flows/${flowId}/refresh`, { method: 'POST' })
}

export function cancelEsignFlow(flowId: number, reason: string) {
  return request<EsignFlow>(`/api/esign/flows/${flowId}/cancel`, {
    method: 'POST', body: JSON.stringify({ confirmed: true, reason }),
  })
}

export async function downloadEsignSignedPdf(flowId: number, reportNo: string) {
  const response = await authedFetch(`/api/esign/flows/${flowId}/signed-pdf`)
  if (!response.ok) {
    let message = `签章 PDF 下载失败：${response.statusText}`
    let code: number | string = response.status
    try {
      const payload = await response.json() as { code?: number | string; message?: string }
      message = payload.message || message
      code = payload.code ?? code
    } catch {
      /* binary/error response without JSON */
    }
    throw new ApiError(message, response.status, code)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const fallback = `${reportNo}-signed-sealed.pdf`
  const filename = encoded ? decodeURIComponent(encoded) : fallback
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function getEsignPositioningUrl(flowId: number) {
  return request<{ url: string; customBizNum: string; expiresInHours: number }>(
    `/api/esign/flows/${flowId}/positioning-url`, { method: 'POST' },
  )
}

export function getEsignSignUrl(flowId: number) {
  return request<{ url: string; shortUrl: string }>(`/api/esign/tasks/${flowId}/sign-url`, { method: 'POST' })
}

export function getEsignBatchSignUrl(flowIds: number[] = []) {
  return request<{ count: number; batchSerialId: string; url: string; shortUrl: string }>('/api/esign/tasks/batch-sign-url', {
    method: 'POST', body: JSON.stringify({ flowIds }),
  })
}

export function fetchEsignBinding(userId: number) {
  return request<EsignBinding>(`/api/esign/admin/bindings/${userId}`)
}

export function saveEsignBinding(userId: number, payload: {
  legalName: string
  psnAccount: string
  psnAccountKind?: 'mobile' | 'email'
  status?: 'pending' | 'disabled'
}) {
  return request<EsignBinding>(`/api/esign/admin/bindings/${userId}`, {
    method: 'PUT', body: JSON.stringify(payload),
  })
}
