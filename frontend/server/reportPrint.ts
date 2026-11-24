import { reportArchiveStatuses, reportArchiveDateFields } from '../src/types/reports/reportArchive'
import { reportDistributionSearchFields, reportDistributionDateFields, reportCollectionMethods, reportDistributionStates, reportDistributionStatuses } from '../src/types/reports/reportDistribution'
import { AppError } from '../src/services/common/errors'
import { reportPrintDateFields, reportPrintSearchFields, reportPrintStates, reportPrintStatuses, type ReportPrintQuery } from '../src/types/reports/reportPrint'
import { parseDataEntryQuery } from './testingDataEntry'
import { reportSigningStates, reportSigningStatuses } from '../src/types/reports/reportSigning'

export function parseReportPrintQuery(input: Record<string, unknown>, mode: 'print' | 'signing' | 'distribution' | 'archive' = 'print'): ReportPrintQuery {
  for (const [key, choices] of [
    ['searchField', (mode === 'distribution' ? reportDistributionSearchFields : reportPrintSearchFields).map(field => field.value)],
    ['dateField', (mode === 'archive' ? reportArchiveDateFields : mode === 'distribution' ? reportDistributionDateFields : reportPrintDateFields).map(field => field.value)],
    [mode === 'archive' ? 'archiveStatus' : mode === 'distribution' ? 'distributionStatus' : mode === 'print' ? 'printStatus' : 'signingStatus', mode === 'archive' ? reportArchiveStatuses : mode === 'distribution' ? reportDistributionStatuses : mode === 'print' ? reportPrintStatuses : reportSigningStatuses],
    ['collectionMethod', mode === 'distribution' ? reportCollectionMethods : []],
    ['form', mode === 'distribution' ? ['纸质', '电子'] : []],
  ] as const) {
    if (input[key] !== undefined && input[key] !== '' && !(choices as readonly unknown[]).includes(input[key])) throw new AppError('BAD_REQUEST', `报告${mode === 'archive' ? '归档' : mode === 'distribution' ? '发放' : mode === 'print' ? '打印' : '签章'}查询条件有误。`)
  }
  const reportDate = input.dateField === 'approvalDate' || input.dateField === 'printDate' || input.dateField === 'distributionDate' || input.dateField === 'archiveDate'
  const query = parseDataEntryQuery({ ...input, searchField: input.searchField === 'recipient' ? undefined : input.searchField, dateField: reportDate ? undefined : input.dateField }, mode === 'archive' ? [] : mode === 'distribution' ? reportDistributionStates : mode === 'print' ? reportPrintStates : reportSigningStates)
  return { ...query, searchField: input.searchField === 'recipient' ? 'recipient' : query.searchField, dateField: (reportDate ? input.dateField : query.dateField) as ReportPrintQuery['dateField'], form: input.form as ReportPrintQuery['form'], collectionMethod: input.collectionMethod as ReportPrintQuery['collectionMethod'], ...(mode === 'archive' ? { archiveStatus: input.archiveStatus as ReportPrintQuery['archiveStatus'] } : mode === 'distribution' ? { distributionStatus: input.distributionStatus as ReportPrintQuery['distributionStatus'] } : mode === 'print' ? { printStatus: input.printStatus as ReportPrintQuery['printStatus'] } : { signingStatus: input.signingStatus as ReportPrintQuery['signingStatus'] }) }
}
