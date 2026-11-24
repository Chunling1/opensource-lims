import { request, authedFetch } from './http'
import type { EsignBinding } from './esign'
export interface ReportArtifact { preview?: { notices?: string[] }; canDownload?: boolean; canPreview?: boolean; kind: 'signed' | 'controlled' | 'preview'; versionId: number | null; flowId: number | null; sha256?: string; label: string }
const path = (no: string, view: string, original = false) => `/api/report-assurance/reports/${encodeURIComponent(no)}/artifact?view=${encodeURIComponent(view)}${original ? '&original=1' : ''}`
export const fetchReportArtifact = (no: string, view: string, original = false) => request<ReportArtifact>(path(no, view, original))
export async function artifactObjectUrl(no: string, view: string, download = false, original = false) {
  const endpoint = path(no, view, original) + `&file=1&download=${download ? '1' : '0'}`
  const deadline = Date.now() + 300000
  const requested = new Set<string>()
  while (true) {
    const response = await authedFetch(endpoint)
    if (response.ok && response.headers.get('content-type')?.includes('application/pdf')) {
      return URL.createObjectURL(await response.blob())
    }
    const body = await response.json().catch(() => null)
    if (response.status !== 202) throw new Error(body?.message || '报告文件不可用，请重试')
    const state = body?.data
    const revision = String(state?.sourceHash || '')
    if (state?.status === 'failed' && requested.has(revision)) throw new Error(state.message || '报告生成失败')
    if (['missing', 'stale', 'failed'].includes(state?.status) && !requested.has(revision)) {
      requested.add(revision)
      await request(endpoint, { method: 'POST', body: JSON.stringify({ retry: state.status === 'failed' }) })
    }
    if (Date.now() >= deadline) throw new Error('预览仍在后台生成，请稍后重新打开')
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
}
export interface SigningHistory { id: number; versionId: number; status: string; hasSignedFile: boolean; error: string; completedAt: string; signers: { role: string; name: string; status: string; signedAt: string }[] }
export const fetchSigningHistory = (no: string, view: string) => request<{ rows: SigningHistory[] }>(`/api/report-assurance/reports/${encodeURIComponent(no)}/signing-history?view=${encodeURIComponent(view)}`)
export async function signingHistoryObjectUrl(no: string, view: string, flowId: number, download = false) {
  const response = await authedFetch(`/api/report-assurance/reports/${encodeURIComponent(no)}/signing-history/${flowId}/file?view=${encodeURIComponent(view)}&download=${download ? '1' : '0'}`)
  if (!response.ok || !response.headers.get('content-type')?.includes('application/pdf')) throw new Error('历史签署原件不可用或无权限，不生成替代文件')
  return URL.createObjectURL(await response.blob())
}
export const fetchBindingRoster = (keyword: string, status: string, page: number) => request<{ rows: (EsignBinding & { enabled: boolean })[]; total: number }>(`/api/report-assurance/bindings?keyword=${encodeURIComponent(keyword)}&status=${encodeURIComponent(status)}&page=${page}`)
export const maintainBinding = (id: number, action: 'sync' | 'rebind') => request(`/api/report-assurance/bindings/${id}/${action}`, { method: 'POST', body: JSON.stringify({ confirmed: true }) })
export const selectedBatchSignUrl = (flowIds: number[]) => request<{ count: number; flowIds: number[]; url: string; shortUrl: string }>('/api/report-assurance/batch-sign-url', { method: 'POST', body: JSON.stringify({ flowIds }) })
export const maintainPublication = (no: string, view: string, action: string, allowDownload = false) => request<{ url: string | null }>(`/api/report-publication/reports/${encodeURIComponent(no)}?view=${encodeURIComponent(view)}`, { method: 'POST', body: JSON.stringify({ action, confirmed: true, allowDownload }) })

export const prepareReportQuery = (no: string) => request<{ prepared: boolean }>(`/api/reports/${encodeURIComponent(no)}/prepare-query`, { method: 'POST' }, 30_000)
export const fetchPublication = (no: string, view: string) => request<{ url: string | null; publication: { allowDownload: boolean } | null }>(`/api/report-publication/reports/${encodeURIComponent(no)}?view=${encodeURIComponent(view)}`)

export const fetchSignedReportArtifact = (no: string, view: string) => request<ReportArtifact>(path(no, view) + '&signed=1')
export async function signedReportObjectUrl(no: string, view: string) {
  const response = await authedFetch(path(no, view) + '&signed=1&file=1&download=1')
  if (!response.ok || !response.headers.get('content-type')?.includes('application/pdf')) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.message || '签字盖章版不可用，请刷新后重试')
  }
  return URL.createObjectURL(await response.blob())
}
