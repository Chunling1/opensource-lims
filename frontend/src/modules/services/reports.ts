import { canCorrect, rememberCorrection } from './businessCorrection'
import { request } from './http'
import type { ReportDetailData } from './auth'

export type ReportDetailView =
  | 'query'
  | 'contract_review'
  | 'data_entry'
  | 'data_change'
  | 'review'
  | 'interim_report'
  | 'approval'
  | 'print'
  | 'release'
  | 'archive'
  | 'change_request'
  | 'entrust_query'
  | 'testing_task_query'
  | 'sample_flow_query'
  | 'entrust_change'
  | 'sample_change'
  | 'sample_register'
  | 'sample_inbound'
  | 'sample_outbound'
  | 'sample_disposal'

const USE_BACKEND = import.meta.env.VITE_USE_BACKEND === '1'

// Full detail is always tied to the page that opened it.  The backend checks
// the same context again against feature, data, state and project-step scope.
export async function fetchReportDetail(
  reportNo: string,
  view: ReportDetailView,
  projection?: 'sample_form' | 'sample_form_text',
): Promise<ReportDetailData | null> {
  if (!USE_BACKEND) return null
  if (canCorrect()) { await rememberCorrection('reports', reportNo); if (['data_entry','data_change','sample_register','sample_change','entrust_change','entrust_query'].includes(view)) view = 'query' }
  const encodedReportNo = encodeURIComponent(reportNo)
  const encodedView = encodeURIComponent(view)
  return request<ReportDetailData>(`/api/reports/${encodedReportNo}?view=${encodedView}${projection ? '&projection=' + projection : ''}`)
}

export function fetchSampleFormImage(reportNo: string, view: ReportDetailView, revision: string) {
  if (canCorrect() && ['data_entry','data_change','sample_register','sample_change','entrust_change','entrust_query'].includes(view)) view = 'query'
  return request<{ reportNo: string; trademarkImage: string }>(`/api/reports/${encodeURIComponent(reportNo)}?view=${encodeURIComponent(view)}&projection=sample_form_image&image_revision=${encodeURIComponent(revision)}`)
}

export function fetchReportRecords(reportNo: string, view: ReportDetailView, query: import('../../types/testing/dataEntryRecords').EntryRecordsQuery, signal?: AbortSignal) {
  const params = new URLSearchParams({view, kind: query.kind, page: String(query.page || 1), pageSize: String(query.pageSize || 10)})
  return request<import('../../types/testing/dataEntryRecords').EntryRecordsPage>(`/api/reports/${encodeURIComponent(reportNo)}/records?${params}`, {signal})
}
