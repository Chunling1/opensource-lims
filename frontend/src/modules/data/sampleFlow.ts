import type { SampleRow } from '@/services/pipeline'

export function sampleFlowRow(row: SampleRow) {
  return { ...row, status: row.voided ? '已作废' : row.sampleStatus,
    tag: row.voided ? '已作废' : row.archiveState === '归档完成' ? '已归档' : row.sampleStatus === '已出库' ? '出库' : '正常',
    date: row.entrustDate || '' }
}
