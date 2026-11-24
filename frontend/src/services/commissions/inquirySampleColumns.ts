import type { RegistrationSampleRow } from '../../types/commissions/registration'
import type { TableColumn } from '../../types/common/table'
import { tableCellText } from '../common/table'

// Inquiry has its own column order; additional columns stay hidden by default.
export const inquirySampleColumns = [
  { key: 'code', label: '样品编号', default: true, required: true, sort: 'code' },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'erpContractNumber', label: '外部ERP合同编号', default: false },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'commissionDate', label: '委托日期', default: false },
  { key: 'name', label: '样品/工程名称', default: true, wrap: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 20, fullTitle: true },
  { key: 'dataStatus', label: '数据状态', default: true },
  { key: 'testPlan', label: '检测方案', default: false, wrap: true },
  { key: 'customer', label: '委托单位', default: true, wrap: true },
  { key: 'projectName', label: '项目名称', default: false, wrap: true },
  { key: 'manufacturer', label: '生产单位', default: false, truncate: 20, fullTitle: true },
  { key: 'quantity', label: '样品数量', default: false },
  { key: 'samplingQuantity', label: '抽样数量', default: false },
  { key: 'specification', label: '规格型号', default: false, truncate: 20, fullTitle: true },
  { key: 'trademark', label: '商标', default: false, truncate: 20, fullTitle: true },
  { key: 'category', label: '检验类别', default: false },
  { key: 'inspector', label: '指定主检人', default: false },
  { key: 'standardPrice', label: '标准价格费用', default: false, money: true },
  { key: 'discountPrice', label: '折扣价格费用', default: false, money: true },
  { key: 'actualPrice', label: '实际价格费用', default: false, money: true },
  { key: 'paymentStatus', label: '收费情况', default: false },
  { key: 'reportDelivery', label: '报告交付方式', default: false },
  { key: 'owner', label: '样品登记人', default: true },
  { key: 'commissionOwner', label: '委托经办人', default: false },
  { key: 'contact', label: '委托人', default: false },
  { key: 'phone', label: '委托人电话', default: false },
  { key: 'customerAddress', label: '委托单位地址', default: false, truncate: 20, fullTitle: true },
] as const satisfies readonly TableColumn<Extract<keyof RegistrationSampleRow, string>>[]
export type InquirySampleColumnKey = typeof inquirySampleColumns[number]['key']
export function inquirySampleCell(row: RegistrationSampleRow, key: InquirySampleColumnKey): string {
  return tableCellText(row[key], inquirySampleColumns.find(column => column.key === key)! as TableColumn)
}
