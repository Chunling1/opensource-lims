import { request } from './http'
import type { SampleRow, EntrustSnapshot } from './pipeline'
export type SampleCopyRow = SampleRow & { archiveState?: string }

export interface SampleCopySource {
  department?: string
  entrustSnapshot?: EntrustSnapshot
  requestedSeal?: string
  reportNo: string
  sampleNo: string
  rawSample?: Record<string, unknown>
  summary: { title: string; fields: [string, string][] }[]
}

export function fetchSampleCopyPage(keyword = '', page = 1) {
  return request<{ rows: SampleCopyRow[]; total: number }>('/api/samples/copy-sources/query', {
    method: 'POST', body: JSON.stringify({ keyword, page, pageSize: 50 }),
  })
}

export function fetchSampleCopySource(reportNo: string) {
  return request<SampleCopySource>(`/api/samples/copy-sources/${encodeURIComponent(reportNo)}`)
}
