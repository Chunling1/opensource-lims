import { AppError } from '../src/services/common/errors'
import type { DemoEvent, RegistrationSample } from '../src/types/commissions/registration'
import type { EntryState } from '../src/types/testing/dataEntryDetail'
import type { EntryChangeRow, EntryIssueRow, EntryRecordsPage, FieldChange } from '../src/types/testing/dataEntryRecords'
import { demoActors } from '../src/services/storage/demoActors'
import { bulkCommissionFields } from '../src/types/commissions/commissionFields'
import { getSampleReportConfig } from './sampleReportSettings'

const labels: Record<string, string> = {
  ...Object.fromEntries(bulkCommissionFields.map(field => [field.key, field.label])),
  form: '试验信息', details: '样品信息', commissionInfo: '委托信息', name: '名称', customer: '委托单位', contact: '联系人', phone: '联系电话', notes: '备注', projects: '检测参数', category: '样品类别', quantity: '数量', unit: '单位', storage: '存放条件',
  conclusion: '结论', conclusionStatus: '结论状态', failedParameters: '不合格参数', tester1Id: '试验人1', tester2Id: '试验人2', reviewerId: '指定审核人', approverId: '指定批准人', testDates: '试验日期', calibrationEnabled: '填写校准日期', calibrationDate: '校准日期', reportDateEnabled: '填写报告日期', reportDate: '报告日期', environment: '试验环境', equipmentIds: '试验设备', showStandard: '体现标准名称', showEquipmentCode: '体现设备档案号', showEquipmentModel: '体现规格型号', showEquipmentManufacturer: '体现厂商名称', showEquipmentSerial: '体现出厂编号', layoutId: '报告版式',
  testPlan: '检测方案', testBasis: '检测依据', assessmentStandard: '评定标准', testingDepartment: '检测部门', testingLocation: '检测地点', nameplate: '铭牌', deliveryDate: '送样日期', appearance: '样品外观', appearanceNotes: '外观备注', taskRecipient: '任务接收人', inspectorPhone: '送样人电话', inspector: '送样人', trademark: '商标', trademarkImage: '商标图片', productCode: '产品编号', manufacturer: '生产单位', productionDate: '生产日期', specification: '规格型号', requestedTestDate: '要求试验日期', internalNotes: '内部备注', samplingOrganization: '抽样单位', samplingLocation: '抽样地点', sampler: '抽样人', samplingTime: '抽样日期', samplingQuantity: '抽样数量', samplingBase: '抽样基数', inspectedOrganization: '受检单位', taskSource: '任务来源', standardPrice: '标准费用', paymentMethod: '付款方式', paymentStatus: '付款状态', paidAmount: '已付金额', feeNotes: '费用备注', externalDueDate: '对外完成日期', internalDueDate: '内部完成日期', disposalMethod: '样品处置方式', reportDelivery: '报告领取方式', mailingAddress: '邮寄地址', reportCopies: '报告份数', reportForm: '报告形式', onsiteArrangement: '现场安排', appointmentDate: '预约日期', urgent: '加急', useAssessmentStandard: '使用评定标准', englishBookMarks: '英文书名号', assessmentEnglishBookMarks: '评定标准英文书名号', hasExternalDueDate: '填写对外完成日期', hasInternalDueDate: '填写内部完成日期', hasAppointment: '预约', reportSettings: '报告设置', formatId: '报告类型', titleId: '报告标题', languageId: '报告语言', subprojects: '子项目信息',
  contract: '合同编号', commissionDate: '委托日期', customerAddress: '委托单位地址', email: '邮箱', postalCode: '邮编', fax: '传真', handlingDepartmentId: '经办部门', requirements: '检测要求', source: '样品来源', settlement: '结算方式', discount: '折扣', taxRate: '税率', dueDate: '要求完成日期',
}
function text(value: unknown, key: string): string {
  if (value == null) return ''
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (['layoutId', 'formatId', 'titleId', 'languageId'].includes(key)) return getSampleReportConfig().options[key as 'layoutId'].find(option => option.id === value)?.label || String(value)
  if (['tester1Id', 'tester2Id', 'reviewerId', 'approverId'].includes(key)) { const person = demoActors.find(row => row.id === value); return person ? `${person.name}（${person.id}）` : String(value) }
  if (key === 'trademarkImage') return (value as { name?: string }).name || ''
  if (Array.isArray(value)) return value.map(item => key === 'testDates' ? `${item.from || ''} 至 ${item.to || ''}` : typeof item === 'object' ? JSON.stringify(item) : String(item)).join('；')
  return String(value)
}
// Store display values at the time of the write; never reconstruct old values from the current form.
export function fieldChanges(before: Record<string, unknown>, after: Record<string, unknown>, prefix = ''): FieldChange[] {
  const result: FieldChange[] = []
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    if (['testStartDate', 'testEndDate', 'dataUrl', 'testPlanId', 'testPlanCode', 'testBasisIds', 'assessmentStandardIds', 'testBasisSeparators', 'assessmentStandardSeparators', 'commissionId'].includes(key)) continue
    const old = before[key], value = after[key]
    if (JSON.stringify(old) === JSON.stringify(value)) continue
    const field = `${prefix}${labels[key] || key}`
    if ((value && typeof value === 'object' && !Array.isArray(value) || old && typeof old === 'object' && !Array.isArray(old)) && key !== 'trademarkImage') result.push(...fieldChanges((old || {}) as Record<string, unknown>, (value || {}) as Record<string, unknown>, `${field} / `))
    else result.push({ field, before: text(old, key), after: text(value, key) })
  }
  return result
}
const actionLabels: Record<string, string> = { save: '保存试验信息', 'change-report-layout': '更换报告版式' }
function changes(events: DemoEvent[], testing: boolean): EntryChangeRow[] {
  const relevant = events.filter(event => event.changes ? event.changes.length > 0 : testing ? ['save', 'change-report-layout'].includes(event.action) : /修改|更改/.test(event.action))
  return relevant.map((event, index) => ({ event, index })).reverse().flatMap(({ event, index }) => (event.changes || [{ field: event.action, before: '', after: '' }]).map((change, fieldIndex) => ({ ...change, id: `${index}-${fieldIndex}`, actor: event.actor, at: event.at, type: actionLabels[event.action] || event.action, sequence: index + 1 })))
}
function issues(sample: RegistrationSample): EntryIssueRow[] {
  const rows: EntryIssueRow[] = []
  const returns = [...(sample.outboundInfo?.returns || []), ...(sample.taskReturns || [])].sort((a, b) => a.recordedAt.localeCompare(b.recordedAt))
  for (const item of returns) rows.push({ id: `return-${rows.length}`, submitterId: item.recordedBy.id, submitter: item.recordedBy.name, description: [item.reason, item.details].filter(Boolean).join('；'), type: item.type === 'commission' ? '委托信息错误' : '任务分配错误', submittedAt: item.date || item.recordedAt, handlerId: '', handler: '', opinion: '', handledAt: '', sequence: rows.length + 1 })
  for (const issue of sample.reportCheckIssues || []) rows.push({ id: issue.id, submitterId: issue.submittedBy.id, submitter: issue.submittedBy.name, description: issue.reason, type: issue.problemType, submittedAt: issue.submittedAt, handlerId: issue.completedBy?.id || '', handler: issue.completedBy?.name || issue.handler, opinion: issue.opinion, handledAt: issue.completedAt || '', destination: issue.destination === 'commission' ? '退回委托更改' : '退回检测数据更改', sequence: rows.length + 1 })
  for (const problem of [sample.commissionChange, sample.dataChange]) {
    if (!problem || problem.reportIssueId && sample.reportCheckIssues?.some(issue => issue.id === problem.reportIssueId)) continue
    const related = rows.find(row => row.submittedAt === problem.submittedAt && row.description === problem.description)
    const row: EntryIssueRow = related || { id: problem === sample.dataChange ? 'data-change' : 'commission-change', submitterId: '', submitter: problem.submittedBy, description: problem.description, type: problem.type, submittedAt: problem.submittedAt, handlerId: '', handler: '', opinion: '', handledAt: '', sequence: rows.length + 1 }
    row.handlerId = problem.completedBy?.id || ''; row.handler = problem.completedBy?.name || ''; row.handledAt = problem.completedAt || ''
    if (!related) rows.push(row)
  }
  return rows.reverse()
}
export function entryRecords(sample: RegistrationSample, entry: EntryState, value: unknown): EntryRecordsPage {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
  const query = value as Record<string, unknown>, page = query.page ?? 1, pageSize = query.pageSize ?? 10
  if (!['commission', 'testing', 'issues'].includes(String(query.kind)) || !Number.isSafeInteger(page) || Number(page) < 1 || ![10, 20, 50].includes(Number(pageSize))) throw new AppError('BAD_REQUEST', '记录类型或分页参数有误。')
  const rows = query.kind === 'issues' ? issues(sample) : changes(query.kind === 'testing' ? entry.events : sample.events, query.kind === 'testing')
  const current = Math.min(Number(page), Math.max(1, Math.ceil(rows.length / Number(pageSize))))
  return { items: rows.slice((current - 1) * Number(pageSize), current * Number(pageSize)), total: rows.length, page: current, pageSize: Number(pageSize) }
}
