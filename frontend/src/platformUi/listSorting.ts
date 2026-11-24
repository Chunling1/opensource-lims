import type { TableColumn } from '../types/common/table'

// Only the identifiers and dated facts requested for business lists. Text,
// statuses, durations and unsourced placeholder dates remain non-sortable.
export const businessSortKeys = new Set([
  'code', 'sampleNo', 'reportCode', 'reportNo', 'commissionCode', 'entrustNo',
  'commissionDate', 'entrustDate', 'sampleRegisteredAt', 'sendDate', 'samplingTime',
  'productionDate', 'inboundDate', 'outboundDate', 'collectionDate',
  'disposalDate', 'sampleInboundDate', 'sampleOutboundDate', 'samplePickupDate',
  'requestedTestDate', 'testStartDate', 'testEndDate', 'checkDate', 'auditDate',
  'approvalDate', 'printDate', 'archiveDate', 'distributionDate', 'voidedAt',
  'problemSubmittedAt', 'contractReviewedAt', 'dataSavedAt', 'dataCompletedAt',
  'reportCheckedAt', 'reportReviewedAt', 'reportApprovedAt', 'reportIssuedAt',
  'reportArchivedAt', 'reportReleasedAt',
])

export function sortableBusinessColumns<T extends TableColumn>(columns: readonly T[]): T[] {
  return columns.map(column => businessSortKeys.has(column.key)
    ? { ...column, sort: column.key } : { ...column })
}

export function compareBusinessRows(a: Record<string, any>, b: Record<string, any>, query: Record<string, any>) {
  if (!query.sort) return 0
  return String(a[query.sort] ?? '').localeCompare(String(b[query.sort] ?? ''), 'zh-CN', { numeric: true })
    * (query.direction === 'desc' ? -1 : 1)
}
