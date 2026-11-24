import { emptyReportSettings, type ReportSettings } from './reportSettings'
export const sampleTextKeys = [
  'testPlan', 'testPlanId', 'testPlanCode', 'testBasis', 'assessmentStandard', 'testingDepartment', 'testingLocation',
  'nameplate', 'deliveryDate', 'appearance', 'appearanceNotes',
  'taskRecipient', 'inspectorPhone', 'inspector', 'trademark',
  'productCode', 'manufacturer', 'productionDate', 'specification', 'requestedTestDate',
  'internalNotes', 'samplingOrganization', 'samplingLocation', 'sampler', 'samplingTime', 'samplingQuantity',
  'samplingBase', 'inspectedOrganization', 'taskSource', 'standardPrice', 'paymentMethod', 'paymentStatus',
  'paidAmount', 'feeNotes', 'externalDueDate', 'internalDueDate', 'disposalMethod', 'reportDelivery',
  'mailingAddress', 'reportCopies', 'reportForm', 'onsiteArrangement', 'appointmentDate',
] as const
export const sampleFlagKeys = ['urgent', 'useAssessmentStandard', 'assessmentEnglishBookMarks', 'hasExternalDueDate', 'hasInternalDueDate', 'hasAppointment', 'englishBookMarks'] as const
export type SampleTextKey = typeof sampleTextKeys[number]
export const sampleDateKeys = ['productionDate', 'requestedTestDate', 'deliveryDate', 'samplingTime', 'externalDueDate', 'internalDueDate', 'appointmentDate'] as const satisfies readonly SampleTextKey[]
export type SampleFlagKey = typeof sampleFlagKeys[number]
export type SampleFormDetails = Record<SampleTextKey, string> & Record<SampleFlagKey, boolean> & { reportSettings: ReportSettings; testBasisIds: string[]; testBasisSeparators: string[]; assessmentStandardIds: string[]; assessmentStandardSeparators: string[]; subprojects: SampleSubproject[]; trademarkImage: SampleTrademarkImage | null }
export function emptySampleDetails(): SampleFormDetails {
  const text = Object.fromEntries(sampleTextKeys.map(key => [key, ''])) as Record<SampleTextKey, string>
  const flags = Object.fromEntries(sampleFlagKeys.map(key => [key, false])) as Record<SampleFlagKey, boolean>
  return { ...text, ...flags, reportSettings: emptyReportSettings(), testBasisIds: [], testBasisSeparators: [], assessmentStandardIds: [], assessmentStandardSeparators: [], subprojects: [], trademarkImage: null }
}
export interface SampleFormOptions {
  subprojectOptions: SampleSubprojectOption[]
  choices: Partial<Record<SampleTextKey, string[]>>
}
export interface TestPlanNode {
  parentId?: string
  id: string
  name: string
  kind: 'group' | 'plan'
  code: string
  groupName: string
  inboundSampleCount?: number
  outboundSampleCount?: number
  disposalSampleCount?: number
  flowSampleCount?: number
  assignmentSampleCount?: number
  pickupSampleCount?: number
  taskQuerySampleCount?: number
  dataEntrySampleCount?: number
  dataCheckSampleCount?: number
  sampleCopySampleCount?: number
  dataChangeSampleCount?: number
  reportCheckSampleCount?: number
  reportReviewSampleCount?: number
  reportApprovalSampleCount?: number
  reportPrintSampleCount?: number
  reportSigningSampleCount?: number
  reportArchiveSampleCount?: number
  reportQuerySampleCount?: number
  reportDistributionSampleCount?: number
}
export interface TestPlanQuery { parentId?: string; keyword?: string; page?: number; pageSize?: number; sampleScope?: string }


export interface SampleSubproject {
  id: string
  name: string
  accountingDepartment: string
  businessCategory: string
  amount: string
  receivedAmount: string
  receiptType: string
  paymentDescription: string
  notes: string
}
export type SampleSubprojectOption = Pick<SampleSubproject, 'name' | 'accountingDepartment' | 'businessCategory'>
export const sampleSubprojectFields = [
  { key: 'name', label: '子项目名称' }, { key: 'accountingDepartment', label: '核算部门' },
  { key: 'businessCategory', label: '业务三级分类' }, { key: 'amount', label: '子项金额', money: true },
  { key: 'receivedAmount', label: '收款金额', money: true }, { key: 'receiptType', label: '收款类型' },
  { key: 'paymentDescription', label: '付款说明' }, { key: 'notes', label: '备注' },
] as const
export const sampleSubprojectReceiptTypes = ['预收款', '结算款', '进度款', '保证金', '奖惩', '其他'] as const
export function emptySampleSubproject(): SampleSubproject {
  return { id: '', name: '', accountingDepartment: '', businessCategory: '', amount: '', receivedAmount: '', receiptType: '预收款', paymentDescription: '', notes: '' }
}

export interface SampleTrademarkImage { name: string; dataUrl: string }
