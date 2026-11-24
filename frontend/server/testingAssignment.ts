import { assignmentStatus } from '../src/types/commissions/workflow'
import { normalizeConclusion } from '../src/types/testing/dataEntryDetail'
import { AppError, problem } from '../src/services/common/errors'
import { demoActors } from '../src/services/storage/demoActors'
import type { Actor } from '../src/types/lims'
import { stockDate, stockField } from './stockReceipt'
import { sampleTypes, type RegistrationSample } from '../src/types/commissions/registration'
import { assignmentStates, assignmentConclusions, assignmentSearchFields, assignmentDateFields, type AssignmentQuery, type AssignmentRow } from '../src/types/testing/assignment'
import { parseStorageQuery } from './sampleInbound'
import { getSampleReportConfig } from './sampleReportSettings'
import { taskQueryStates } from '../src/types/testing/taskQuery'
import { sampleCopyStates } from '../src/types/testing/sampleCopy'

const printableStates: readonly string[] = [...taskQueryStates.slice(taskQueryStates.indexOf('任务分配中')), ...sampleCopyStates.slice(sampleCopyStates.indexOf('检测数据录入完成'), sampleCopyStates.indexOf('报告打印完成') + 1)]

export function assignmentPending(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return assignmentStatus(sample.dataStatus) === '任务分配中' && !['voided', 'void_pending'].includes(sample.status)
}
export function assignmentReversible(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return sample.dataStatus === '任务分配完成' && !['voided', 'void_pending'].includes(sample.status)
}
export function assignmentPrintable(sample: Pick<RegistrationSample, 'status' | 'dataStatus'>) {
  return !['voided', 'void_pending'].includes(sample.status) && printableStates.includes(sample.dataStatus)
}
export function parseAssignmentSubmission(input: unknown, people: readonly Pick<Actor, 'id' | 'name'>[] = demoActors) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '请填写分配信息。')
  const data = input as Record<string, unknown>
  const account = stockField(data, 'account', '分配人工号'), name = stockField(data, 'name', '分配人姓名')
  const assigner = people.find(person => person.id === account)
  if (!assigner || assigner.name !== name) throw new AppError('VALIDATION', '分配人工号与姓名不匹配，请核对后重新提交。', { fieldErrors: { account: '请核对分配人工号。', name: '工号与姓名不匹配，请核对后重新提交。' } })
  function person(key: string, label: string, required = true) {
    const value = stockField({ ...data, [key]: data[key] ?? '' }, key, label, 100, required)
    if (!value) return undefined
    const byAccount = people.find(person => person.id === value)
    if (byAccount) return byAccount
    const matches = people.filter(person => person.name === value)
    if (!matches.length) throw problem('VALIDATION', `${label}不存在，请核对姓名或账号。`, key)
    if (matches.length > 1) throw problem('VALIDATION', `${label}存在同名人员，请改填账号。`, key)
    return matches[0]!
  }
  const dataEntry = person('dataEntryPerson', '数据录入人')!, tester1 = person('tester1', '检测人1')!, tester2 = person('tester2', '检测人2', false)
  if (tester2?.id === tester1.id) throw problem('VALIDATION', '检测人2不能与检测人1重复。', 'tester2')
  return { assignedBy: assigner.name, assignedById: assigner.id, dataEntryPerson: dataEntry.name, dataEntryPersonId: dataEntry.id, tester1: tester1.name, tester1Id: tester1.id,
    tester2: tester2?.name || '', tester2Id: tester2?.id || '', assignedDate: stockDate(data, '分配日期') }
}

export function parseAssignmentQuery(input: Record<string, unknown>, states: readonly string[] = assignmentStates): AssignmentQuery {
  const base = parseStorageQuery(input, states, '查询日期')
  const query: AssignmentQuery = { plans: base.plans, status: base.status, from: base.from, to: base.to, page: base.page, pageSize: base.pageSize, sort: base.sort, direction: base.direction, ids: base.ids }
  const choices = { searchField: assignmentSearchFields.map(field => field.value), dateField: assignmentDateFields.map(field => field.value), sampleType: sampleTypes, conclusion: assignmentConclusions }
  for (const key of ['searchField', 'dateField', 'sampleType', 'conclusion', 'contains'] as const) {
    const value = key === 'conclusion' && typeof input[key] === 'string' ? normalizeConclusion(input[key]) : input[key]
    if (value === undefined || value === '') continue
    if (typeof value !== 'string' || value.length > 200 || key !== 'contains' && !(choices[key] as readonly string[]).includes(value)) throw new AppError('BAD_REQUEST', '任务查询条件格式有误。')
    Object.assign(query, { [key]: value.trim() })
  }
  return query
}
export function assignmentRows(samples: (RegistrationSample & { commissionCode: string; commissionName: string })[], query: AssignmentQuery, states: readonly string[] = assignmentStates, includeInactive = false): AssignmentRow[] {
  if (states === assignmentStates) samples = samples.map(sample => ({ ...sample, dataStatus: assignmentStatus(sample.dataStatus) }))
  const titles = getSampleReportConfig().options.titleId
  const rows = samples.filter(sample => (includeInactive || !['voided', 'void_pending'].includes(sample.status)) && states.includes(sample.dataStatus)).map(sample => {
    const info = sample.assignmentInfo, details = sample.details
    const reportTitle = titles.find(option => option.id === details?.reportSettings.titleId)?.label || ''
    return { id: sample.id, version: sample.version, canAssign: false, canUndoAssign: false, canPrintTask: assignmentPrintable(sample), code: sample.code, commissionCode: sample.commissionCode, reportCode: sample.reportCode, sampleType: sample.sampleType, name: sample.name,
      parameters: sample.projects.join('；'), dataStatus: sample.dataStatus, projectName: details?.testPlan || '', attachmentCount: sample.attachments.length,
      contact: sample.commissionInfo.contact, phone: sample.commissionInfo.phone, commissionDate: sample.commissionInfo.commissionDate || '',
      appointmentDate: details?.hasAppointment ? details.appointmentDate : '', customer: sample.customer, engineeringName: sample.commissionName,
      projectAddress: sample.commissionInfo.projectAddress || '', assignedBy: info?.assignedBy || '', dataEntryPerson: info?.dataEntryPerson || '',
      tester1: info?.tester1 || '', tester2: info?.tester2 || '', requestedTestDate: details?.requestedTestDate || '', reportTitle,
      conclusion: normalizeConclusion(info?.conclusion || '') || ({ qualified: '合格', unqualified: '不合格' } as Record<string, string>)[sample.workflow?.conclusion || ''] || '' }
  }).filter(row => {
    const date = row[query.dateField || 'commissionDate']
    return (!query.status || row.dataStatus === query.status) && (!query.sampleType || row.sampleType === query.sampleType)
      && (!query.conclusion || row.conclusion === query.conclusion) && (!query.ids || query.ids.includes(row.id))
      && (!query.contains || row[query.searchField || 'code'].toLocaleLowerCase().includes(query.contains.toLocaleLowerCase()))
      && (!query.from || !!date && date >= query.from) && (!query.to || !!date && date <= query.to)
  })
  const key = query.sort || 'code', direction = query.direction === 'desc' ? -1 : 1
  return rows.sort((a, b) => (a[key].localeCompare(b[key], 'zh-CN', { numeric: true }) || a.code.localeCompare(b.code, 'zh-CN', { numeric: true })) * direction)
}
