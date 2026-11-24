import { authedFetch, request } from './http'
export type CorrectionType = 'internal' | 'external'
export interface CorrectionAttachment { id: number; name: string; type: string; source: string; status: string; contentType: string }
export interface CorrectionRequest {
  id: number; mainReportNo: string; correctionReportNo: string; correctionType: CorrectionType | 'legacy'
  reason: string; returnMode: string; status: string; applicantName: string; createdAt: string
  applicationAttachment: CorrectionAttachment | null; receiptAttachment: CorrectionAttachment | null
  approverName: string; approverNote: string; approverAt: string
  directorName: string; directorNote: string; directorAt: string; leaderName: string; leaderNote: string; leaderAt: string
  canApprove: boolean; canApproveDirector: boolean; canApproveLeader: boolean
  hasHistory?: boolean; blocksNewRequest?: boolean
}
export interface CorrectionHistory {
  report: { reportNo: string; client: string; status: string; version: string }
  versions: { id: number; versionLabel: string; hasPdf: boolean; createdAt: string }[]
  flows: { id: number; status: string; hasSignedFile: boolean; documentVersionId: number }[]
}
export function fetchCorrectionHistory(id: number) {
  return request<CorrectionHistory>(`/api/reports/correction-requests/${id}/history`)
}
export async function downloadCorrectionHistory(id: number, kind: 'version' | 'signed', fileId: number) {
  const response = await authedFetch(`/api/reports/correction-requests/${id}/history/${kind}/${fileId}/pdf`)
  if (!response.ok || !response.headers.get('Content-Type')?.includes('application/pdf')) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.message || '历史文件下载失败')
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a'); link.href = url; link.download = `更正前历史-${id}-${kind}-${fileId}.pdf`; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export const correctionStatus: Record<string, string> = { pending_approval: '待审批', pending_director: '待部门主任审批', pending_leader: '待院领导审批', approved: '审批通过', rejected: '已驳回' }
export const correctionReturnModes: Record<string, string> = { data_only: '检测数据更改', entrust_only: '委托更改', entrust_and_data: '委托和检测数据更改' }
export function fetchCorrections() { return request<{ rows: CorrectionRequest[] }>('/api/reports/correction-requests') }
export function submitCorrection(reportNo: string, type: CorrectionType, reason: string, returnMode: string, internalFile: File, receiptFile?: File) {
  const body = new FormData()
  body.append('correctionType', type); body.append('reason', reason.trim()); body.append('returnMode', returnMode)
  body.append('internalFile', internalFile)
  if (type === 'external' && receiptFile) body.append('receiptFile', receiptFile)
  return request<CorrectionRequest>(`/api/reports/${encodeURIComponent(reportNo)}/correction-requests`, { method: 'POST', body })
}
export function decideCorrection(id: number, decision: 'approve' | 'reject', note: string) {
  return request<CorrectionRequest>(`/api/reports/correction-requests/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, note: note.trim() }) })
}
