import type { TableColumn } from '../common/table'
import type { DataEntryRow } from '../testing/dataEntry'
import type { ReportPrintQuery } from './reportPrint'
import type { RegistrationPage } from '../commissions/registration'
import type { PlanSelectionState } from '../samples/inbound'
export { reportPrintSearchFields as reportQuerySearchFields } from './reportPrint'
export { reportDistributionStates as reportQueryStates } from './reportDistribution'
export const reportQueryDateFields = [
  { value: 'commissionDate', label: '委托日期' },
  { value: 'testStartDate', label: '试验开始日期' },
  { value: 'testEndDate', label: '试验结束日期' },
  { value: 'checkDate', label: '校核日期' },
  { value: 'auditDate', label: '审核日期' },
  { value: 'approvalDate', label: '批准日期' },
  { value: 'archiveDate', label: '归档日期' },
  { value: 'printDate', label: '打印日期' },
] as const
export type ReportQueryQuery = Pick<ReportPrintQuery, 'searchField' | 'contains' | 'status' | 'sampleType' | 'conclusion' | 'from' | 'to' | 'plans' | 'sort' | 'direction' | 'page' | 'pageSize' | 'ids'> & { dateField?: typeof reportQueryDateFields[number]['value'] }
export const reportQueryActions = [
  { id: 'preview', label: '报告预览', icon: 'ti ti-file-search' },
  { id: 'data', label: '查看数据', icon: 'ti ti-eye' },
  { id: 'attachments', label: '查看附件', icon: 'ti ti-paperclip' },
  { id: 'void', label: '作废', icon: 'ti ti-circle-x' },
] as const
export type ReportQueryAction = typeof reportQueryActions[number]['id']
export interface ReportQueryRow extends DataEntryRow {
  releaseId: string; form: string; signingStatus: string; canVoid: boolean
  erpProjectNumber: string; erpContractNumber: string; contractType: string; changeCount: number | null
  reportDeliveryStatus: string; reportArchiveStatus: string; paymentStatus: string; priceAdjustmentStatus: string
  recipient: string; collectionDate: string; pendingStatus: string
  inboundDate: string; inboundPerson: string; outboundDate: string; outboundPerson: string
  checkDate: string; checker: string; dataCompletedDate: string; auditDate: string; auditor: string; approvalDate: string; approver: string
  printDate: string; printPerson: string; printCount: number | null; distributionDate: string; distributionPerson: string
  archiveDate: string; archiver: string; failedParameters: string
  standardPrice: number | null; discountPrice: number | null; actualPrice: number | null
}
export interface ReportQueryPage extends RegistrationPage<ReportQueryRow> { planSelection: PlanSelectionState }
export const reportQueryColumns: readonly TableColumn<keyof ReportQueryRow>[] = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'erpProjectNumber', label: '外部ERP项目编号' },
  { key: 'erpContractNumber', label: '外部ERP合同编号' },
  { key: 'contractType', label: '合同类型' },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'changeCount', label: '更改次数' },
  { key: 'reportDeliveryStatus', label: '报告发放状态', default: true },
  { key: 'reportArchiveStatus', label: '报告归档状态' },
  { key: 'paymentStatus', label: '收费状态' },
  { key: 'priceAdjustmentStatus', label: '价格调整状态' },
  { key: 'recipient', label: '领取人' },
  { key: 'collectionDate', label: '领取日期' },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'pendingStatus', label: '待处理状态' },
  { key: 'projectName', label: '检测方案', truncate: 14, fullTitle: true },
  { key: 'assignedBy', label: '分配人' },
  { key: 'customer', label: '委托单位', truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人' },
  { key: 'commissionDate', label: '委托日期', sort: 'commissionDate' },
  { key: 'engineeringName', label: '项目名称', truncate: 14, fullTitle: true },
  { key: 'projectAddress', label: '工程地址', truncate: 18, fullTitle: true },
  { key: 'testStartDate', label: '试验开始日期' },
  { key: 'testEndDate', label: '试验结束日期' },
  { key: 'tester1', label: '试验人1' },
  { key: 'tester2', label: '试验人2' },
  { key: 'inboundDate', label: '入库日期' },
  { key: 'inboundPerson', label: '入库人' },
  { key: 'outboundDate', label: '出库日期' },
  { key: 'outboundPerson', label: '出库人' },
  { key: 'checkDate', label: '校核日期' },
  { key: 'checker', label: '校核人' },
  { key: 'dataCompletedDate', label: '检测数据完成日期' },
  { key: 'auditDate', label: '审核日期' },
  { key: 'auditor', label: '审核人' },
  { key: 'approvalDate', label: '批准日期' },
  { key: 'approver', label: '批准人' },
  { key: 'printDate', label: '打印日期' },
  { key: 'printPerson', label: '打印人' },
  { key: 'printCount', label: '打印次数' },
  { key: 'distributionDate', label: '发放日期' },
  { key: 'distributionPerson', label: '发放人' },
  { key: 'archiveDate', label: '归档日期' },
  { key: 'archiver', label: '归档人' },
  { key: 'conclusion', label: '检测结果', truncate: 18, fullTitle: true },
  { key: 'failedParameters', label: '不合格参数', truncate: 14, fullTitle: true },
  { key: 'standardPrice', label: '标准价格费用', money: true },
  { key: 'discountPrice', label: '折扣价格费用', money: true },
  { key: 'actualPrice', label: '实际价格费用', money: true },
  { key: 'attachmentCount', label: '附件' },
]
