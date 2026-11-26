import { parseTemplateCapacityWarnings } from '../../platformUi/testing/templateCapacityWarnings'
import { canCorrect, correctForm, rememberCorrection } from './businessCorrection'
// 检测人员新建委托：委托/样品落库后先进入合同评审，再按样品流转进入检测录入。
import { ApiError, authedFetch, request } from './http'
import { AppError } from '../../services/common/errors'
import type { ReportDetailView } from './reports'
import { USE_BACKEND } from './auth'

export const PIPELINE_AVAILABLE = USE_BACKEND

export interface EntrustSnapshot {
  sourceEntrustId?: number
  sourceEntrustNo: string
  entrustNo: string
  contractNo: string
  client: string
  projectName: string
  projectType: string
  amount: string
  department: string
  owner: string
  info: Record<string, string>
}

export interface ReportDetail {
  projectName: string
  summary: { title: string; fields: [string, string][] }[]
  checks: { group: string; status: string; type: 'success' | 'warning' | 'danger'; items: [string, string][] }[]
  attachments: { name: string; type: string; source: string; status: string }[]
  entrustSnapshot?: EntrustSnapshot
  rawSample?: Record<string, unknown>
  sampleRegistrar?: string
  sampleRegistrarAccount?: string
  sampleRegistrarDepartment?: string
}

export interface CreateReportPayload {
  reportNo?: string
  reportNoPrefix?: string
  sampleNo?: string
  project: string
  projectName: string
  client: string
  template?: string
  deadline?: string
  department?: string
  owner?: string
  entrustNo?: string
  detail: ReportDetail
  // 第三类：补充/英文/分项报告——基于原报告派生，继承其信息
  baseReportNo?: string
  reportCategory?: string
  regState?: '登记中' | '登记完成'
}

export function createReport(payload: CreateReportPayload) {
  return request<{ reportNo: string; sampleNo?: string; status: string; editVersion?: number }>('/api/reports/create', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface DerivableReport { reportNo: string; mainReportNo?: string; client: string; projectName: string; sampleNo: string; project: string; status: string }
export interface DerivableReportPage { rows: DerivableReport[]; total: number; page: number; size: number }
export function fetchDerivableReportPage(query: { category: string; keyword: string; page: number; size: number }, signal?: AbortSignal) {
  return request<DerivableReportPage>('/api/reports/derivable', { method: 'POST', body: JSON.stringify(query), signal })
}

// 基础库：标准库 / 检测方案库 / 检测项目库
export interface StdItem { code: string; name: string; qualKind: string; category: string; dept: string }
export function fetchStandards(keyword = '', cmaOnly = false) {
  return request<{ rows: StdItem[] }>('/api/reports/lib/standards', { method: 'POST', body: JSON.stringify({ keyword, cmaOnly }) }).then((d) => d.rows)
}
export interface SchemeRow {
  dept: string
  name: string
  code: string
  numberCode?: string
  project?: string
  testDept?: string
  testRoom?: string
  testBasis?: string
  standardJudge?: string
  defaultCycle?: string
  sealRequirement?: string
  reportTitle?: string
  centerPrefix?: string
  testCategory?: string
  reportType?: string
  reportFormat?: string
  detectionParameters?: string
  sampleAmount?: string
  sampleStatus?: string
  testLocation?: string
  location?: string
}
export interface SchemeNode { dept: string; schemes: SchemeRow[] }
export function fetchSchemes(keyword = '') {
  return request<{ tree: SchemeNode[] }>('/api/reports/lib/schemes', { method: 'POST', body: JSON.stringify({ keyword }) }).then((d) => d.tree)
}
export interface TestItemRow { dept: string; name: string; code: string }
export function fetchTestItems(keyword = '', department = '') {
  return request<{ rows: TestItemRow[] }>('/api/reports/lib/items', {
    method: 'POST',
    body: JSON.stringify({ keyword, department }),
  }).then((d) => d.rows)
}

export interface CapabilityItemRow {
  address?: string
  accreditation?: string
  active?: boolean
  superseded?: boolean
  standardItemId?: number
  sourceStandardCode?: string
  sourceStandardName?: string
  id: number
  batchId: number
  capabilityType: string
  certificateNo: string
  site: string
  sectionPath: string
  objectSeq: string
  objectName: string
  itemSeq: string
  itemName: string
  standardCode: string
  standardName: string
  methodClause: string
  restriction: string
  effectiveDate: string
  expiresOn: string
  sourceFile: string
  sourcePage: number
  mappingStatus: string
  departments: string[]
}

export interface CapabilityQuery {
  locationFilter?: string
  accreditationFilter?: string
  includeLocations?: boolean
  allStandards?: boolean
  onsiteOnly?: boolean
  department?: string
  standardItemId?: number
  standardItemIds?: number[]
  standardCode?: string
  standardCodes?: string[]
  ids?: number[]
  capabilityType?: string
  site?: string
  date?: string
  keyword?: string
  page?: number
  size?: number
}
export function fetchCapabilityPage(payload: CapabilityQuery, signal?: AbortSignal) {
  return request<{ rows: CapabilityItemRow[]; total: number; page: number; size: number; locations?: string[] }>('/api/reports/lib/capability-items', {
    method: 'POST', body: JSON.stringify(payload), signal,
  })
}
export function fetchTestingLocations(signal?: AbortSignal) {
  return request<{ rows: string[] }>('/api/reports/lib/testing-locations', { signal }).then(result => result.rows)
}
export function fetchCapabilityItems(payload: CapabilityQuery, signal?: AbortSignal) {
  return fetchCapabilityPage(payload, signal).then(d => d.rows)
}

export interface ComplianceIssue {
  level?: 'block' | 'confirm' | 'notice'
  code?: string
  id: string
  category: string
  title: string
  message: string
  evidence: Record<string, unknown>
  effect: string
  hardBlocker: boolean
  acknowledgeable: boolean
}

export interface CompliancePreflight {
  standardChoices?: {code:string;candidates:{id:number;code:string;name:string;department:string;implementationDate:string;marks:string}[]}[]
  required: boolean
  stage: 'contract_review' | 'report_review' | 'report_approval'
  preflightVersion: string
  requestedSeal: string
  finalSeal: string
  issues: ComplianceIssue[]
  hardBlockers: ComplianceIssue[]
  requiresOpinion: boolean
  ready: boolean
}

export async function fetchCompliancePreflight(
  reportNo: string,
  stage: CompliancePreflight['stage'],
) {
  const res = await authedFetch(
    `/api/reports/${encodeURIComponent(reportNo)}/compliance-preflight?stage=${encodeURIComponent(stage)}`,
  )
  const body = await res.json()
  if (body.code !== 0) throw new Error(body.message || '合规预检失败')
  return body.data as CompliancePreflight
}

export interface ComplianceConfirmation {
  preflightVersion?: string
  acknowledgedIssueIds?: string[]
  complianceOpinion?: string
  finalSeal?: string
}

export interface SampleConfigurationResult {
  ready: boolean
  errors: string[]
  warnings: string[]
  requiredCma: boolean
  requiredCnas: boolean
  standard?: Record<string, unknown> | null
  scheme?: SchemeRow | null
}

export function validateSampleConfiguration(payload: {
  schemeCode: string
  department: string
  project: string
  testRoom: string
  testBasis: string
  testBases?: string[]
  standardItemIds?: number[]
  standardJudge: string
  seal: string
}) {
  return request<SampleConfigurationResult>('/api/reports/lib/validate-sample', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// 样品录入阶段预览报告封面+首页：优先返回真实模板填好后的 PDF（网页内 iframe 直接看），
// 服务器无 LibreOffice 时回退 HTML。
// 对已存在报告取真实模板：默认封面+首页；样品登记可单独预览封面或首页
export type ReportCoverPart = 'all' | 'cover' | 'homepage'
export async function fetchReportCover(reportNo: string, view: ReportDetailView, format: 'pdf' | 'docx' = 'pdf', part: ReportCoverPart = 'all'): Promise<CoverPreview | { type: 'docx'; url: string; name: string }> {
  const params = new URLSearchParams({ format, view })
  if (part !== 'all') params.set('part', part)
  const label = part === 'cover' ? '报告封面' : part === 'homepage' ? '报告首页' : '封面首页'
  const res = await authedFetch(`/api/reports/${encodeURIComponent(reportNo)}/cover?${params}`, { method: 'GET' })
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('pdf')) return { type: 'pdf', url: URL.createObjectURL(await res.blob()) }
  if (ct.includes('wordprocessingml')) return { type: 'docx', url: URL.createObjectURL(await res.blob()), name: `${reportNo}-${label}.docx` }
  if (!ct.includes('json')) throw new Error(`生成${label}失败（服务 ${res.status}）`)
  const j = await res.json()
  if (j.code !== 0) throw new Error(j.message || `生成${label}失败`)
  return { type: 'html', html: j.data.html }
}

export type CoverPreview = { type: 'pdf'; url: string } | { type: 'html'; html: string }
export async function previewCover(payload: Record<string, unknown>): Promise<CoverPreview> {
  const res = await authedFetch('/api/reports/cover-preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('pdf')) return { type: 'pdf', url: URL.createObjectURL(await res.blob()) }
  const j = await res.json()
  if (j.code !== 0) throw new Error(j.message || '封面预览失败')
  return { type: 'html', html: j.data.html }
}

// 客户（单位）库——与销售易客户库联动，供委托「合同甲方/付款方/委托单位」下拉
export interface Customer {
  code: string
  name: string
  type?: string
  dept?: string
  owner?: string
  industry?: string
  addr?: string
  legal?: string
  phone?: string
  zip?: string
}
export function searchCustomers(keyword: string) {
  return request<{ rows: Customer[] }>(`/api/customers/search?keyword=${encodeURIComponent(keyword)}`).then((d) => d.rows)
}

export interface ErpContract {
  sourceFieldSummary?: string
  contractStartDate?: string
  erpLogReceivedAt?: string
  contractNo: string
  client: string
  projectName: string
  projectAddr: string
  contact: string
  phone: string
  amount: string
  category: string
  erpType?: string
  bizDept?: string
  owner?: string
  auditTime?: string
}

export async function fetchErpContracts() {
  const erp = await request<{ rows: ErpContract[] }>('/api/erp/contracts').then((d) => d.rows)
  // 合并客户协议维护「已登记」推送的合同库（流程图 #2 终点）
  let library: ErpContract[] = []
  try {
    library = await request<{ rows: ErpContract[] }>('/api/agreements/contract-library').then((d) => d.rows)
  } catch {
    library = []
  }
  const seen = new Set(erp.map((c) => c.contractNo))
  return [...erp, ...library.filter((c) => !seen.has(c.contractNo))]
}

export interface SamplePickup {
  managerId?: string
  managerName?: string
  outTime?: string
  receiverName?: string
  pickupTime?: string
  signed?: boolean
  returnNote?: string
}

export interface SampleRow {
  entrustDate?: string
  archiveState?: string
  inboundPerson?: string
  inboundTime?: string
  pickupPerson?: string
  pickupTime?: string
  sampleDisposition?: string
  sampleNo: string
  reportNo: string
  entrustNo?: string
  status?: string
  voided?: boolean
  sampleRegState?: string
  dataStatus?: string
  project: string
  client: string
  projectName: string
  sampleStatus: string
  dataEntryStarted?: boolean
  samplePickup?: SamplePickup | null
  department: string
  owner: string
  erpProjectNo?: string
  erpProjectType?: string
  erpContractNo?: string
  handler?: string
  handlerDepartment?: string
  registrar?: string
  registrarDepartment?: string
  completionAccount?: string
  completionUserName?: string
  sampleOrProjectName?: string
  testItems?: string
  testDepartment?: string
  schemeName?: string
  schemeCode?: string
  schemeDisplay?: string
  amount?: string
  reportCategory?: string
  reportFormat?: string
  testCategory?: string
  sampleRegisteredAt?: string
  sendDate?: string
  reportTitle?: string
  sealRequirement?: string
  samplingUnit?: string
  sampler?: string
  samplingTime?: string
  consignor?: string
  consignorPhone?: string
  clientAddress?: string
  reviewer?: string
  reviewedAt?: string
  sampleRegistrationCompletionAccount?: string
  sampleRegistrationCompletionUserName?: string
  canRecallSampleRegistration?: boolean
  canReturnStock?: boolean
  returnStockBlockedReason?: string
  canRecallSampleOutbound?: boolean
  canUndoSampleInbound?: boolean
  sampleOutboundRecallReason?: string
}

export type SampleListView = 'register' | 'inbound' | 'outbound' | 'flow_query'

export function fetchSamples(view: SampleListView = 'flow_query', includeVoided = false) {
  return request<{ rows: SampleRow[] }>('/api/samples/query', {
    method: 'POST',
    body: JSON.stringify({ view, ...(includeVoided ? { includeVoided: true } : {}) }),
  }).then((d) => d.rows)
}

export interface TestInfoPayload {
  testEditVersion?: string
  standard: string
  standards?: string[]
  validateForCompletion?: boolean
  instrument?: string
  testStartDate?: string
  testEndDate?: string
  testIntervals?: Array<{ start: string; end: string }>
  equipmentIds?: number[]
  equipmentDisplay?: {
    archiveNo: boolean
    spec: boolean
    maker: boolean
    factoryNo: boolean
  }
  standardTitleStyles?: Record<string, 'CN' | 'EN' | 'none'>
  judgmentDisplay?: {standardShowName?: boolean; standardTitleStyles?: Record<string, 'CN' | 'EN' | 'none'>; standardSeparatorText?: string}
  standardNames?: Record<string, string>
  standardSeparatorText?: string
  equipmentSeparatorText?: string
  standardShowName?: boolean
  standardSeparator?: 'newline' | 'semicolon' | 'space'
  calibrationTime?: string
  calibrationPlace?: string
  temperature?: string
  humidity?: string
  pressure?: string
  primaryTester1Code?: string
  primaryTester2Code?: string
  reviewerCode?: string
  approverCode?: string
  owner?: string
  conclusion?: string
  resultStatus?: string
  unqualifiedParams?: string
  recordNo?: string
  result?: string
  assignedReviewer?: string
  assignedApprover?: string
  remark?: string
}

export interface AuthorizedReportPerson {
  id: number
  code: string
  name: string
  department: string
  title?: string
  position?: string
}

export interface AuthorizedReportPeople {
  project: {
    id: number
    code: string
    name: string
  }
  testers: AuthorizedReportPerson[]
  originalRecordReviewers: AuthorizedReportPerson[]
  reviewers: AuthorizedReportPerson[]
  approvers: AuthorizedReportPerson[]
}

export function fetchAuthorizedReportPeople(reportNo: string) {
  return request<AuthorizedReportPeople>(`/api/reports/${reportNo}/authorized-people`, {cache:'no-store'})
}

export function fetchEntryReferences(reportNo: string) {
  return request<Record<string, unknown>>(`/api/reports/${encodeURIComponent(reportNo)}/entry-references`, {cache:'no-store'})
}

export function updateTestInfo(reportNo: string, payload: TestInfoPayload, administratorEditing = false) {
  if (administratorEditing && canCorrect()) return correctForm<{ checks: unknown[]; draft?: boolean; testEditVersion?: string; notice?: string }>('reports', reportNo, payload, `/api/reports/${encodeURIComponent(reportNo)}/testinfo`)
  return request<{ checks: unknown[]; draft?: boolean; testEditVersion?: string; notice?: string }>(`/api/reports/${reportNo}/testinfo`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }, 30_000)
}

export type EsignWorkflow = 'legacy' | 'business_stages_v1'

interface TestCompletionResult {
  status: string
  esignPending?: boolean
  esignWorkflowRequired?: boolean
  esignPrepareError?: string
  message?: string
}

export class TestCompletionUncertain extends Error {}

async function submitTestCompletion(reportNo: string, action: 'testinfo-complete' | 'change-test-complete', body: object) {
  try {
    return await request<TestCompletionResult>(`/api/reports/${encodeURIComponent(reportNo)}/${action}`, {
      method: 'POST', body: JSON.stringify(body),
    }, 60_000)
  } catch (error) {
    if ((error instanceof AppError && error.code === 'NETWORK') ||
        (error instanceof ApiError && error.status >= 500) || error instanceof SyntaxError) {
      throw new TestCompletionUncertain('检测数据已保存。完成请求未收到回执，正在核对服务器状态。', { cause: error })
    }
    throw error
  }
}

export function completeTestInfo(reportNo: string, signingWorkflow?: EsignWorkflow) {
  return submitTestCompletion(reportNo, 'testinfo-complete', { signingWorkflow })
}

export function readTestCompletion(reportNo: string, view: 'data_entry' | 'data_change') {
  return request<{ status: string; esignPending: boolean; stillEditable: boolean }>(
    `/api/reports/${encodeURIComponent(reportNo)}/testinfo-completion-state?view=${view}`, { cache: 'no-store' },
  )
}

export interface ContractReviewPayload {
  action: 'pass' | 'return'
  items: Record<string, boolean>
  cma: boolean
  cnas: boolean
  opinion: string
  preflightVersion?: string
  acknowledgedIssueIds?: string[]
  complianceOpinion?: string
  finalSeal?: string
}

export function submitContractReview(reportNo: string, payload: ContractReviewPayload) {
  return request<{ reportNo: string; status: string; dataStatus?: string }>(`/api/reports/${reportNo}/contract-review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface SamplePickupPayload {
  action: 'sign' | 'return'
  managerId?: string
  managerName?: string
  outTime?: string
  receiverName?: string
  pickupTime?: string
  returnNote?: string
}

export function submitSamplePickup(reportNo: string, payload: SamplePickupPayload) {
  return request<{ reportNo: string; sampleStatus: string }>(`/api/samples/${reportNo}/pickup`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// 样品入库（手动点一下入库）
export function submitSampleInbound(reportNo: string, inboundDate?: string) {
  return request<{ reportNo: string; sampleStatus: string }>(`/api/samples/${reportNo}/inbound`, {
    method: 'POST',
    body: JSON.stringify(inboundDate === undefined ? {} : { inboundDate }),
  })
}

export function undoSampleInbound(reportNo: string) {
  return request(`/api/samples/${encodeURIComponent(reportNo)}/inbound-undo`, {
    method: 'POST', body: JSON.stringify({}),
  })
}

// R6 样品回库（出库领取后检测未完成 → 回到已入库）
export function submitSampleReturnStock(reportNo: string) {
  return request<{ reportNo: string; sampleStatus: string }>(`/api/samples/${reportNo}/return-stock`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

// R6 样品处置（检测完成后处置，终态）
export function submitSampleDispose(reportNo: string) {
  return request<{ reportNo: string; sampleStatus: string }>(`/api/samples/${reportNo}/dispose`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

// R6 样品登记两态：complete 登记完成（进入合同评审待办）/ uncomplete 撤销
export function sampleRegAction(reportNo: string, action: 'complete' | 'uncomplete') {
  return request<Record<string, unknown>>(`/api/reports/${reportNo}/sample-reg`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
}

export function voidSample(reportNo: string) {
  return request<Record<string, unknown>>(`/api/samples/${encodeURIComponent(reportNo)}/void`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

// 报告附加页（报告预览编辑）
export interface ReportPageItem { title: string; content: string }
export function saveReportPages(reportNo: string, pages: ReportPageItem[]) {
  return request<{ reportNo: string; pages: ReportPageItem[] }>(`/api/reports/${reportNo}/report-pages`, {
    method: 'PUT',
    body: JSON.stringify({ pages }),
  })
}

export interface Agreement {
  editVersion?: number
  contractStartDate?: string
  erpLogReceivedAt?: string
  id?: number
  agreementNo: string
  client: string
  erpType: string
  contractType: string
  projectCode: string
  projectName: string
  category: string
  amount: string
  payment: string
  department: string
  owner: string
  status?: string
  info?: Record<string, string>
  erpProjectNo?: string
  erpProjectType?: string
  projectAuditTime?: string
  businessDepartment?: string
  projectOwner?: string
  registrar?: string
  completionAccount?: string
  completionUserName?: string
  testDepartment?: string
  registeredAt?: string
  remark?: string
}

export function fetchAgreementDetail(id: number) {
  return request<Agreement>(`/api/agreements/${id}`)
}
export function fetchAgreements(params: { keyword?: string; status?: string; projection?: 'list' } = {}) {
  return request<{ rows: Agreement[] }>('/api/agreements/query', {
    method: 'POST',
    body: JSON.stringify(params),
  }).then((d) => d.rows)
}

export function createAgreement(payload: Agreement) {
  return request<Agreement>('/api/agreements/create', { method: 'POST', body: JSON.stringify(payload) }).then(async row => { if (row.id) await rememberCorrection('agreements', row.id).catch(() => undefined); return row })
}

export function updateAgreement(id: number, payload: Agreement) {
  if (canCorrect()) return correctForm<Agreement>('agreements', id, payload)
  return request<Agreement>(`/api/agreements/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function deleteAgreement(id: number) {
  return request<{ agreementNo: string }>(`/api/agreements/${id}`, { method: 'DELETE' })
}

export function completeAgreement(id: number) {
  return request<Agreement>(`/api/agreements/${id}/complete`, { method: 'POST', body: JSON.stringify({}) })
}

export function uncompleteAgreement(id: number) {
  return request<Agreement>(`/api/agreements/${id}/uncomplete`, { method: 'POST', body: JSON.stringify({}) })
}

export interface AgreementDepartment {
  id: number
  name: string
  fullName: string
  leafName: string
  parentId: number | null
  isLeaf: boolean
}

// 委托登记可用部门组织
export function fetchDepartments() {
  return request<{ rows: AgreementDepartment[] }>('/api/entrust/departments').then((d) => d.rows)
}
export function fetchClaimableContracts(): Promise<ErpContract[]> {
  return Promise.resolve([])
}
export function deleteClaimableContract(_contractNo: string): Promise<{ agreementNo: string }> {
  return Promise.resolve({ agreementNo: '' })
}
export function claimContract(_payload: { contractNo: string; department: string }): Promise<Agreement> {
  return Promise.reject(new Error('开源版不包含合同认领功能'))
}
export function fetchClaimedContracts(): Promise<Agreement[]> {
  return Promise.resolve([])
}
export function fetchContractSelectionPage(
  _keyword = '', page = 1, _signal?: AbortSignal, _number = '',
): Promise<{ rows: Agreement[]; total: number; page: number; size: number; scope?: 'all' | 'department' }> {
  return Promise.resolve({ rows: [], total: 0, page, size: 20, scope: 'department' })
}

// 委托单（一单多样品）
export interface EntrustOrder {
  editVersion?: number
  id?: number
  entrustNo: string
  contractNo: string
  client: string
  projectName: string
  projectType: string
  amount: string
  department: string
  owner: string
  status: string
  sampleCount?: number
  date?: string
  info?: Record<string, string>
  dataStatus?: string
  erpProjectNo?: string
  erpProjectType?: string
  completionAccount?: string
  completionUserName?: string
  contractPartyA?: string
  otherPartyA?: string
  entrustDate?: string
  handler?: string
  handlerDepartment?: string
  consignor?: string
  clientAddress?: string
}
export interface CreateEntrustPayload {
  editVersion?: number
  entrustNo?: string
  contractNo: string
  client: string
  projectName: string
  projectType?: string
  amount?: string
  department?: string
  owner?: string
  info?: Record<string, string>
}
export function createEntrust(payload: CreateEntrustPayload) {
  return request<EntrustOrder>('/api/entrust/create', { method: 'POST', body: JSON.stringify(payload) }).then(async row => { if (row.id) await rememberCorrection('entrusts', row.id).catch(() => undefined); return row })
}
// 就地修改委托单（不重走流程）
export function updateEntrust(id: number, payload: CreateEntrustPayload, administratorEditing = canCorrect()) {
  if (administratorEditing && canCorrect()) return correctForm<EntrustOrder>('entrusts', id, payload)
  return request<EntrustOrder>(`/api/entrust/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}
// 完成委托：委托中 → 委托完成
export function completeEntrust(id: number) {
  return request<EntrustOrder>(`/api/entrust/${id}/complete`, { method: 'POST' })
}
// R6 撤销委托登记完成：委托完成 → 委托中（下游已有样品单则被拦截）
export function uncompleteEntrust(id: number) {
  return request<EntrustOrder>(`/api/entrust/${id}/uncomplete`, { method: 'POST' })
}
export type BusinessFormPrint =
  | { type: 'pdf'; url: string; name: string; sourceHash: string; engine: string; expectedPages: number; etag?: string }
  | { type: 'docx'; url: string; name: string; sourceHash: string; expectedPages: number }
export type BusinessFormTemplateKind = 'product' | 'engineering' | 'product-extended' | 'engineering-extended'
export const BUSINESS_FORM_TEMPLATE_OPTIONS: { label: string; value: BusinessFormTemplateKind }[] = [
  { label: '产品类（4204d）', value: 'product' },
  { label: '工程类（4204g）', value: 'engineering' },
  { label: '产品类扩展版（4204d）', value: 'product-extended' },
  { label: '工程类扩展版（4204g）', value: 'engineering-extended' },
]

function responseFilename(response: Response, fallback: string) {
  const disposition = response.headers.get('content-disposition') || ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try { return decodeURIComponent(encoded.replace(/^"|"$/g, '')) } catch { /* use fallback */ }
  }
  return disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallback
}

async function namedObjectUrl(response: Response, fallback: string) {
  const blob = await response.blob()
  const name = responseFilename(response, fallback)
  return { name, url: URL.createObjectURL(new File([blob], name, { type: blob.type })) }
}

export async function awaitBusinessPreview(initial: Response, isCurrent = () => true, onStatus = (_message: string) => {}, etag = '') {
  let response = initial
  for (let attempt = 0; response.status === 202 && attempt < 180; attempt += 1) {
    const body = await response.json()
    if (body.code !== 0 || !body.data?.pollUrl) throw new Error(body.message || '委托单生成失败')
    if (!isCurrent()) throw new Error('已关闭委托单预览；后台任务继续处理')
    const url = String(body.data.pollUrl)
    if (!url.startsWith('/api/samples/entrust-preview-jobs/')) throw new Error('预览任务地址无效')
    onStatus(body.message || '委托单正在后台生成')
    if (body.data.status !== 'ready') await new Promise(resolve => window.setTimeout(resolve, 2000))
    if (!isCurrent()) throw new Error('已关闭委托单预览；后台任务继续处理')
    response = etag ? await authedFetch(url, { headers: { 'If-None-Match': etag } }) : await authedFetch(url)
  }
  if (response.status === 202) throw new Error('委托单仍在后台生成，可关闭窗口稍后重新打开；不会重复转换')
  return response
}

async function fetchBusinessFormPrint(url: string, format: 'pdf' | 'docx', name: string, templateKind: BusinessFormTemplateKind, pages: number[] = [], reusable?: BusinessFormPrint): Promise<BusinessFormPrint> {
  const params = new URLSearchParams({ format, templateKind })
  if (format === 'pdf' && pages.length) params.set('pages', pages.join(','))
  if (format === 'pdf' && url.startsWith('/api/samples/')) {
    params.set('asyncPreview', '1'); params.set('retryPreview', '1')
  }
  const etag = reusable?.type === 'pdf' ? reusable.etag : ''
  const res = await awaitBusinessPreview(await authedFetch(`${url}?${params.toString()}`, {
    method: 'GET', ...(etag ? { headers: { 'If-None-Match': etag } } : {}),
  }), undefined, undefined, etag)
  if (res.status === 304) {
    if (!reusable || !etag || res.headers.get('etag') !== etag) throw new Error('委托单缓存校验失败，请重新预览')
    return reusable
  }
  const ct = res.headers.get('content-type') || ''
  const sourceHash = res.headers.get('x-source-document-sha256') || ''
  const expectedPages = Number(res.headers.get('x-expected-pages') || 0)
  if (ct.includes('pdf')) {
    const binary = await namedObjectUrl(res, name.replace(/\.docx$/i, '.pdf'))
    return {
      type: 'pdf',
      url: binary.url,
      name: binary.name,
      sourceHash,
      engine: res.headers.get('x-preview-engine') || '',
      etag: res.headers.get('etag') || '',
      expectedPages,
    }
  }
  if (ct.includes('wordprocessingml')) {
    const binary = await namedObjectUrl(res, name)
    return { type: 'docx', url: binary.url, name: binary.name, sourceHash, expectedPages }
  }
  if (!ct.includes('json')) throw new Error(`生成业务单失败（服务 ${res.status}）`)
  const body = await res.json()
  throw new Error(body.message || '生成业务单失败')
}

// 打印委托合同单：format=pdf 网页预览，docx 下载（与 Word 模板完全一致）
export function fetchEntrustPrint(id: number, format: 'pdf' | 'docx', templateKind: BusinessFormTemplateKind, reusable?: BusinessFormPrint) {
  const label = templateKind.startsWith('engineering') ? '工程类' : '产品类'
  return fetchBusinessFormPrint(`/api/entrust/${id}/print`, format, `${label}委托单.docx`, templateKind, [], reusable)
}

// 样品登记打印：按打印窗口中用户选择的正式模板生成
export function fetchSamplePrint(reportNo: string, format: 'pdf' | 'docx', templateKind: BusinessFormTemplateKind, pages: number[] = [], reusable?: BusinessFormPrint) {
  const label = templateKind.startsWith('engineering') ? '工程类' : '产品类'
  return fetchBusinessFormPrint(`/api/samples/${encodeURIComponent(reportNo)}/print`, format, `${label}样品单.docx`, templateKind, pages, reusable)
}

export interface EntrustPreviewFile {
  type: 'pdf'
  url: string
  name: string
  sourceHash: string
  expectedPages: number
  etag?: string
}

export async function previewSampleEntrust(payload: Record<string, unknown>, templateKind: BusinessFormTemplateKind, isCurrent = () => true, onStatus = (_message: string) => {}, reusable?: EntrustPreviewFile): Promise<EntrustPreviewFile> {
  const etag = reusable?.etag
  const res = await awaitBusinessPreview(await authedFetch('/api/samples/entrust-preview', {
    method: 'POST',
    // A ready preview can be returned directly by this POST, without polling.
    // Validate it here too so unchanged downloads keep the existing PDF Blob.
    headers: { 'Content-Type': 'application/json', ...(etag ? { 'If-None-Match': etag } : {}) },
    body: JSON.stringify({ ...payload, templateKind, asyncPreview: true, retryPreview: true }),
  }), isCurrent, onStatus, etag)
  if (!isCurrent()) throw new Error('已关闭委托单预览；后台任务继续处理')
  // The current form is still submitted and every read re-authorized. A 304
  // reuses only this caller's live Blob, never a global/private HTTP cache.
  if (res.status === 304) {
    if (!reusable?.url || !reusable.etag || res.headers.get('etag') !== reusable.etag) {
      throw new Error('委托单缓存校验失败，请重新预览')
    }
    return reusable
  }
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('pdf')) {
    const payloadSampleNo = String(payload.sampleNo || 'sample')
    const binary = await namedObjectUrl(res, `${payloadSampleNo}-WT.pdf`)
    return {
      type: 'pdf' as const,
      url: binary.url,
      name: binary.name,
      sourceHash: res.headers.get('x-source-document-sha256') || '',
      expectedPages: Number(res.headers.get('x-expected-pages') || 0),
      etag: res.headers.get('etag') || '',
    }
  }
  if (contentType.includes('json')) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.message || `委托单预览生成失败（服务 ${res.status}）`)
  }
  const text = await res.text().catch(() => '')
  throw new Error(text && !text.trim().startsWith('<') ? text : `委托单预览生成失败（服务 ${res.status}）`)
}
// 就地修改样品/委托登记信息（直接更新该报告 detail + 刷封面，不改状态、不重走评审）
export function editReportInPlace(reportNo: string, payload: { fullDetail: ReportDetail; editVersion?: number }, administratorEditing = canCorrect()) {
  if (administratorEditing && canCorrect()) return correctForm<{ reportNo: string; status: string; editVersion?: number }>('reports', reportNo, payload)
  return request<{ reportNo: string; status: string; editVersion?: number }>(`/api/reports/${reportNo}/edit`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function fetchEntrustDetail(id: number) {
  return request<EntrustOrder>(`/api/entrust/${id}`)
}
export function fetchEntrustList(params: { keyword?: string; status?: string; projection?: 'list' } = {}) {
  return request<{ rows: EntrustOrder[] }>('/api/entrust/query', { method: 'POST', body: JSON.stringify(params) }).then((d) => d.rows)
}
export interface EntrustOption {
  id?: number
  entrustNo: string
  client: string
  projectName: string
  contractNo: string
  projectType?: string
  erpProjectNo?: string
  amount?: string
  department?: string
  owner?: string
  info?: Record<string, string>
  sampleCount: number
  entrustDate?: string
  workflowDates?: { entrustAt?: string }
}
export function fetchEntrustOptions() {
  return request<{ rows: EntrustOption[] }>('/api/entrust/options').then((d) => d.rows)
}
export function fetchNextEntrustNo() {
  return request<{ entrustNo: string }>('/api/entrust/next-no').then((d) => d.entrustNo)
}

// 经办部门候选（本部门+子部门）+ 当前部门
export function fetchHandleDepartments() {
  return request<{ rows: { id: number; name: string }[]; current: string }>('/api/entrust/handle-departments')
}

// 委托更改：编辑后「提交委托更改完成」回到合同评审
export interface ChangeResubmitPayload {
  editVersion?: number
  client?: string
  projectName?: string
  sampleNo?: string
  project?: string
  note?: string
  fullDetail?: ReportDetail
}
export function changeResubmit(reportNo: string, payload: ChangeResubmitPayload) {
  return request<{ reportNo: string; status: string; editVersion?: number }>(`/api/reports/${reportNo}/change-resubmit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function saveEntrustChange(reportNo: string, payload: { fullDetail: ReportDetail; editVersion?: number }) {
  return request<{ reportNo: string; status: string; editVersion?: number }>(`/api/reports/${reportNo}/change-save`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// 批准后申请报告更改：待打印/待发放/已发放 → 委托更改中（重新从委托开始，保留信息）
export function requestReportChange(reportNo: string, note: string) {
  return request<{ reportNo: string; status: string; editVersion?: number }>(`/api/reports/${reportNo}/request-change`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

// 检测更改完成：检测更改中 → 待审核
export async function changeTestComplete(reportNo: string) {
  const { completePreviewState } = await import('./attachments')
  const preview = await completePreviewState(reportNo, 'data_change')
  if (preview.status !== 'ready') throw new Error('请先打开最新完整报告预览并点击“报告确认”，再提交检测更改')
  return submitTestCompletion(reportNo, 'change-test-complete', {})
}

// ---------- 版本化标准报告 ----------

export interface ReportResultItem {
  name: string
  condition: string
  unit: string
  value: string
}

export interface ReportResultGroup {
  name: string
  items: ReportResultItem[]
}

export interface ReportPhotoSlot {
  attachmentId: number | null
  caption: string
}

export interface ReportDocumentContent {
  profileCode: string
  resultGroups: ReportResultGroup[]
  remarks: string
  photos: ReportPhotoSlot[]
  extraPages: ReportPageItem[]
  compositionOptions: {
    includedOtherAttachmentIds: number[]
    noSupplementBody?: boolean
    preserveUploadedReport?: boolean
    reportLanguage?: 'CN' | 'EN'
    reportTemplateVariant?: 'Standard' | 'Extended'
  }
  updatedBy?: string
  updatedAt?: string
}

export interface ReportTemplateProfile {
  code: string
  name: string
  reportNoPattern: string
  centerPrefix: string
  reportType: string
  composition: string[]
  requiredFields: string[]
  requiresVersion: boolean
  active: boolean
}

export interface ReportDocumentPreflight {
  profile: ReportTemplateProfile
  values: Record<string, unknown>
  content: ReportDocumentContent
  missing: string[]
  warnings: string[]
  ready: boolean
  sourceHash: string
  currentVersionStale: boolean
  hasCompletedReport: boolean
  noSupplementBody?: boolean
  noSupplementSupported?: boolean
  templateSelection?: {
    filename?: string
    kind?: string
    language?: string
    variant?: string
  } | null
}

export interface ReportDocumentVersion {
  id: number
  reportNo: string
  outputKind: 'official' | 'audit'
  versionNo: number
  versionLabel: string
  status: string
  profileCode: string
  composition: string[]
  warnings: string[]
  sourceHash: string
  sha256: string
  hasDocx: boolean
  hasPdf: boolean
  stale: boolean | null
  sourceVerification?: string
  sourceVerificationError?: string
  createdBy: string
  createdAt: string
}

export interface ReportRenderJob {
  id: string
  reportNo: string
  outputKind: 'official' | 'audit'
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  versionId?: number
  version?: ReportDocumentVersion
}

export interface ReportDocumentVersionsResponse {
  rows: ReportDocumentVersion[]
  currentVersionId?: number
  approvedVersionId?: number
}

export function fetchReportDocumentPreflight(reportNo: string, view: ReportDetailView, kind: 'official' | 'audit' = 'official') {
  return request<ReportDocumentPreflight>(`/api/reports/${encodeURIComponent(reportNo)}/document-preflight?kind=${kind}&view=${encodeURIComponent(view)}`)
}

export function fetchReportDocumentContent(reportNo: string, view: ReportDetailView) {
  return request<ReportDocumentContent>(`/api/reports/${encodeURIComponent(reportNo)}/document-content?view=${encodeURIComponent(view)}`)
}

export function saveReportDocumentContent(reportNo: string, content: ReportDocumentContent) {
  return request<ReportDocumentPreflight>(`/api/reports/${encodeURIComponent(reportNo)}/document-content`, {
    method: 'PUT',
    body: JSON.stringify(content),
  })
}

export async function downloadReportAuthoringTemplate(reportNo: string): Promise<{ url: string; name: string; capacityWarnings: string[] }> {
  const response = await authedFetch(`/api/reports/${encodeURIComponent(reportNo)}/authoring-template`)
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('json')) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.message || '完整报告 Word 模板生成失败')
  }
  if (!response.ok || !contentType.includes('wordprocessingml')) {
    throw new Error(`完整报告 Word 模板生成失败（服务 ${response.status}）`)
  }
  return {
    url: URL.createObjectURL(await response.blob()),
    name: `${reportNo}-完整报告填写模板.docx`,
    capacityWarnings: parseTemplateCapacityWarnings(response.headers.get('X-Template-Capacity-Warnings')),
  }
}

export function createReportRenderJob(reportNo: string, outputKind: 'official' | 'audit') {
  return request<ReportRenderJob>(`/api/reports/${encodeURIComponent(reportNo)}/document-jobs`, {
    method: 'POST',
    body: JSON.stringify({ outputKind }),
  })
}

export function fetchReportRenderJob(reportNo: string, jobId: string, view: ReportDetailView) {
  return request<ReportRenderJob>(`/api/reports/${encodeURIComponent(reportNo)}/document-jobs/${jobId}?view=${encodeURIComponent(view)}`)
}

export function fetchReportDocumentVersions(reportNo: string, view: ReportDetailView) {
  return request<ReportDocumentVersionsResponse>(`/api/reports/${encodeURIComponent(reportNo)}/document-versions?view=${encodeURIComponent(view)}`)
}

export async function reportVersionObjectUrl(
  reportNo: string,
  versionId: number,
  view: ReportDetailView,
  format: 'pdf' | 'docx' = 'pdf',
  download = false,
) {
  const response = await authedFetch(
    `/api/reports/${encodeURIComponent(reportNo)}/document-versions/${versionId}/file?format=${format}&download=${download ? 1 : 0}&view=${encodeURIComponent(view)}`,
  )
  const responseType = response.headers.get('content-type') || ''
  if (responseType.includes('application/json')) {
    const body = await response.json()
    throw new Error(body?.message || '报告版本读取失败')
  }
  if (!response.ok) throw new Error(`报告版本读取失败（服务 ${response.status}）`)
  const blob = await response.blob()
  return { url: URL.createObjectURL(blob), contentType: blob.type }
}

export async function resolveReportStandards(reportNo:string, payload:Record<string,unknown>) {
  const res=await authedFetch(`/api/reports/${encodeURIComponent(reportNo)}/standard-resolution`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  const body=await res.json()
  if(body.code!==0)throw new Error(body.message||'标准关联确认失败')
  return body.data as CompliancePreflight
}
