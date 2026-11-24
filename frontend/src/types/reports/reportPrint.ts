import type { TableColumn } from '../common/table'
import type { DataEntryRow, DataEntryQuery } from '../testing/dataEntry'
import type { ReportLifecycleRow, SigningStatus } from './reportLifecycle'
import type { PlanSelectionState } from '../samples/inbound'
import type { RegistrationPage } from '../commissions/registration'
export { reportCheckSearchFields as reportPrintSearchFields } from './reportCheck'

export const reportPrintStates = ['报告打印中', '报告打印完成'] as const
export const reportPrintStatuses = ['未打印', '已打印'] as const
export const reportPrintDateFields = [
  { value: 'approvalDate', label: '批准日期' },
  { value: 'testStartDate', label: '试验开始日期' },
  { value: 'testEndDate', label: '试验结束日期' },
  { value: 'commissionDate', label: '委托日期' },
] as const
export interface ReportPrintQuery extends Omit<DataEntryQuery, 'dateField' | 'searchField'> {
  searchField?: DataEntryQuery['searchField'] | 'recipient'
  dateField?: typeof reportPrintDateFields[number]['value'] | 'printDate' | 'distributionDate' | 'archiveDate'
  printStatus?: '' | '未打印' | '已打印'
  signingStatus?: '' | SigningStatus
  distributionStatus?: '' | '未发放' | '已发放'
  archiveStatus?: '' | '待归档' | '已归档'
  form?: '' | '纸质' | '电子'
  collectionMethod?: '' | '自取' | '邮寄' | '其他'
}
export interface ReportPrintRow extends DataEntryRow, ReportLifecycleRow {
  reportCopies: string; changeCount: number | null; printPerson: string; printDate: string; approvalDate: string
  paymentStatus: string; priceAdjustmentStatus: string; standardPrice: number | null; discountPrice: number | null
  signatureStatus?: string; sealStatus?: string; signingDate?: string
  deliveryMethod?: string; trackingNumber?: string; mailingAddress?: string
  archivePerson?: string; archiveDate?: string
}
export interface ReportPrintPage extends RegistrationPage<ReportPrintRow> { planSelection: PlanSelectionState }
export const reportPrintColumns: readonly TableColumn<keyof ReportPrintRow>[] = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'reportCopies', label: '报告交付份数', default: false },
  { key: 'changeCount', label: '更改次数', default: false },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'archiveStatus', label: '报告归档状态', default: false },
  { key: 'testPlan', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'form', label: '报告形式', default: false },
  { key: 'printPerson', label: '打印人', default: true },
  { key: 'printDate', label: '打印日期', default: true },
  { key: 'attachmentCount', label: '附件', default: false },
  { key: 'approvalDate', label: '批准日期', default: false },
  { key: 'testStartDate', label: '试验开始日期', default: false },
  { key: 'testEndDate', label: '试验结束日期', default: false },
  { key: 'conclusion', label: '结论', default: false },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人', default: false },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'paymentStatus', label: '收费状态', default: false },
  { key: 'standardPrice', label: '标准价格费用', default: false, money: true },
  { key: 'discountPrice', label: '折扣价格费用', default: false, money: true },
  { key: 'actualPrice', label: '实际价格费用', default: false, money: true },
]
