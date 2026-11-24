import type { DailyRequestDraft, DailyRequestRow, DailyRequestQuery, DailyRequestPage } from '../../types/quality/dailyRequests'
import type { EnvironmentQuery, EnvironmentPage, EnvironmentDetail, EnvironmentPlan } from '../../types/quality/testEnvironments'
import type { StandardDraft, StandardRow, StandardQuery, StandardPage, StandardOptions } from '../../types/quality/standards'
import { definitionApiPath, type DefinitionModule } from '../../types/quality/equipmentGroups'
import type { DocumentModule, LibraryDocumentDraft, LibraryDocumentRow, DocumentMovement, DocumentMovementKind, DocumentQuery, DocumentPage } from '../../types/quality/documentLibrary'
import type { MaintenanceCostDraft, MaintenanceCostRecord, MaintenanceCostQuery, MaintenanceCostPage } from '../../types/quality/maintenanceCosts'
import type { ConsumableDraft, ConsumableRecord, ConsumableQuery, ConsumablePage } from '../../types/quality/consumables'
import type { EquipmentTypeQuery, EquipmentTypePage, EquipmentTypeRow } from '../../types/quality/equipmentTypes'
import type { MaterialKind, MaterialQuery, MaterialPage, MaterialRecord, MaterialDraft, AcceptanceRecord, AcceptanceDraft } from '../../types/quality/referenceMaterials'
import type { SupplierListKind, SupplierQuery, SupplierRecord, SupplierDraft, SupplierPage, EvaluationRecord, EvaluationDraft } from '../../types/quality/equipmentSuppliers'
import type { LoanTab, EquipmentLoanQuery, EquipmentLoanPage, EquipmentLoanRow, EquipmentLoanContext, EquipmentBorrowInput, EquipmentReturnInput } from '../../types/quality/equipmentLoans'
import type { CertificateListKind, CertificateQuery, CertificatePage, CertificateDetail, ApprovedProjectDetail, CertificateOptions } from '../../types/quality/certificates'
import type { EquipmentLedgerPage, EquipmentLedgerQuery } from '../../types/quality/equipmentLedger'
import type { EquipmentGroupContext, EquipmentGroupSubmission, EquipmentGroupQuery, EquipmentGroupPage, EquipmentGroupRow } from '../../types/quality/equipmentGroups'
import type { MonthlyCalibrationQuery } from '../../types/quality/monthlyCalibration'
import type { OverallPlanQuery, OverallPlanPage, OverallPlanRow, OverallPlanSubmission } from '../../types/quality/equipmentOverallPlan'
import type { InterimPlanQuery, InterimPlanPage, InterimPlanRow, InterimPlanDraft, InterimPlanEquipmentPage } from '../../types/quality/equipmentInterimPlan'
import type { CalibrationPlanQuery, CalibrationPlanPage, CalibrationPlanRow, CalibrationPlanSubmission } from '../../types/quality/equipmentCalibrationPlan'
import type { EquipmentDraft, EquipmentRecord, EquipmentFormOptions, EquipmentBatchInput } from '../../types/quality/equipmentForm'
import { uploadRequest, type TransferProgress } from '../common/uploadRequest'
import type { PersonnelQuery, PersonnelPage, PersonnelRecord, PersonnelDraft } from '../../types/quality/personnel'
import type { ReportChangeQuery, ReportChangePage, ReportChangeRow, ReportChangeDraft, ReportChangeCandidate, ReportChangeCandidateQuery, ReportChangeSource } from '../../types/reports/reportChange'
import type { ReportDistributionDetail } from '../../types/reports/reportDistribution'
import type { ReportQueryQuery, ReportQueryPage } from '../../types/reports/reportQuery'
import type { ReportPricingDetail } from '../../types/reports/reportPricing'
import type { OriginalContext, ElnPage } from '../../types/testing/originalRecords'
import type { ReportLifecycleQuery, ReportLifecyclePage, ReportLifecycleRow, ReportRelease } from '../../types/reports/reportLifecycle'
import type { ReportPrintQuery, ReportPrintPage } from '../../types/reports/reportPrint'
import type { EntryPeopleQuery, EntryPeoplePage, EntryPersonCandidate, EntryPersonRole } from '../../types/testing/dataEntryDetail'
import type { EntryDetail } from '../../types/testing/dataEntryDetail'
import type { EntryRecordsQuery, EntryRecordsPage } from '../../types/testing/dataEntryRecords'
import type { DataEntryQuery, DataEntryPage } from '../../types/testing/dataEntry'
import type { DataChangeQuery, DataChangePage } from '../../types/testing/dataChanges'
import type { DataQueryQuery, DataQueryPage } from '../../types/testing/dataQuery'
import type { DataCheckQuery, DataCheckPage } from '../../types/testing/dataCheck'
import type { ReportBatchSubmission, ReportStage, ReportCheckQuery, ReportCheckPage, ReportCheckConfirmation, ReportCheckRejection } from '../../types/reports/reportCheck'
import type { SampleCopyQuery, SampleCopyPage, SampleCopyInput } from '../../types/testing/sampleCopy'
import type { InboundAction, InboundReceipt, InboundPage, InboundQuery, PlanSelection, PlanSelectionState, PlanSelectionContext, PlanSelectionToggle } from '../../types/samples/inbound'
import type { RegistrationAttachmentContext } from '../../types/commissions/registration'
import type { TaskProcessingInput, TaskProcessingQuery, TaskProcessingPage, TaskProcessingDetail, TaskProcessingAttachments } from '../../types/testing/taskProcessing'
import type { OutboundSubmission, OutboundReturn } from '../../types/samples/outbound'
import type { DisposalQuery, DisposalSubmission } from '../../types/samples/disposal'
import type { SampleCompletionQuery, SampleCompletionPage, SampleCompletionSubmission } from '../../types/testing/sampleCompletion'
import type { FlowQuery, FlowPage } from '../../types/samples/flow'
import type { AssignmentQuery, AssignmentPage, AssignmentSubmission } from '../../types/testing/assignment'
import type { TaskPrintContext, TaskPrintJob } from '../../types/testing/taskPrint'
import type { TaskQuery, TaskQueryPage } from '../../types/testing/taskQuery'
import type { PickupQuery, PickupPage, PickupReceipt } from '../../types/testing/pickup'
import type { CancellationQuery, CancellationRow, CancellationSubmission } from '../../types/commissions/cancellationApproval'
import type { CommissionChangeQuery, CommissionChangeRow } from '../../types/commissions/commissionChanges'
import type { BatchReviewTarget, BatchReviewCheckResponse, BatchReviewSubmission, ContractReviewSubmission, ReviewCheckOptions, ReviewCheckResult } from '../../types/commissions/contractReview'
import type { BulkCommissionContext, BulkCommissionResult, BulkCommissionTarget } from '../../types/commissions/bulkCommission'
import type { SampleCommissionInfo } from '../../types/commissions/sampleCommission'
import type { ReportSettingsConfig } from '../../types/commissions/reportSettings'
import type { ManufacturerQuery, ManufacturerPage } from '../../types/commissions/manufacturer'
import { currentActor, sessionLocked } from '../../stores/session'
import type { SampleFormOptions, TestPlanNode, TestPlanQuery } from '../../types/commissions/sampleForm'
import type { TestBasisPage, TestBasisQuery, TestBasisSelection } from '../../types/commissions/testBasis'
import type { PrintRequest, PrintTask, PrintContext } from '../../types/commissions/commissionPrint'
import { AppError, type ErrorCode } from '../common/errors'
import type { RegistrationContract, RegistrationContractQuery, RegistrationOrganization, RegistrationOrganizationQuery } from '../../types/commissions/commissionForm'
import type { RegistrationWorkspace, RegistrationQuery, RegistrationPage, RegistrationCommissionRow, RegistrationSampleRow, RegistrationCommission, RegistrationSample, RegistrationKind, RegistrationCommissionInput, RegistrationSampleInput, DemoAttachment } from '../../types/commissions/registration'

import { platformAdapter } from '../platform/adapter'
async function request<T>(path: string, method = 'GET', data?: unknown, signal?: AbortSignal, blob = false, _progress?: TransferProgress): Promise<T> {
  if (sessionLocked.value) throw new AppError('LOCKED', '工作空间已锁定。')
  return platformAdapter<T>(path, method, data, signal, blob)
}
const workflow = (workspace?: RegistrationWorkspace) => workspace && workspace !== 'registration' ? { workspace } : {}
// HTTP adapter only: no datasets, joins, filtering, pagination loops or browser storage here.
export const registrationDemo = {
  customerProjects: (query: import('../../types/customers/projects').ProjectQuery, signal?: AbortSignal) => request<import('../../types/customers/projects').ProjectPage>('/customers/projects/query', 'POST', query, signal),
  customerProject: (id: string, signal?: AbortSignal) => request<import('../../types/customers/projects').CustomerProject>('/customers/projects/detail', 'POST', { id }, signal),
  projectOptions: (signal?: AbortSignal) => request<import('../../types/customers/projects').ProjectOptions>('/customers/projects/options', 'POST', {}, signal),
  saveCustomerProject: (input: import('../../types/customers/projects').ProjectDraft) => request<import('../../types/customers/projects').CustomerProject>('/customers/projects/save', 'POST', input),
  batchCustomerProjects: (ids: string[], changes: import('../../types/customers/projects').ProjectDraft) => request<{ count: number }>('/customers/projects/batch', 'POST', { ids, changes }),
  deleteCustomerProject: (id: string) => request<{ id: string }>('/customers/projects/delete', 'POST', { id }),
  importCustomerProjects: (csv: string) => request<{ count: number }>('/customers/projects/import', 'POST', { csv }),
  projectTemplate: () => request<Blob>('/customers/projects/template', 'POST', {}, undefined, true),
  exportCustomerProjects: (query: import('../../types/customers/projects').ProjectQuery) => request<Blob>('/customers/projects/export', 'POST', query, undefined, true),
  customerAccounts: (query: import('../../types/customers/accounts').CustomerAccountQuery, signal?: AbortSignal) => request<import('../../types/customers/accounts').CustomerAccountPage>('/customers/accounts/query', 'POST', query, signal),
  customerAccount: (id: string, signal?: AbortSignal) => request<import('../../types/customers/accounts').CustomerAccountDetail>('/customers/accounts/detail', 'POST', { id }, signal),
  saveCustomerAccount: (input: import('../../types/customers/accounts').CustomerAccountDraft & { id?: string }) => request<import('../../types/customers/accounts').CustomerAccountDetail>('/customers/accounts/save', 'POST', input),
  resetCustomerPassword: (id: string) => request<{ code: string; password: string; mustChangePassword: boolean }>('/customers/accounts/reset-password', 'POST', { id }),
  exportCustomerAccounts: (query: import('../../types/customers/accounts').CustomerAccountQuery) => request<Blob>('/customers/accounts/export', 'POST', query, undefined, true),
  dailyRequests: (query: DailyRequestQuery, signal?: AbortSignal) => request<DailyRequestPage>('/quality/requests/query', 'POST', query, signal),
  dailyRequestDetail: (id: string, signal?: AbortSignal) => request<DailyRequestRow>('/quality/requests/detail', 'POST', { id }, signal),
  saveDailyRequest: (input: DailyRequestDraft & { id?: string; version?: number; intent: 'save' | 'submit'; attachmentDraftId?: string }) => request<DailyRequestRow>('/quality/requests/save', 'POST', input),
  dailyRequestAction: (input: { id: string; version: number; withdrawalReason?: string }, kind: 'withdraw' | 'delete') => request<{ id: string }>(`/quality/requests/${kind}`, 'POST', input),
  exportDailyRequests: (query: DailyRequestQuery) => request<Blob>('/quality/requests/export', 'POST', query, undefined, true),
  dailyApprovals: (query: DailyRequestQuery, signal?: AbortSignal) => request<DailyRequestPage>('/quality/approvals/query', 'POST', query, signal),
  dailyApprovalDetail: (id: string, signal?: AbortSignal) => request<DailyRequestRow>('/quality/approvals/detail', 'POST', { id }, signal),
  dailyApprovalAction: (input: { id: string; version: number; result: string; opinion: string }, operation: 'approve' | 'revoke' | 'void') => request<DailyRequestRow>(`/quality/approvals/${operation}`, 'POST', input),
  exportDailyApprovals: (query: DailyRequestQuery) => request<Blob>('/quality/approvals/export', 'POST', query, undefined, true),
  testEnvironments: (query: EnvironmentQuery, signal?: AbortSignal) => request<EnvironmentPage>('/quality/environment/query', 'POST', query, signal),
  testEnvironmentDetail: (id: string, signal?: AbortSignal) => request<EnvironmentDetail>('/quality/environment/detail', 'POST', { id }, signal),
  testEnvironmentPlans: (signal?: AbortSignal) => request<EnvironmentPlan[]>('/quality/environment/options', 'POST', {}, signal),
  saveTestEnvironment: (input: { id?: string; version?: number; name: string; planIds: string[] }) => request<EnvironmentDetail>('/quality/environment/save', 'POST', input),
  deleteTestEnvironment: (id: string, version: number) => request<{ id: string }>('/quality/environment/delete', 'POST', { id, version }),
  exportTestEnvironments: (query: EnvironmentQuery) => request<Blob>('/quality/environment/export', 'POST', query, undefined, true),
  monthlyCalibration: (query: MonthlyCalibrationQuery, signal?: AbortSignal, departmentMode = false) => request<EquipmentLedgerPage>(`/quality/equipment/${departmentMode ? 'department-monthly-calibration' : 'monthly-calibration'}/query`, 'POST', query, signal),
  exportMonthlyCalibration: (query: MonthlyCalibrationQuery, departmentMode = false) => request<Blob>(`/quality/equipment/${departmentMode ? 'department-monthly-calibration' : 'monthly-calibration'}/export`, 'POST', query, undefined, true),
  referenceMaterials: (query: MaterialQuery, signal?: AbortSignal) => request<MaterialPage<MaterialRecord>>('/quality/equipment/reference-materials/query', 'POST', { ...query, kind: 'materials' }, signal),
  materialAcceptances: (query: MaterialQuery, signal?: AbortSignal) => request<MaterialPage<AcceptanceRecord>>('/quality/equipment/reference-materials/query', 'POST', { ...query, kind: 'acceptances' }, signal),
  referenceMaterialDetail: (id: string, signal?: AbortSignal) => request<MaterialRecord>('/quality/equipment/reference-materials/detail', 'POST', { id, kind: 'materials' }, signal),
  materialAcceptanceDetail: (id: string, signal?: AbortSignal) => request<AcceptanceRecord>('/quality/equipment/reference-materials/detail', 'POST', { id, kind: 'acceptances' }, signal),
  saveReferenceMaterial: (input: MaterialDraft & { id?: string; version?: number }) => request<MaterialRecord>('/quality/equipment/reference-materials/save', 'POST', { ...input, kind: 'materials' }),
  saveMaterialAcceptance: (input: AcceptanceDraft & { id?: string; version?: number }) => request<AcceptanceRecord>('/quality/equipment/reference-materials/save', 'POST', { ...input, kind: 'acceptances' }),
  deleteMaterialRecord: (kind: MaterialKind, id: string, version: number, materialVersion?: number) => request<{ id: string }>('/quality/equipment/reference-materials/delete', 'POST', { kind, id, version, materialVersion }),
  exportMaterialRecords: (kind: MaterialKind, query: MaterialQuery) => request<Blob>('/quality/equipment/reference-materials/export', 'POST', { ...query, kind }, undefined, true),
  materialPeople: (query: { account: string; name: string; certificateNumber: string; page: number; pageSize: number }, signal?: AbortSignal) => request<EntryPeoplePage>('/quality/equipment/reference-materials/people', 'POST', query, signal),
  materialPerson: (id: string, signal?: AbortSignal) => request<EntryPersonCandidate>('/quality/equipment/reference-materials/person', 'POST', { id }, signal),
  equipmentSuppliers: (query: SupplierQuery, signal?: AbortSignal) => request<SupplierPage<SupplierRecord>>('/quality/equipment/suppliers/query', 'POST', { ...query, kind: 'suppliers' }, signal),
  supplierEvaluations: (query: SupplierQuery, signal?: AbortSignal) => request<SupplierPage<EvaluationRecord>>('/quality/equipment/suppliers/query', 'POST', { ...query, kind: 'evaluations' }, signal),
  supplierDetail: (id: string, signal?: AbortSignal) => request<SupplierRecord>('/quality/equipment/suppliers/detail', 'POST', { id, kind: 'suppliers' }, signal),
  supplierEvaluationDetail: (id: string, signal?: AbortSignal) => request<EvaluationRecord>('/quality/equipment/suppliers/detail', 'POST', { id, kind: 'evaluations' }, signal),
  supplierOptions: (signal?: AbortSignal) => request<Pick<SupplierRecord, 'id' | 'name' | 'services'>[]>('/quality/equipment/suppliers/options', 'POST', {}, signal),
  saveEquipmentSupplier: (input: SupplierDraft & { id?: string; version?: number }) => request<SupplierRecord>('/quality/equipment/suppliers/save', 'POST', { ...input, kind: 'suppliers' }),
  saveSupplierEvaluation: (input: EvaluationDraft & { id?: string; version?: number }) => request<EvaluationRecord>('/quality/equipment/suppliers/save', 'POST', { ...input, kind: 'evaluations' }),
  deleteEquipmentSupplierRecord: (kind: SupplierListKind, id: string, version: number) => request<{ id: string }>('/quality/equipment/suppliers/delete', 'POST', { kind, id, version }),
  exportEquipmentSupplierRecords: (kind: SupplierListKind, query: SupplierQuery) => request<Blob>('/quality/equipment/suppliers/export', 'POST', { ...query, kind }, undefined, true),
  equipmentLoans: (kind: LoanTab, query: EquipmentLoanQuery, signal?: AbortSignal) => request<EquipmentLoanPage>('/quality/equipment/loans/query', 'POST', { ...query, kind }, signal),
  equipmentLoanContext: (mode: 'borrow' | 'return', ids: string[], signal?: AbortSignal) => request<EquipmentLoanContext>('/quality/equipment/loans/context', 'POST', { mode, ids }, signal),
  equipmentLoanDetail: (id: string, signal?: AbortSignal) => request<EquipmentLoanRow>('/quality/equipment/loans/detail', 'POST', { id }, signal),
  borrowEquipment: (input: EquipmentBorrowInput) => request<{ count: number }>('/quality/equipment/loans/borrow', 'POST', input),
  returnEquipment: (input: EquipmentReturnInput) => request<{ count: number }>('/quality/equipment/loans/return', 'POST', input),
  exportEquipmentLoanRecords: (query: EquipmentLoanQuery) => request<Blob>('/quality/equipment/loans/history-export', 'POST', query, undefined, true),
  exportEquipmentLoans: (kind: LoanTab, query: EquipmentLoanQuery) => request<Blob>('/quality/equipment/loans/export', 'POST', { ...query, kind }, undefined, true),
  equipmentLedger: (query: EquipmentLedgerQuery, signal?: AbortSignal, departmentMode = false) => request<EquipmentLedgerPage>(`/quality/equipment/${departmentMode ? 'department-ledger' : 'ledger'}/query`, 'POST', query, signal),
  equipmentTemplate: () => request<Blob>('/quality/equipment/ledger/template', 'GET', undefined, undefined, true),
  importEquipment: (csv: string, progress?: TransferProgress) => request<{ count: number }>('/quality/equipment/ledger/import', 'POST', { csv }, undefined, false, progress),
  equipmentFormOptions: (signal?: AbortSignal) => request<EquipmentFormOptions>('/quality/equipment/ledger/options', 'GET', undefined, signal),
  equipmentTestPlans: (query: TestPlanQuery = {}, signal?: AbortSignal) => request<RegistrationPage<TestPlanNode>>('/quality/equipment/ledger/plans', 'POST', query, signal),
  equipmentPlanSelection: (selection: PlanSelection, toggle?: PlanSelectionToggle, signal?: AbortSignal) => request<PlanSelectionContext>('/quality/equipment/ledger/plan-selection', 'POST', { selection, toggle }, signal),
  equipmentDetail: (id: string, signal?: AbortSignal) => request<EquipmentRecord>(`/quality/equipment/ledger/${encodeURIComponent(id)}/detail`, 'GET', undefined, signal),
  deleteEquipment: (id: string, version: number) => request<{ id: string }>(`/quality/equipment/ledger/${encodeURIComponent(id)}/delete`, 'POST', { version }),
  batchUpdateEquipment: (data: EquipmentBatchInput) => request<{ count: number }>('/quality/equipment/ledger/batch-update', 'POST', data),
  equipmentGroupContext: (ids: string[], signal?: AbortSignal) => request<EquipmentGroupContext>('/quality/equipment/ledger/group-context', 'POST', { ids }, signal),
  libraryDocuments: (query: DocumentQuery, signal?: AbortSignal, module: DocumentModule = 'library') => request<DocumentPage<LibraryDocumentRow>>(`/quality/documents/${module}/query`, 'POST', query, signal),
  libraryDocumentDetail: (id: string, signal?: AbortSignal, module: DocumentModule = 'library') => request<LibraryDocumentRow>(`/quality/documents/${module}/detail`, 'POST', { id }, signal),
  saveLibraryDocument: (input: LibraryDocumentDraft & { id?: string; version?: number }, module: DocumentModule = 'library') => request<LibraryDocumentRow>(`/quality/documents/${module}/save`, 'POST', input),
  deleteLibraryDocument: (id: string, version: number, module: DocumentModule = 'library') => request(`/quality/documents/${module}/delete`, 'POST', { id, version }),
  documentMovement: (kind: DocumentMovementKind, input: { id: string; version: number; quantity: number; date: string; person: string }, module: DocumentModule = 'library') => request<DocumentMovement>(`/quality/documents/${module}/move`, 'POST', { ...input, kind }),
  documentHistory: (kind: DocumentMovementKind, query: DocumentQuery, signal?: AbortSignal, module: DocumentModule = 'library') => request<DocumentPage<DocumentMovement>>(`/quality/documents/${module}/history`, 'POST', { ...query, kind }, signal),
  exportLibraryDocuments: (query: DocumentQuery, module: DocumentModule = 'library') => request<Blob>(`/quality/documents/${module}/export`, 'POST', query, undefined, true),
  exportDocumentHistory: (kind: DocumentMovementKind, query: DocumentQuery, module: DocumentModule = 'library') => request<Blob>(`/quality/documents/${module}/export-history`, 'POST', { ...query, kind }, undefined, true),
  saveLibraryDocumentFiles: (input: { id: string; version: number; files: DemoAttachment[]; attachmentDraftId?: string }, module: DocumentModule = 'library') => request<LibraryDocumentRow>(`/quality/documents/${module}/files`, 'POST', input),
  maintenanceCosts: (query: MaintenanceCostQuery, signal?: AbortSignal) => request<MaintenanceCostPage>('/quality/equipment/maintenance-costs/query', 'POST', query, signal),
  maintenanceCostDetail: (id: string, signal?: AbortSignal) => request<MaintenanceCostRecord>('/quality/equipment/maintenance-costs/detail', 'POST', { id }, signal),
  saveMaintenanceCost: (input: MaintenanceCostDraft & { id?: string; version?: number }) => request<MaintenanceCostRecord>('/quality/equipment/maintenance-costs/save', 'POST', input),
  deleteMaintenanceCost: (id: string, version: number) => request<{ id: string }>('/quality/equipment/maintenance-costs/delete', 'POST', { id, version }),
  exportMaintenanceCosts: (query: MaintenanceCostQuery) => request<Blob>('/quality/equipment/maintenance-costs/export', 'POST', query, undefined, true),
  maintenanceCostTemplate: () => request<Blob>('/quality/equipment/maintenance-costs/template', 'POST', {}, undefined, true),
  importMaintenanceCosts: (csv: string) => request<{ count: number }>('/quality/equipment/maintenance-costs/import', 'POST', { csv }),
  consumables: (query: ConsumableQuery, signal?: AbortSignal) => request<ConsumablePage>('/quality/equipment/consumables/query', 'POST', query, signal),
  consumableDetail: (id: string, signal?: AbortSignal) => request<ConsumableRecord>('/quality/equipment/consumables/detail', 'POST', { id }, signal),
  saveConsumable: (input: ConsumableDraft & { id?: string; version?: number }) => request<ConsumableRecord>('/quality/equipment/consumables/save', 'POST', input),
  deleteConsumable: (id: string, version: number) => request<{ id: string }>('/quality/equipment/consumables/delete', 'POST', { id, version }),
  exportConsumables: (query: ConsumableQuery) => request<Blob>('/quality/equipment/consumables/export', 'POST', query, undefined, true),
  consumableTemplate: () => request<Blob>('/quality/equipment/consumables/template', 'POST', {}, undefined, true),
  importConsumables: (csv: string) => request<{ count: number }>('/quality/equipment/consumables/import', 'POST', { csv }),
  equipmentTypeDefinitions: (query: EquipmentTypeQuery, signal?: AbortSignal) => request<EquipmentTypePage>('/quality/equipment/types/query', 'POST', query, signal),
  equipmentTypeDetail: (id: string, signal?: AbortSignal) => request<EquipmentTypeRow>('/quality/equipment/types/detail', 'POST', { id }, signal),
  saveEquipmentType: (input: { name: string; lendable: boolean; notes: string; id?: string; version?: number }) => request<EquipmentTypeRow>('/quality/equipment/types/save', 'POST', input),
  deleteEquipmentType: (id: string, version: number) => request<{ id: string }>('/quality/equipment/types/delete', 'POST', { id, version }),
  exportEquipmentTypes: (query: EquipmentTypeQuery) => request<Blob>('/quality/equipment/types/export', 'POST', query, undefined, true),
  standards: (query: StandardQuery, signal?: AbortSignal, departmentMode = false) => request<StandardPage>(`/quality/standards/${departmentMode ? 'department-library' : 'library'}/query`, 'POST', query, signal),
  standardDetail: (id: string, signal?: AbortSignal) => request<StandardRow>('/quality/standards/library/detail', 'POST', { id }, signal),
  standardOptions: (signal?: AbortSignal) => request<StandardOptions>('/quality/standards/library/options', 'POST', {}, signal),
  saveStandard: (data: StandardDraft & { id?: string; version?: number }) => request<StandardRow>('/quality/standards/library/save', 'POST', data),
  deleteStandard: (id: string, version: number) => request('/quality/standards/library/delete', 'POST', { id, version }),
  standardGroupContext: (ids: string[], signal?: AbortSignal) => request<EquipmentGroupContext>('/quality/standards/library/group-context', 'POST', { ids }, signal),
  saveStandardGroups: (data: EquipmentGroupSubmission) => request('/quality/standards/library/group-associations', 'POST', data),
  standardTemplate: () => request<Blob>('/quality/standards/library/template', 'POST', {}, undefined, true),
  importStandards: (csv: string) => request<{ count: number }>('/quality/standards/library/import', 'POST', { csv }),
  exportStandards: (query: StandardQuery, departmentMode = false) => request<Blob>(`/quality/standards/${departmentMode ? 'department-library' : 'library'}/export`, 'POST', query, undefined, true),
  equipmentGroupDefinitions: (query: EquipmentGroupQuery, signal?: AbortSignal, module: DefinitionModule = 'equipment') => request<EquipmentGroupPage>(`${definitionApiPath(module)}/query`, 'POST', query, signal),
  overallPlans: (query: OverallPlanQuery, signal?: AbortSignal) => request<OverallPlanPage>('/quality/equipment/plans/overall/query', 'POST', query, signal),
  interimPlans: (query: InterimPlanQuery, signal?: AbortSignal) => request<InterimPlanPage>('/quality/equipment/plans/interim/query', 'POST', query, signal),
  calibrationPlans: (query: CalibrationPlanQuery, signal?: AbortSignal) => request<CalibrationPlanPage>('/quality/equipment/plans/calibration/query', 'POST', query, signal),
  exportCalibrationPlans: (query: CalibrationPlanQuery) => request<Blob>('/quality/equipment/plans/calibration/export', 'POST', query, undefined, true),
  calibrationPlanDetail: (id: string, signal?: AbortSignal) => request<CalibrationPlanRow>('/quality/equipment/plans/calibration/detail', 'POST', { id }, signal),
  saveCalibrationPlan: (data: CalibrationPlanSubmission, submit = false) => request<CalibrationPlanRow>(`/quality/equipment/plans/calibration/${submit ? 'submit' : 'save'}`, 'POST', data),
  interimPlanEquipmentChoices: (query: InterimPlanQuery, signal?: AbortSignal) => request<InterimPlanEquipmentPage>('/quality/equipment/plans/interim/equipment/query', 'POST', query, signal),
  interimPlanDetail: (id: string, signal?: AbortSignal) => request<InterimPlanRow>('/quality/equipment/plans/interim/detail', 'POST', { id }, signal),
  saveInterimPlan: (data: InterimPlanDraft & { id?: string; version?: number }) => request<InterimPlanRow>('/quality/equipment/plans/interim/save', 'POST', data),
  deleteInterimPlan: (id: string, version: number) => request<{ id: string }>('/quality/equipment/plans/interim/delete', 'POST', { id, version }),
  exportInterimPlans: (query: InterimPlanQuery) => request<Blob>('/quality/equipment/plans/interim/export', 'POST', query, undefined, true),
  printInterimPlans: (query: InterimPlanQuery) => request<InterimPlanPage>('/quality/equipment/plans/interim/print', 'POST', query),
  overallPlanDetail: (id: string, signal?: AbortSignal) => request<OverallPlanRow>('/quality/equipment/plans/overall/detail', 'POST', { id }, signal),
  saveOverallPlan: (data: OverallPlanSubmission, batch = false) => request<{ count: number }>(`/quality/equipment/plans/overall/${batch ? 'batch' : 'save'}`, 'POST', data),
  exportOverallPlans: (query: OverallPlanQuery) => request<Blob>('/quality/equipment/plans/overall/export', 'POST', query, undefined, true),
  printOverallPlans: (query: OverallPlanQuery) => request<OverallPlanPage>('/quality/equipment/plans/overall/print', 'POST', query),
  equipmentGroupDetail: (id: string, signal?: AbortSignal, module: DefinitionModule = 'equipment') => request<EquipmentGroupRow>(`${definitionApiPath(module)}/detail`, 'POST', { id }, signal),
  saveEquipmentGroupDefinition: (data: { id?: string; version?: number; name: string }, module: DefinitionModule = 'equipment') => request<EquipmentGroupRow>(`${definitionApiPath(module)}/save`, 'POST', data),
  deleteEquipmentGroupDefinition: (id: string, version: number, module: DefinitionModule = 'equipment') => request<{ id: string }>(`${definitionApiPath(module)}/delete`, 'POST', { id, version }),
  exportEquipmentGroupDefinitions: (query: EquipmentGroupQuery, module: DefinitionModule = 'equipment') => request<Blob>(`${definitionApiPath(module)}/export`, 'POST', query, undefined, true),
  saveEquipmentGroups: (data: EquipmentGroupSubmission) => request<{ count: number }>('/quality/equipment/ledger/group-associations', 'POST', data),
  saveEquipment: (draft: EquipmentDraft & { attachmentDraftId?: string; version?: number }, id?: string) => request<EquipmentRecord>(id ? `/quality/equipment/ledger/${encodeURIComponent(id)}/save` : '/quality/equipment/ledger/save', 'POST', draft),
  exportEquipmentLedger: (query: EquipmentLedgerQuery, departmentMode = false) => request<Blob>(`/quality/equipment/${departmentMode ? 'department-ledger' : 'ledger'}/export`, 'POST', query, undefined, true),
  certificateOptions: (signal?: AbortSignal) => request<CertificateOptions>('/quality/certificates/options', 'GET', undefined, signal),
  certificateList: (kind: CertificateListKind, query: CertificateQuery, signal?: AbortSignal) => request<CertificatePage>(`/quality/certificates/${kind}/query`, 'POST', query, signal),
  exportCertificateList: (kind: CertificateListKind, query: CertificateQuery) => request<Blob>(`/quality/certificates/${kind}/export`, 'POST', query, undefined, true),
  certificateDetail: (id: string, signal?: AbortSignal) => request<CertificateDetail>(`/quality/certificates/certificates/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  approvedProjectDetail: (id: string, signal?: AbortSignal) => request<ApprovedProjectDetail>(`/quality/certificates/projects/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  saveCertificate: (data: object, id?: string) => request<CertificateDetail>(id ? `/quality/certificates/certificates/${encodeURIComponent(id)}/save` : '/quality/certificates/certificates', 'POST', data),
  saveApprovedProjects: (data: object, id?: string) => request<{ count: number }>(id ? `/quality/certificates/projects/${encodeURIComponent(id)}/save` : '/quality/certificates/projects', 'POST', data),
  deleteCertificateRecord: (kind: 'certificates' | 'projects', id: string, data: object) => request(`/quality/certificates/${kind}/${encodeURIComponent(id)}/delete`, 'POST', data),
  certificateFile: (id: string, fileId: string) => request<Blob>(`/quality/certificates/certificates/${encodeURIComponent(id)}/files/${encodeURIComponent(fileId)}`, 'GET', undefined, undefined, true),
  uploadDraftAttachment: (id: string, scope: 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request', recordId: string, file: DemoAttachment, progress: TransferProgress, signal: AbortSignal) => request<DemoAttachment>(`/attachment-drafts/${encodeURIComponent(id)}/upload`, 'POST', { scope, recordId, file }, signal, false, progress),
  draftAttachmentFile: (id: string, scope: 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request', recordId: string, fileId: string) => request<Blob>(`/attachment-drafts/${encodeURIComponent(id)}/file`, 'POST', { scope, recordId, fileId }, undefined, true),
  discardAttachmentDraft: (id: string, scope: 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request', recordId: string) => request(`/attachment-drafts/${encodeURIComponent(id)}/discard`, 'POST', { scope, recordId }),
  removeDraftAttachment: (id: string, scope: 'personnel' | 'external' | 'certificate' | 'equipment' | 'document' | 'monitoring-document' | 'daily-request', recordId: string, fileId: string) => request(`/attachment-drafts/${encodeURIComponent(id)}/remove`, 'POST', { scope, recordId, fileId }),
  personnelUsers: (query: { account: string; name: string; certificateNumber: string; page: number; pageSize: number }, signal?: AbortSignal) => request<EntryPeoplePage>('/quality/personnel/users/query', 'POST', query, signal),
  personnelUser: (id: string, signal?: AbortSignal) => request<EntryPersonCandidate>('/quality/personnel/users/validate', 'POST', { id }, signal),
  personnel: (query: PersonnelQuery, signal?: AbortSignal) => request<PersonnelPage>('/quality/personnel/query', 'POST', query, signal),
  personnelDetail: (id: string, signal?: AbortSignal) => request<PersonnelRecord>(`/quality/personnel/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  savePersonnel: (draft: PersonnelDraft & { version?: number; attachmentDraftId?: string }, id?: string, progress?: TransferProgress) => request<PersonnelRecord>(id ? `/quality/personnel/${encodeURIComponent(id)}/save` : '/quality/personnel', 'POST', draft, undefined, false, progress),
  deletePersonnel: (id: string, version: number) => request(`/quality/personnel/${encodeURIComponent(id)}/delete`, 'POST', { version }),
  importPersonnel: (csv: string) => request<{ count: number }>('/quality/personnel/import', 'POST', { csv }),
  personnelTemplate: () => request<Blob>('/quality/personnel/template', 'GET', undefined, undefined, true),
  exportPersonnel: (query: PersonnelQuery) => request<Blob>('/quality/personnel/export', 'POST', query, undefined, true),
  reportChanges: (query: ReportChangeQuery, signal?: AbortSignal, source: ReportChangeSource = 'internal') => request<ReportChangePage>(`/reports/${source}-changes/query`, 'POST', query, signal),
  reportChangeCandidates: (query: ReportChangeCandidateQuery, signal?: AbortSignal, source: ReportChangeSource = 'internal') => request<ReportChangeCandidate[]>(`/reports/${source}-changes/candidates`, 'POST', query, signal),
  reportChangeDetail: (id: string, signal?: AbortSignal, source: ReportChangeSource = 'internal') => request<ReportChangeRow>(`/reports/${source}-changes/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  saveReportChange: (draft: ReportChangeDraft & { version?: number; intent?: 'save' | 'submit'; attachmentDraftId?: string }, id?: string, source: ReportChangeSource = 'internal', progress?: TransferProgress) => request<ReportChangeRow>(id ? `/reports/${source}-changes/${encodeURIComponent(id)}/save` : `/reports/${source}-changes`, 'POST', draft, undefined, false, progress),
  reportChangeAction: (id: string, version: number, action: 'withdraw' | 'delete', reason: string, source: ReportChangeSource = 'internal') => request<ReportChangeRow>(`/reports/${source}-changes/${encodeURIComponent(id)}/action`, 'POST', { version, action, reason }),
  exportReportChanges: (query: ReportChangeQuery, source: ReportChangeSource = 'internal') => request<Blob>(`/reports/${source}-changes/export`, 'POST', query, undefined, true),
  reportChangeHandlers: (query: EntryPeopleQuery, signal?: AbortSignal, source: ReportChangeSource = 'external') => request<EntryPeoplePage>(`/reports/${source}-changes/handlers/query`, 'POST', query, signal),
  reportChangeHandler: (id: string, signal?: AbortSignal, source: ReportChangeSource = 'external') => request<EntryPersonCandidate>(`/reports/${source}-changes/handlers/validate`, 'POST', { id }, signal),
  reportQuerySamples: (query: ReportQueryQuery, signal?: AbortSignal) => request<ReportQueryPage>('/reports/query/list', 'POST', query, signal),
  exportReportQuerySamples: (query: ReportQueryQuery) => request<Blob>('/reports/query/export', 'POST', query, undefined, true),
  reportQueryVoid: (id: string, version: number, reason: string) => request(`/reports/query/${encodeURIComponent(id)}/void`, 'POST', { version, reason }),
  reportQueryFile: (id: string, releaseId: string, signal?: AbortSignal) => request<Blob>(`/reports/query/${encodeURIComponent(id)}/file`, 'POST', { releaseId }, signal, true),
  reportLifecycle: (query: ReportLifecycleQuery, signal?: AbortSignal) => request<ReportLifecyclePage>('/reports/lifecycle/query', 'POST', query, signal),
  reportPrintSamples: (query: ReportPrintQuery, signal?: AbortSignal) => request<ReportPrintPage>('/reports/lifecycle/print-query', 'POST', query, signal),
  exportReportPrintSamples: (query: ReportPrintQuery) => request<Blob>('/reports/lifecycle/print-export', 'POST', query, undefined, true),
  reportSigningSamples: (query: ReportPrintQuery, signal?: AbortSignal) => request<ReportPrintPage>('/reports/lifecycle/signing-query', 'POST', query, signal),
  exportReportSigningSamples: (query: ReportPrintQuery) => request<Blob>('/reports/lifecycle/signing-export', 'POST', query, undefined, true),
  reportDistributionSamples: (query: ReportPrintQuery, signal?: AbortSignal) => request<ReportPrintPage>('/reports/lifecycle/distribution-query', 'POST', query, signal),
  exportReportDistributionSamples: (query: ReportPrintQuery) => request<Blob>('/reports/lifecycle/distribution-export', 'POST', query, undefined, true),
  reportArchiveSamples: (query: ReportPrintQuery, signal?: AbortSignal) => request<ReportPrintPage>('/reports/lifecycle/archive-query', 'POST', query, signal),
  exportReportArchiveSamples: (query: ReportPrintQuery) => request<Blob>('/reports/lifecycle/archive-export', 'POST', query, undefined, true),
  reportDistributionDetail: (id: string, version: number, releaseId: string, signal?: AbortSignal) => request<ReportDistributionDetail>(`/reports/lifecycle/${encodeURIComponent(id)}/distribution-detail`, 'POST', { version, releaseId }, signal),
  reportPricingDetail: (id: string, version: number, releaseId: string, signal?: AbortSignal) => request<ReportPricingDetail>(`/reports/lifecycle/${encodeURIComponent(id)}/pricing-detail`, 'POST', { version, releaseId }, signal),
  reportLifecycleAction: (id: string, input: Record<string, unknown>) => request<ReportLifecycleRow>(`/reports/lifecycle/${encodeURIComponent(id)}/action`, 'POST', input),
  reportLifecycleFile: (id: string, releaseId: string, operation: 'preview' | 'print' | 'download' | 'print-report', signal?: AbortSignal) => request<Blob>(`/reports/lifecycle/${encodeURIComponent(id)}/file`, 'POST', { releaseId, operation }, signal, true),
  reportSigningProgress: (id: string, signal?: AbortSignal) => request<Pick<ReportRelease, 'id' | 'revision' | 'form' | 'signing' | 'history' | 'receipt'> & { simulated: boolean }>(`/reports/lifecycle/${encodeURIComponent(id)}/progress`, 'GET', undefined, signal),
  sampleCopySamples: (query: SampleCopyQuery, signal?: AbortSignal) => request<SampleCopyPage>('/samples/sample-copy/query', 'POST', query, signal),
  exportSampleCopySamples: (query: SampleCopyQuery) => request<Blob>('/samples/sample-copy/export', 'POST', query, undefined, true),
  dataCheckSamples: (query: DataCheckQuery, signal?: AbortSignal) => request<DataCheckPage>('/samples/data-check/query', 'POST', query, signal),
  reportCheckSamples: (query: ReportCheckQuery, signal?: AbortSignal, stage: ReportStage = 'check') => request<ReportCheckPage>('/samples/report-check/query', 'POST', { ...query, stage }, signal),
  exportReportCheckSamples: (query: ReportCheckQuery, stage: ReportStage = 'check') => request<Blob>('/samples/report-check/export', 'POST', { ...query, stage }, undefined, true),
  reportCheckRecipients: (id: string, query: EntryPeopleQuery, signal?: AbortSignal, stage: ReportStage = 'check') => request<EntryPeoplePage>(`/samples/${encodeURIComponent(id)}/report-check-recipients/query`, 'POST', { ...query, stage }, signal),
  reportCheckRecipient: (id: string, recipientId: string, signal?: AbortSignal, stage: ReportStage = 'check') => request<EntryPersonCandidate>(`/samples/${encodeURIComponent(id)}/report-check-recipients/resolve`, 'POST', { id: recipientId, stage }, signal),
  reportComplianceCheck: (id: string, version: number, signal?: AbortSignal, stage: ReportStage = 'check') => request<ReviewCheckResult>(`/samples/${encodeURIComponent(id)}/report-compliance-check`, 'POST', { version, stage }, signal),
  reportCheckAction: (id: string, action: 'check' | 'reject' | 'undo', version: number, confirmation?: ReportCheckConfirmation, rejection?: ReportCheckRejection, stage: ReportStage = 'check') => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/report-check-action`, 'POST', { action, version, confirmation, rejection, stage }),
  exportDataCheckSamples: (query: DataCheckQuery) => request<Blob>('/samples/data-check/export', 'POST', query, undefined, true),
  dataCheckAction: (id: string, action: 'check' | 'reject' | 'undo', version: number) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/data-check-action`, 'POST', { action, version }),
  originals: (id: string) => request<OriginalContext>(`/samples/${encodeURIComponent(id)}/data-entry/original-records`),
  originalElnQuery: (id: string, query: { sampleCode: string; name: string; page: number; pageSize: number }) => request<ElnPage>(`/samples/${encodeURIComponent(id)}/data-entry/original-records/eln/query`, 'POST', query),
  originalAction: (id: string, action: string, data: unknown, progress?: TransferProgress) => request<OriginalContext>(`/samples/${encodeURIComponent(id)}/data-entry/original-records/${action}`, 'POST', data, undefined, false, progress),
  taskProcessingRecords: (id: string, query: TaskProcessingQuery, signal?: AbortSignal) => request<TaskProcessingPage>(`/samples/${encodeURIComponent(id)}/task-processing-records/query`, 'POST', query, signal),
  createTaskProcessingRecord: (id: string, input: TaskProcessingInput) => request<TaskProcessingDetail>(`/samples/${encodeURIComponent(id)}/task-processing-records`, 'POST', input),
  taskProcessingRecord: (id: string, recordId: string, signal?: AbortSignal) => request<TaskProcessingDetail>(`/samples/${encodeURIComponent(id)}/task-processing-records/${encodeURIComponent(recordId)}`, 'GET', undefined, signal),
  taskProcessingAttachments: (id: string, recordId: string, signal?: AbortSignal) => request<TaskProcessingAttachments>(`/samples/${encodeURIComponent(id)}/task-processing-records/${encodeURIComponent(recordId)}/attachments`, 'GET', undefined, signal),
  attachTaskProcessingFile: (id: string, recordId: string, version: number, file: Omit<DemoAttachment, 'id'>, progress?: TransferProgress) => request<TaskProcessingAttachments>(`/samples/${encodeURIComponent(id)}/task-processing-records/${encodeURIComponent(recordId)}/attachments`, 'POST', { version, file }, undefined, false, progress),
  deleteTaskProcessingFile: (id: string, recordId: string, version: number, fileId: string) => request<TaskProcessingAttachments>(`/samples/${encodeURIComponent(id)}/task-processing-records/${encodeURIComponent(recordId)}/attachments/${encodeURIComponent(fileId)}`, 'DELETE', { version }),
  manufacturers: (query: ManufacturerQuery = {}, signal?: AbortSignal) => request<ManufacturerPage>('/manufacturers/query', 'POST', query, signal),
  testBases: (query: TestBasisQuery, signal?: AbortSignal) => request<TestBasisPage>('/test-bases/query', 'POST', query, signal),
  resolveTestBases: (planId: string, ids: string[], englishBookMarks: boolean, signal?: AbortSignal, separators?: string[]) => request<TestBasisSelection>('/test-bases/resolve', 'POST', { planId, ids, englishBookMarks, separators }, signal),
  inboundSamples: (query: InboundQuery, signal?: AbortSignal) => request<InboundPage>('/samples/inbound/query', 'POST', query, signal),
  outboundSamples: (query: InboundQuery, signal?: AbortSignal) => request<InboundPage>('/samples/outbound/query', 'POST', query, signal),
  disposalSamples: (query: DisposalQuery, signal?: AbortSignal) => request<InboundPage>('/samples/disposal/query', 'POST', query, signal),
  sampleCompletionSamples: (query: SampleCompletionQuery, signal?: AbortSignal) => request<SampleCompletionPage>('/samples/sample-completion/query', 'POST', query, signal),
  sampleCompletionAction: (id: string, version: number, submission: SampleCompletionSubmission) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/sample-completion-action`, 'POST', { ...submission, version }),
  exportSampleCompletionSamples: (query: SampleCompletionQuery) => request<Blob>('/samples/sample-completion/export', 'POST', query, undefined, true),
  assignmentAction: (id: string, version: number, submission: AssignmentSubmission) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/assignment-action`, 'POST', { ...submission, version }),
  undoAssignment: (id: string, version: number) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/assignment-action`, 'POST', { action: 'undo', version }),
  autoAssignment: (id: string, version: number) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/assignment-action`, 'POST', { action: 'auto', version }),
  taskPrintContext: (id: string) => request<TaskPrintContext>(`/samples/${encodeURIComponent(id)}/task-print-context`),
  taskPrintSubmit: (id: string, version: number) => request<TaskPrintJob>(`/samples/${encodeURIComponent(id)}/task-prints`, 'POST', { version }),
  taskPrintHistory: (id: string, page = 1, pageSize = 5) => request<RegistrationPage<TaskPrintJob>>(`/samples/${encodeURIComponent(id)}/task-prints?page=${page}&pageSize=${pageSize}`),
  taskPrintJob: (id: string, task: string) => request<TaskPrintJob>(`/samples/${encodeURIComponent(id)}/task-prints/${encodeURIComponent(task)}`),
  taskPrintPdf: (id: string, task: string) => request<Blob>(`/samples/${encodeURIComponent(id)}/task-prints/${encodeURIComponent(task)}/pdf`, 'GET', undefined, undefined, true),
  entryPeople: (id: string, query: EntryPeopleQuery, signal?: AbortSignal) => request<EntryPeoplePage>(`/samples/${encodeURIComponent(id)}/data-entry/people/query`, 'POST', query, signal),
  entryPerson: (id: string, data: { role: EntryPersonRole; id: string; excludeId?: string }, signal?: AbortSignal) => request<EntryPersonCandidate>(`/samples/${encodeURIComponent(id)}/data-entry/people/validate`, 'POST', data, signal),
  entryDetail: (id: string) => request<EntryDetail>(`/samples/${encodeURIComponent(id)}/data-entry`),
  entryRecords: (id: string, query: EntryRecordsQuery, signal?: AbortSignal) => request<EntryRecordsPage>(`/samples/${encodeURIComponent(id)}/data-entry/records/query`, 'POST', query, signal),
  entryAction: (id: string, action: string, data: unknown, progress?: TransferProgress) => request<EntryDetail>(`/samples/${encodeURIComponent(id)}/data-entry/${action}`, 'POST', data, undefined, false, progress),
  entryDownload: (id: string, target: string) => request<Blob>(`/samples/${encodeURIComponent(id)}/data-entry/${target}`, 'GET', undefined, undefined, true),
  dataQuerySamples: (query: DataQueryQuery, signal?: AbortSignal) => request<DataQueryPage>('/samples/data-query/query', 'POST', query, signal),
  exportDataQuerySamples: (query: DataQueryQuery) => request<Blob>('/samples/data-query/export', 'POST', query, undefined, true),
  dataEntrySamples: (query: DataEntryQuery, signal?: AbortSignal) => request<DataEntryPage>('/samples/data-entry/query', 'POST', query, signal),
  exportDataEntrySamples: (query: DataEntryQuery) => request<Blob>('/samples/data-entry/export', 'POST', query, undefined, true),
  taskQuerySamples: (query: TaskQuery, signal?: AbortSignal) => request<TaskQueryPage>('/samples/task-query/query', 'POST', query, signal),
  taskQueryReturn: (id: string, version: number, returned: OutboundReturn) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/task-return`, 'POST', { version, returned }),
  exportTaskQuerySamples: (query: TaskQuery) => request<Blob>('/samples/task-query/export', 'POST', query, undefined, true),
  pickupSamples: (query: PickupQuery, signal?: AbortSignal) => request<PickupPage>('/samples/pickup/query', 'POST', query, signal),
  pickupAction: (id: string, version: number, receipt: PickupReceipt) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/pickup-action`, 'POST', { version, receipt }),
  exportPickupSamples: (query: PickupQuery) => request<Blob>('/samples/pickup/export', 'POST', query, undefined, true),
  assignmentSamples: (query: AssignmentQuery, signal?: AbortSignal) => request<AssignmentPage>('/samples/assignment/query', 'POST', query, signal),
  exportAssignmentSamples: (query: AssignmentQuery) => request<Blob>('/samples/assignment/export', 'POST', query, undefined, true),
  flowSamples: (query: FlowQuery, signal?: AbortSignal) => request<FlowPage>('/samples/flow/query', 'POST', query, signal),
  exportFlowSamples: (query: FlowQuery) => request<Blob>('/samples/flow/export', 'POST', query, undefined, true),
  disposalAction: (id: string, version: number, submission: DisposalSubmission) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/disposal-action`, 'POST', { ...submission, version }),
  exportDisposalSamples: (query: DisposalQuery) => request<Blob>('/samples/disposal/export', 'POST', query, undefined, true),
  outboundAction: (id: string, version: number, submission: OutboundSubmission) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/outbound-action`, 'POST', { ...submission, version }),
  exportOutboundSamples: (query: InboundQuery) => request<Blob>('/samples/outbound/export', 'POST', query, undefined, true),
  inboundAction: (id: string, action: InboundAction, version: number, receipt?: InboundReceipt) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/inbound-action`, 'POST', { action, version, ...(action === 'receive' ? { receipt } : {}) }),
  exportInboundSamples: (query: InboundQuery) => request<Blob>('/samples/inbound/export', 'POST', query, undefined, true),
  testPlanSelection: (selection: PlanSelection, toggle?: PlanSelectionToggle, signal?: AbortSignal, sampleScope?: 'inbound' | 'outbound' | 'disposal' | 'flow' | 'assignment' | 'pickup' | 'task-query' | 'data-entry' | 'data-check' | 'sample-copy' | 'data-changes' | 'report-check' | 'report-review' | 'report-approval' | 'report-print' | 'report-signing' | 'report-distribution' | 'report-archive' | 'report-query') => request<PlanSelectionContext>('/test-plans/selection', 'POST', { selection, toggle, sampleScope }, signal),
  testPlans: (query: TestPlanQuery = {}, signal?: AbortSignal) => request<RegistrationPage<TestPlanNode>>('/test-plans/query', 'POST', query, signal),
  reportSettingsConfig: (signal?: AbortSignal) => request<ReportSettingsConfig>('/samples/report-settings-config', 'GET', undefined, signal),
  sampleDefaults: () => request<SampleFormOptions>('/samples/defaults'),
  copySample: (id: string, input: SampleCopyInput) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/copy`, 'POST', input),
  commissionDefaults: () => request<{ commissionDate: string }>('/commissions/defaults'),
  printContext: (kind: RegistrationKind, id: string) => request<PrintContext>(`/${kind}/${encodeURIComponent(id)}/print-context`),
  printSubmit: (kind: RegistrationKind, id: string, input: PrintRequest) => request<PrintTask>(`/${kind}/${encodeURIComponent(id)}/prints`, 'POST', input),
  printHistory: (kind: RegistrationKind, id: string, page = 1, pageSize = 5) => request<RegistrationPage<PrintTask>>(`/${kind}/${encodeURIComponent(id)}/prints?page=${page}&pageSize=${pageSize}`),
  printTask: (kind: RegistrationKind, id: string, task: string) => request<PrintTask>(`/${kind}/${encodeURIComponent(id)}/prints/${encodeURIComponent(task)}`),
  printPdf: (kind: RegistrationKind, id: string, task: string) => request<Blob>(`/${kind}/${encodeURIComponent(id)}/prints/${encodeURIComponent(task)}/pdf`, 'GET', undefined, undefined, true),
  organizations: (query: RegistrationOrganizationQuery = {}, signal?: AbortSignal) => request<RegistrationPage<RegistrationOrganization>>('/organizations/query', 'POST', query, signal),
  contracts: (query: RegistrationContractQuery = {}, signal?: AbortSignal) => request<RegistrationPage<RegistrationContract>>('/contracts/query', 'POST', query, signal),
  cancellationApprovals: (query: CancellationQuery = {}, signal?: AbortSignal) => request<RegistrationPage<CancellationRow>>('/samples/cancellation-approvals/query', 'POST', query, signal),
  exportCancellationApprovals: (query: CancellationQuery) => request<Blob>('/samples/cancellation-approvals/export', 'POST', query, undefined, true),
  approveCancellation: (id: string, input: CancellationSubmission) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/cancellation-approval`, 'POST', input),
  dataChanges: (query: DataChangeQuery = {}, signal?: AbortSignal) => request<DataChangePage>('/samples/data-changes/query', 'POST', query, signal),
  exportDataChanges: (query: DataChangeQuery) => request<Blob>('/samples/data-changes/export', 'POST', query, undefined, true),
  completeDataChange: (id: string, version: number, acknowledgeMissingOriginals = false) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/complete-data-change`, 'POST', { version, acknowledgeMissingOriginals }),
  sampleChanges: (query: CommissionChangeQuery = {}, signal?: AbortSignal) => request<RegistrationPage<CommissionChangeRow>>('/samples/changes/query', 'POST', query, signal),
  exportSampleChanges: (query: CommissionChangeQuery) => request<Blob>('/samples/changes/export', 'POST', query, undefined, true),
  commissions: (query: RegistrationQuery = {}, signal?: AbortSignal) => request<RegistrationPage<RegistrationCommissionRow>>('/commissions/query', 'POST', query, signal),
  samples: (query: RegistrationQuery = {}, signal?: AbortSignal, workspace?: RegistrationWorkspace) => request<RegistrationPage<RegistrationSampleRow>>('/samples/query', 'POST', { ...query, ...workflow(workspace) }, signal),
  commission: (id: string, signal?: AbortSignal) => request<RegistrationCommission>(`/commissions/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  commissionSummary: (id: string, signal?: AbortSignal) => request<RegistrationCommissionRow>(`/commissions/${encodeURIComponent(id)}/summary`, 'GET', undefined, signal),
  sample: (id: string, signal?: AbortSignal) => request<RegistrationSample & { commissionCode: string; commissionName: string }>(`/samples/${encodeURIComponent(id)}`, 'GET', undefined, signal),
  saveCommission: (input: RegistrationCommissionInput, id?: string, version?: number, workspace?: RegistrationWorkspace) => request<RegistrationCommission>(`/commissions${id ? '/' + encodeURIComponent(id) : ''}`, id ? 'PUT' : 'POST', { input, version, ...workflow(workspace) }),
  saveSample: (input: RegistrationSampleInput, id?: string, version?: number, reportConfigVersion?: string, workspace?: RegistrationWorkspace) => request<RegistrationSample>(`/samples${id ? '/' + encodeURIComponent(id) : ''}`, id ? 'PUT' : 'POST', { input, version, reportConfigVersion, ...workflow(workspace) }),
  bulkCommissionContext: (ids: string[], workspace?: RegistrationWorkspace) => request<BulkCommissionContext>('/samples/bulk-commission/context', 'POST', { ids, ...workflow(workspace) }),
  bulkCommissionSource: (ids: string[], workspace?: RegistrationWorkspace) => request<SampleCommissionInfo>('/samples/bulk-commission/source', 'POST', { ids, ...workflow(workspace) }),
  saveBulkCommission: (targets: BulkCommissionTarget[], changes: Record<string, string>, workspace?: RegistrationWorkspace) => request<BulkCommissionResult>('/samples/bulk-commission', 'POST', { targets, changes, ...workflow(workspace) }),
  reviewCheck: (id: string, version: number, reviewOptions: ReviewCheckOptions, signal?: AbortSignal) => request<ReviewCheckResult>(`/samples/${encodeURIComponent(id)}/review-check`, 'POST', { version, reviewOptions }, signal),
  startBatchReview: (targets: BatchReviewTarget[]) => request<RegistrationSample[]>('/samples/batch-review/start', 'POST', { targets }),
  batchReviewContext: (ids: string[]) => request<RegistrationSample[]>('/samples/batch-review/context', 'POST', { ids }),
  reportBatchContext: (ids: string[], stage: ReportStage, signal?: AbortSignal) => request<RegistrationSample[]>('/samples/report-batch/context', 'POST', { ids, stage }, signal),
  reportBatchCheck: (targets: BatchReviewTarget[], stage: ReportStage, signal?: AbortSignal) => request<BatchReviewCheckResponse>('/samples/report-batch/check', 'POST', { targets, stage }, signal),
  reportBatchSubmit: (input: ReportBatchSubmission) => request<RegistrationSample[]>('/samples/report-batch/submit', 'POST', input),
  reportVoidAction: (id: string, version: number, reason: string, stage: ReportStage) => request<RegistrationSample>(`/samples/${encodeURIComponent(id)}/report-void-action`, 'POST', { version, reason, stage }),
  batchReviewCheck: (targets: BatchReviewTarget[], reviewOptions: ReviewCheckOptions, signal?: AbortSignal) => request<BatchReviewCheckResponse>('/samples/batch-review/check', 'POST', { targets, reviewOptions }, signal),
  submitBatchReview: (input: BatchReviewSubmission) => request<RegistrationSample[]>('/samples/batch-review/submit', 'POST', input),
  act: (kind: RegistrationKind, id: string, actionId: string, version: number, reason = '', review?: ContractReviewSubmission) => request<RegistrationCommission | RegistrationSample>(`/${kind}/${encodeURIComponent(id)}/actions`, 'POST', { actionId, version, reason, ...(review ? { review } : {}) }),
  export: (kind: RegistrationKind, query: RegistrationQuery, workspace?: RegistrationWorkspace) => request<Blob>(`/${kind}/export`, 'POST', { ...query, ...workflow(workspace) }, undefined, true),
  attachments: (id: string, kind: RegistrationKind, signal?: AbortSignal) => request<RegistrationAttachmentContext>(`/${kind}/${encodeURIComponent(id)}/attachments`, 'GET', undefined, signal),
  attach: (id: string, version: number, file: Omit<DemoAttachment, 'id'>, workspace?: RegistrationWorkspace, progress?: TransferProgress) => request<RegistrationCommission & RegistrationAttachmentContext>(`/commissions/${encodeURIComponent(id)}/attachments`, 'POST', { version, file, ...workflow(workspace) }, undefined, false, progress),
  attachSample: (id: string, version: number, file: Omit<DemoAttachment, 'id'>, workspace?: RegistrationWorkspace, progress?: TransferProgress) => request<RegistrationSample & RegistrationAttachmentContext>(`/samples/${encodeURIComponent(id)}/attachments`, 'POST', { version, file, ...workflow(workspace) }, undefined, false, progress),
  deleteSampleAttachment: (id: string, version: number, attachmentId: string, workspace?: RegistrationWorkspace) => request<RegistrationSample & RegistrationAttachmentContext>(`/samples/${encodeURIComponent(id)}/attachments/${encodeURIComponent(attachmentId)}`, 'DELETE', { version, ...workflow(workspace) }),
  deleteAttachment: (id: string, version: number, attachmentId: string, workspace?: RegistrationWorkspace) => request<RegistrationCommission & RegistrationAttachmentContext>(`/commissions/${encodeURIComponent(id)}/attachments/${encodeURIComponent(attachmentId)}`, 'DELETE', { version, ...workflow(workspace) }),
}
