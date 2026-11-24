import type { TableColumn } from '../common/table'
import type { RegistrationPage } from '../commissions/registration'
import type { PlanSelectionState } from '../samples/inbound'
import type { DataEntryQuery, DataEntryRow } from './dataEntry'
import { dataEntryDateFields } from './dataEntry'

export const dataCheckStates = ['检测数据校核中', '检测数据校核完成'] as const
export const dataCheckDateFields = [...dataEntryDateFields, { value: 'checkDate', label: '校核日期' }] as const
export interface DataCheckQuery extends Omit<DataEntryQuery, 'dateField'> { dateField?: typeof dataCheckDateFields[number]['value'] }
export interface DataCheckInfo { actorId: string; actorName: string; at: string; previousDataStatus: string }
export interface DataCheckRow extends DataEntryRow { checker: string; checkDate: string; canCheck: boolean; canUndoCheck: boolean }
export interface DataCheckPage extends RegistrationPage<DataCheckRow> { planSelection: PlanSelectionState }
export const dataCheckActions = [
  { label: '数据校核', icon: 'ti ti-circle-check' },
  { label: '撤销校核', icon: 'ti ti-arrow-back-up' },
  { label: '查看附件', icon: 'ti ti-paperclip' },
] as const
export const dataCheckColumns = [
  { key: 'code', label: '样品编号', required: true, sort: 'code' },
  { key: 'reportCode', label: '报告编号', default: true },
  { key: 'sampleType', label: '样品类型', default: true },
  { key: 'commissionCode', label: '委托编号', default: false },
  { key: 'name', label: '样品/工程名称', default: true, truncate: 12, fullTitle: true },
  { key: 'parameters', label: '检测参数', default: true, truncate: 12, fullTitle: true },
  { key: 'dataStatus', label: '当前数据状态', default: true },
  { key: 'projectName', label: '检测方案', default: false, truncate: 14, fullTitle: true },
  { key: 'checker', label: '校核人', default: true },
  { key: 'checkDate', label: '校核日期', default: true },
  { key: 'attachmentCount', label: '附件', default: false },
  { key: 'conclusion', label: '结论状态', default: false },
  { key: 'customer', label: '委托单位', default: false, truncate: 14, fullTitle: true },
  { key: 'contact', label: '委托人', default: false },
  { key: 'engineeringName', label: '项目名称', default: false, truncate: 14, fullTitle: true },
  { key: 'tester1', label: '试验人1', default: false },
  { key: 'tester2', label: '试验人2', default: false },
  { key: 'testStartDate', label: '试验开始日期', default: false },
  { key: 'testEndDate', label: '试验结束日期', default: false },
  { key: 'commissionDate', label: '委托日期', default: false, sort: 'commissionDate' },
] as const satisfies readonly TableColumn<keyof DataCheckRow>[]
