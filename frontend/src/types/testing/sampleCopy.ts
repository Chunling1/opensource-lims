import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { PlanSelectionState } from '../samples/inbound'
import type { DataEntryQuery, DataEntryRow } from './dataEntry'
export const sampleCopyDateFields = [
  { value: 'commissionDate', label: '委托日期' },
  { value: 'testStartDate', label: '试验开始日期' }, { value: 'testEndDate', label: '试验结束日期' },
  { value: 'checkDate', label: '校核日期' }, { value: 'auditDate', label: '审核日期' },
  { value: 'approvalDate', label: '批准日期' }, { value: 'issueDate', label: '签发日期' },
  { value: 'archiveDate', label: '归档日期' },
] as const

export const sampleCopyTypes = ['分项/阶段性报告样品', '英文报告样品', '补充报告'] as const
export const sampleCopySearchFields = [
  { value: 'code', label: '样品编号' }, { value: 'reportCode', label: '报告编号' },
  { value: 'commissionCode', label: '委托编号' }, { value: 'customer', label: '委托单位' },
  { value: 'engineeringName', label: '项目名称' }, { value: 'reportTitle', label: '报告标题' },
] as const
export const sampleCopyStates = [
  '委托登记中', '委托登记完成', '委托复核中', '委托复核完成',
  '样品入库中', '样品入库完成', '任务分配中', '任务分配完成', '样品出库中', '样品出库完成',
  '样品待领取', '样品已领取', '任务处理中', '任务处理完成',
  '检测数据录入中', '检测数据录入完成', '检测数据校核中', '检测数据校核完成',
  '报告校核中', '报告校核完成', '报告审核中', '报告审核完成', '报告批准中', '报告批准完成',
  '报告打印中', '报告打印完成', '委托更改中', '检测更改中', '报告更改中',
  '委托作废申请中', '委托已作废', '报告更改审批中', '任务已取消', '终止',
] as const

export const sampleCopyTargetStates = ['委托登记中', '委托登记完成', '检测数据录入中', '检测数据录入完成', '报告审核完成', '报告批准完成'] as const
export function availableSampleCopyStates(sourceStatus: string) {
  // Change/cancellation states are branches, not progress beyond report printing.
  const workflow = sampleCopyStates.slice(0, sampleCopyStates.indexOf('报告打印完成') + 1)
  const progress = Math.max(0, workflow.findIndex(state => state === sourceStatus))
  return sampleCopyTargetStates.filter(state => workflow.indexOf(state) <= progress)
}
export function sampleCopyNextState(status: string) {
  return sampleCopyTargetStates.some(value => value === status) ? sampleCopyStates[sampleCopyStates.findIndex(value => value === status) + 1]! : ''
}
export function sampleCopyReportSuffix(type: typeof sampleCopyTypes[number], suffix: string) {
  return type === '英文报告样品' ? '(E)' : type === '补充报告' ? 'BC' : suffix.trim()
}
export interface SampleCopyInput {
  requestId: string; version: number; sampleType: typeof sampleCopyTypes[number]
  dataStatus: string; testingDepartment: string; reportSuffix: string
}

export interface SampleCopyQuery extends Omit<DataEntryQuery, 'searchField' | 'dateField'> {
  searchField?: typeof sampleCopySearchFields[number]['value']
  dateField?: typeof sampleCopyDateFields[number]['value']
}
export interface SampleCopyRow extends DataEntryRow {
  testingDepartment: string
  canCopy: boolean; changeCount: number | null; reportDeliveryStatus: string; reportArchiveStatus: string; paymentStatus: string; priceAdjustmentStatus: string
  collectionPerson: string; collectionDate: string; inboundDate: string; inboundPerson: string; outboundDate: string; outboundPerson: string
  checkDate: string; checker: string; auditDate: string; auditor: string; approvalDate: string; approver: string
  issueDate: string; printDate: string; printPerson: string; distributionDate: string; distributionPerson: string
  archiveDate: string; archiver: string; failedParameters: string
  standardPrice: number | null; discountPrice: number | null; actualPrice: number | null
}
export interface SampleCopyPage extends RegistrationPage<SampleCopyRow> { planSelection: PlanSelectionState }
export const sampleCopyColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'changeCount', label: '更改次数', default: false },
  { key: 'reportDeliveryStatus', label: '报告发放状态', default: false },
  { key: 'reportArchiveStatus', label: '报告归档状态', default: false },
  { key: 'paymentStatus', label: '收费状态', default: false },
  { key: 'priceAdjustmentStatus', label: '价格调整状态', default: false },
  { key: 'collectionPerson', label: '领取人', default: false },
  { key: 'collectionDate', label: '领取日期', default: false },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '数据状态', default: true },
  { key: 'projectName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'assignedBy', label: '分配人', default: false },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人', default: false },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'projectAddress', label: '工程地址', default: false, truncate: 18, fullTitle: true },
  { key: 'testStartDate', label: '试验开始日期', default: false },
  { key: 'testEndDate', label: '试验结束日期', default: false },
  { key: 'tester1', label: '试验人1', default: false },
  { key: 'tester2', label: '试验人2', default: false },
  { key: 'inboundDate', label: '入库日期', default: false },
  { key: 'inboundPerson', label: '入库人', default: false },
  { key: 'outboundDate', label: '出库日期', default: false },
  { key: 'outboundPerson', label: '出入库人', default: false },
  { key: 'checkDate', label: '校核日期', default: false },
  { key: 'checker', label: '校核人', default: false },
  { key: 'auditDate', label: '审核日期', default: false },
  { key: 'auditor', label: '审核人', default: false },
  { key: 'approvalDate', label: '批准日期', default: false },
  { key: 'approver', label: '批准人', default: false },
  { key: 'printDate', label: '打印日期', default: false },
  { key: 'printPerson', label: '打印人', default: false },
  { key: 'distributionDate', label: '发放日期', default: false },
  { key: 'distributionPerson', label: '发放人', default: false },
  { key: 'archiveDate', label: '归档日期', default: false },
  { key: 'archiver', label: '归档人', default: false },
  { key: 'conclusion', label: '结论', default: false, truncate: 18, fullTitle: true },
  { key: 'failedParameters', label: '不合格参数', default: false, truncate: 14, fullTitle: true },
  { key: 'standardPrice', label: '标准价格费用', default: false, money: true },
  { key: 'discountPrice', label: '折扣价格费用', default: false, money: true },
  { key: 'actualPrice', label: '实际价格费用', default: false, money: true },
  { key: 'attachmentCount', label: '附件', default: false },
] as const satisfies readonly TableColumn<keyof SampleCopyRow>[]
