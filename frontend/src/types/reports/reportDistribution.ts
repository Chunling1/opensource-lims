import type { TableColumn } from '../common/table'
import type { ReportPrintRow } from './reportPrint'
import type { ReportForm } from './reportLifecycle'

export interface ReportDistributionDetail {
  id: string; version: number; releaseId: string; form: ReportForm
  contract: string; contractCustomer: string; commissionCode: string; customer: string; projectName: string
  receivedAmount: number | null; contractBalance: number | null; availableCredit: number | null
  fees: { id: string; testPlan: string; code: string; quantity: number; amount: number | null; paymentStatus: string }[]
  totalAmount: number | null; mailingAddress: string
}
export interface ReportDistributionDraft {
  recipient: string; method: string; date: string; notes: string; trackingNumber: string; mailingAddress: string
}

export const reportDistributionSearchFields = [
  { value: 'code', label: '样品编号' },
  { value: 'reportCode', label: '报告编号' },
  { value: 'commissionCode', label: '委托编号' },
  { value: 'recipient', label: '领取人' },
  { value: 'customer', label: '委托单位' },
  { value: 'contact', label: '委托人' },
  { value: 'engineeringName', label: '项目名称' },
] as const

export const reportDistributionStates = [
  '委托登记中', '委托登记完成',
  '任务分配中', '任务分配完成',
  '任务处理中', '任务处理完成',
  '检测数据录入中', '检测数据录入完成',
  '报告审核中', '报告审核完成',
  '报告批准中', '报告批准完成',
  '报告打印中', '报告打印完成',
  '委托更改中', '检测更改中', '报告更改中',
  '委托作废申请中', '委托已作废', '报告更改审批中',
  '任务已取消', '终止',
] as const
export const reportDistributionStatuses = ['未发放', '已发放'] as const
export const reportDistributionStatusLabels: Record<string, string> = { 未发放: '报告发放中', 已发放: '报告已发放' }
export const reportDistributionDateFields = [
  { value: 'printDate', label: '打印日期' },
  { value: 'approvalDate', label: '批准日期' },
  { value: 'distributionDate', label: '领取日期' },
  { value: 'commissionDate', label: '委托日期' },
] as const
export const reportCollectionMethods = ['自取', '邮寄', '其他'] as const
export function reportCollectionMethod(method: string) {
  if (!method) return ''
  if (method === '领取' || method === '自取') return '自取'
  return method === '邮寄' ? '邮寄' : '其他'
}
export const reportDistributionColumns: readonly TableColumn<keyof ReportPrintRow>[] = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'changeCount', label: '更改次数' },
  { key: 'commissionCode', label: '委托编号' },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'testPlan', label: '检测方案', truncate: 14, fullTitle: true },
  { key: 'form', label: '报告形式', default: true },
  { key: 'distributionStatus', label: '发放状态', default: true },
  { key: 'recipient', label: '领取人', default: true },
  { key: 'distributionDate', label: '领取日期', default: true },
  { key: 'deliveryMethod', label: '领取方式' },
  { key: 'trackingNumber', label: '快递单号' },
  { key: 'mailingAddress', label: '邮寄地址', truncate: 18, fullTitle: true },
  { key: 'approvalDate', label: '批准日期' },
  { key: 'printDate', label: '打印日期' },
  { key: 'paymentStatus', label: '收费状态' },
  { key: 'priceAdjustmentStatus', label: '价格调整状态' },
  { key: 'standardPrice', label: '标准价格费用', money: true },
  { key: 'discountPrice', label: '折扣价格费用', money: true },
  { key: 'actualPrice', label: '实际价格费用', money: true },
  { key: 'conclusion', label: '结论' },
  { key: 'commissionDate', label: '委托日期', sort: 'commissionDate' },
  { key: 'customer', label: '委托单位', truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人' },
  { key: 'engineeringName', label: '项目名称', truncate: 14, fullTitle: true },
]
