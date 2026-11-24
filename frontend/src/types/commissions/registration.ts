import type { OriginalStore } from '../testing/originalRecords'
export interface RegistrationState { customerProjects?: import('../customers/projects').CustomerProject[]; customerProjectSequence?: number; customerAccounts?: import('../customers/accounts').CustomerAccount[]; customerCredentials?: Record<string, import('../customers/accounts').CustomerCredential> }
import type { EntryState } from '../testing/dataEntryDetail'
import type { CommissionChangeInfo } from './commissionChanges'
import type { TaskProcessingRecord } from '../testing/taskProcessing'
import type { DataEntryInfo } from '../testing/dataEntry'
import type { AssignmentInfo } from '../testing/assignment'
import type { SavedInboundReceipt } from '../samples/inbound'
import type { OutboundInfo, OutboundReturn } from '../samples/outbound'
import type { DisposalInfo } from '../samples/disposal'
import type { SampleFlowInfo } from '../samples/flow'
import type { SampleWorkflowData, SampleWorkflowQuery } from './sampleWorkflow'
import type { SampleAdvancedFields } from './sampleAdvancedQuery'
import type { CommissionAdvancedFields } from './commissionAdvancedQuery'
import type { ContractReview } from './contractReview'
import type { Actor } from '../lims'
import type { CommissionFormDetails } from './commissionForm'
import type { SampleFormDetails } from './sampleForm'
import type { SampleCommissionInfo } from './sampleCommission'

export type RegistrationWorkspace = 'registration' | 'review' | 'query' | 'changes'
export type SampleRegistrationStatus = 'pending' | 'completed' | 'void_pending' | 'voided'
export interface SampleVoidApplication {
  reason: string; appliedAt: string; appliedBy: { id: string; name: string }
  decision?: 'approved' | 'rejected'; approvedAt?: string; approvedBy?: { id: string; name: string }; rejectionReason?: string
  previousStatus: 'pending' | 'completed'; previousDataStatus: string; previousReviewStatus?: SampleReviewStatus
}
export type SampleReviewStatus = 'unreviewed' | 'reviewed' | 'approved'
export type RegistrationKind = 'commissions' | 'samples'
export interface DemoAttachment { id: string; name: string; type: string; dataUrl: string; size: number }
export type RegistrationAttachmentContext = Pick<RegistrationRecord, 'id' | 'code' | 'name' | 'version' | 'attachments'> & { canManageAttachments: boolean }
export interface DemoEvent { at: string; actor: string; action: string; reason: string; changes?: import('../testing/dataEntryRecords').FieldChange[] }
export interface RegistrationRecord {
  id: string; code: string; name: string; customer: string; departmentId: string
  owner: string; createdAt: string; version: number; contact: string; phone: string
  projects: string[]; notes: string; events: DemoEvent[]; attachments: DemoAttachment[]
}
export interface RegistrationCommission extends RegistrationRecord, CommissionFormDetails {
  status: string; contract: string; dueDate: string; requirements: string
  source: string; settlement: string; discount: number; taxRate: number
  completedReports: number; openTasks: number
}
export interface RegistrationSample extends RegistrationRecord {
  copyInfo?: { sourceId: string; sourceCode: string; actorId: string; requestId: string; fingerprint: string; pendingStatus: string }
  // Provided by the backend; distinct from commissionInfo.erpContract (project number).
  erpContractNumber?: string
  erpReportNumber?: string; contractType?: string; reportPrintCount?: number
  dataEntryInfo?: DataEntryInfo
  dataCheckInfo?: import('../testing/dataCheck').DataCheckInfo
  reportCheckInfo?: import('../reports/reportCheck').ReportCheckInfo
  reportReviewInfo?: import('../reports/reportCheck').ReportCheckInfo
  reportApprovalInfo?: import('../reports/reportCheck').ReportCheckInfo
  reportCheckIssues?: import('../reports/reportCheck').ReportCheckIssue[]
  reportChangeCount?: number
  reportRelease?: import('../reports/reportLifecycle').ReportRelease
  reportReleaseHistory?: import('../reports/reportLifecycle').ReportRelease[]
  reportPricing?: { amount: number; rule: string; at: string; standardPrice?: number; discountPrice?: number }
  assignmentInfo?: AssignmentInfo
  inboundInfo?: { site: string; groupNumber: string; receipt?: SavedInboundReceipt }
  outboundInfo?: OutboundInfo
  disposalInfo?: DisposalInfo
  sampleCompletionInfo?: import('../testing/sampleCompletion').SampleCompletionInfo
  flowInfo?: SampleFlowInfo
  taskReturns?: (OutboundReturn & { recordedAt: string; recordedBy: { id: string; name: string }; previousDataStatus: string })[]
  commissionChange?: CommissionChangeInfo
  dataChange?: CommissionChangeInfo
  workflow?: SampleWorkflowData
  reportCode: string
  reviewStatus?: SampleReviewStatus
  contractReview?: ContractReview
  voidApplication?: SampleVoidApplication
  sampleType: string; dataStatus: string
  commissionInfo: SampleCommissionInfo
  details?: SampleFormDetails
  status: SampleRegistrationStatus; commissionId: string; category: string; quantity: number; unit: string; storage: string
}
export interface RegistrationState { dailyRequests?: import('../quality/dailyRequests').DailyRequestRecord[]; testEnvironments?: import('../quality/testEnvironments').TestEnvironment[]; standards?: import('../quality/standards').StandardRecord[]; standardCategories?: import('../quality/equipmentGroups').EquipmentGroup[]; standardGroups?: import('../quality/equipmentGroups').EquipmentGroup[]; monitoringDocuments?: import('../quality/documentLibrary').LibraryDocument[]; monitoringMovements?: import('../quality/documentLibrary').DocumentMovement[]; libraryDocuments?: import('../quality/documentLibrary').LibraryDocument[]; documentMovements?: import('../quality/documentLibrary').DocumentMovement[]; maintenanceCosts?: import('../quality/maintenanceCosts').MaintenanceCostRecord[]; consumables?: import('../quality/consumables').ConsumableRecord[]; equipmentTypes?: import('../quality/equipmentTypes').EquipmentType[]; referenceMaterials?: import('../quality/referenceMaterials').MaterialRecord[]; materialAcceptances?: import('../quality/referenceMaterials').AcceptanceRecord[]; equipmentSuppliers?: import('../quality/equipmentSuppliers').SupplierRecord[]; equipmentSupplierEvaluations?: import('../quality/equipmentSuppliers').EvaluationRecord[]; equipmentLoans?: import('../quality/equipmentLoans').EquipmentLoanRecord[]; equipmentCalibrationPlans?: Record<string, import('../quality/equipmentCalibrationPlan').CalibrationPlanRecord>; equipmentInterimPlans?: import('../quality/equipmentInterimPlan').InterimPlanRecord[]; equipmentOverallPlans?: Record<string, import('../quality/equipmentOverallPlan').EquipmentOverallPlan>; equipmentGroups?: import('../quality/equipmentGroups').EquipmentGroup[]; equipmentGroupLinks?: Record<string, string[]>; equipmentProfiles?: Record<string, import('../quality/equipmentForm').EquipmentProfile>; equipmentLedger?: import('../quality/equipmentLedger').EquipmentLedgerRow[]; personnelCertificates?: import('../quality/certificates').CertificateRecord[]; approvedProjects?: import('../quality/certificates').ApprovedProjectRecord[]; personnelRecords?: import('../quality/personnel').PersonnelRecord[]; reportChangeRequests?: import('../reports/reportChange').ReportChangeRecord[]; equipmentPlans?: Record<string, import('../testing/dataEntryDetail').EntryEquipmentConfig>; originalRecords?: Record<string, OriginalStore>; dataEntries?: Record<string, EntryState>; commissions: RegistrationCommission[]; samples: RegistrationSample[]; taskProcessingRecords?: TaskProcessingRecord[] }
export type RegistrationCommissionRow = Pick<RegistrationCommission, 'id' | 'code' | 'name' | 'customer' | 'status' | 'contract' | 'owner' | 'createdAt' | 'version' | 'commissionDate' | 'contact'> & {
  sampleCount: number
  receivableAmount?: number | null; constructionUnit?: string | null; constructionCompany?: string | null
}
export type RegistrationSampleRow = Pick<RegistrationSample, 'id' | 'code' | 'reportCode' | 'reviewStatus' | 'sampleType' | 'dataStatus' | 'name' | 'customer' | 'status' | 'category' | 'quantity' | 'unit' | 'owner' | 'createdAt' | 'version' | 'commissionId'> & {
  commissionCode: string; commissionName: string; commissionOwner: string; parameters: string; projectName: string
  testPlan: string; attachmentCount: number
  standardPrice: number | null; discountPrice: number | null; actualPrice: number | null
  // Additional summary fields returned by the commission inquiry workspace only.
  erpContractNumber?: string; commissionDate?: string
  manufacturer?: string; samplingQuantity?: string; specification?: string
  trademark?: string; inspector?: string
  paymentStatus?: string; reportDelivery?: string; contact?: string; phone?: string; customerAddress?: string
}
export const commissionSearchFields = [
  { value: 'all', label: '全部' }, { value: 'code', label: '委托编号' }, { value: 'name', label: '样品/工程名称' },
  { value: 'customer', label: '委托单位' }, { value: 'contact', label: '委托人' },
  { value: 'owner', label: '委托经办人' },
] as const
export const sampleSearchFields = [
  { value: 'all', label: '全部' }, { value: 'code', label: '样品编号' },
  { value: 'reportCode', label: '报告编号' }, { value: 'owner', label: '样品登记人' },
] as const
export const inquirySampleSearchFields = [
  { value: 'commissionOwner', label: '委托经办人' }, { value: 'owner', label: '样品登记人' },
  { value: 'reviewer', label: '合同评审人' }, { value: 'customer', label: '委托单位' },
  { value: 'name', label: '工程/产品名称' }, { value: 'contact', label: '委托人' }, { value: 'manufacturer', label: '生产单位' },
] as const
// Retain the old API fields for integrations, without exposing them in the new form.
export const legacyCommissionSearchFields = ['contract'] as const
export const sampleDataStates = ['委托登记中', '完成登记', '合同评审中', '评审完成'] as const
export const sampleTypes = ['原始样品', '英文报告样品', '分项/阶段性报告样品', '补充报告'] as const
export interface RegistrationQuery {
  reportGroup?: string
  commissionAdvanced?: CommissionAdvancedFields
  sampleAdvanced?: SampleAdvancedFields
  sampleWorkflow?: SampleWorkflowQuery
  sampleCode?: string; reportCode?: string; dataStatus?: string; sampleType?: string
  commissionFrom?: string; commissionTo?: string
  contains?: string; searchField?: typeof commissionSearchFields[number]['value'] | typeof sampleSearchFields[number]['value'] | typeof inquirySampleSearchFields[number]['value'] | typeof legacyCommissionSearchFields[number]
  commissionCode?: string; keyword?: string; status?: string; from?: string; to?: string; customer?: string
  owner?: string; contract?: string; category?: string; commissionId?: string; commissionIds?: string[]
  sort?: string; direction?: string; page?: number; pageSize?: number; ids?: string[]; eligibleOnly?: boolean
}
export interface RegistrationPage<T> { items: T[]; total: number; page: number; pageSize: number }
export interface RegistrationCommissionInput extends CommissionFormDetails {
  name: string; customer: string; contract: string; dueDate: string; requirements: string
  contact: string; phone: string; projects: string[]; notes: string
  source: string; settlement: string; discount: number; taxRate: number
}
export interface RegistrationSampleInput {
  commissionInfo?: SampleCommissionInfo
  details?: SampleFormDetails
  name: string; customer: string; commissionId: string; category: string; quantity: number
  unit: string; storage: string; contact: string; phone: string; projects: string[]; notes: string
}
export interface RegistrationDependencies {
  actor: () => Actor
  locked?: () => boolean
  read?: () => RegistrationState | null
  write?: (state: RegistrationState) => void
}

