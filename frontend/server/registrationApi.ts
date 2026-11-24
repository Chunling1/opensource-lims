import { createDailyRequests, seedDailyRequests } from './dailyRequests'
import { createCustomerAccounts } from './customerAccounts'
import { createCustomerProjects } from './customerProjects'
import { canApplyDailyRequests } from '../src/types/quality/dailyRequests'
import { createTestEnvironments, seedTestEnvironments } from './testEnvironments'
import { createStandards, seedStandards } from './standards'
import { createDocumentLibrary, seedDocumentLibrary } from './documentLibrary'
import { canManageDocuments } from '../src/types/quality/documentLibrary'
import { createMaintenanceCosts, seedMaintenanceCosts } from './maintenanceCosts'
import { createConsumables, seedConsumables } from './consumables'
import { createEquipmentTypes, seedEquipmentTypes } from './equipmentTypes'
import { createReferenceMaterials, seedReferenceMaterials } from './referenceMaterials'
import { createEquipmentSuppliers, seedEquipmentSuppliers } from './equipmentSuppliers'
import { createEquipmentLoans, seedEquipmentLoans } from './equipmentLoans'
import { createPersonnelCertificates, seedPersonnelCertificates } from './personnelCertificates'
import { createEquipmentLedger, seedEquipmentLedger } from './equipmentLedger'
import { createEquipmentForms } from './equipmentForm'
import { createEquipmentGroups, seedEquipmentGroups } from './equipmentGroups'
import { createEquipmentGroupDefinitions, seedStandardGroups } from './equipmentGroupDefinitions'
import { createEquipmentOverallPlans } from './equipmentOverallPlan'
import { createEquipmentInterimPlans } from './equipmentInterimPlan'
import { createEquipmentCalibrationPlans, seedEquipmentCalibrationPlans } from './equipmentCalibrationPlan'
import { createMonthlyCalibration } from './monthlyCalibration'
import type { CertificateListKind } from '../src/types/quality/certificates'
import { createAttachmentDrafts, attachmentReferences } from './attachmentDrafts'
import { createReportChanges } from './reportChanges'
import { createPersonnelService } from './personnel'
import { reportArchiveColumns } from '../src/types/reports/reportArchive'
import { reportDistributionColumns } from '../src/types/reports/reportDistribution'
import { reportSigningColumns } from '../src/types/reports/reportSigning'
import { createOriginalRecordService } from './originalRecords'
import { createReportLifecycleService } from './reportLifecycle'
import { createDemoSigningProvider, type SigningProvider } from './reportSigning'
import { seedReportLifecycleDemo } from './reportLifecycleDemo'
import type { ReportLifecycleQuery } from '../src/types/reports/reportLifecycle'
import { reportPrintColumns } from '../src/types/reports/reportPrint'
import { tableCellText } from '../src/services/common/table'
import { registrationCsv } from './registrationDomain'
import { createDataEntryService } from './dataEntryDetail'
import { entryWord, entryPdf } from './dataEntryDocuments'
import { parseDataEntryQuery } from './testingDataEntry'
import { parseDataChangeQuery } from './testingDataChanges'
import { parseDataQueryQuery } from './testingDataQuery'
import { parseDataCheckQuery } from './testingDataCheck'
import { parseReportCheckQuery } from './reportCheck'
import { parseReportPrintQuery } from './reportPrint'
import { parseSampleCopyQuery } from './testingSampleCopy'
import { parseTaskQuery } from './testingTaskQuery'
import { parseInboundQuery, parseOutboundQuery } from './sampleInbound'
import { parseDisposalQuery } from './sampleDisposal'
import { parseSampleCompletionQuery } from './testingSampleCompletion'
import { parseFlowQuery } from './sampleFlow'
import { parseCancellationQuery } from './cancellationApprovals'
import { parseCommissionChangeQuery } from './commissionChanges'
import { sampleWorkflowDateFields, sampleConclusions } from '../src/types/commissions/sampleWorkflow'
import { sampleAdvancedFields } from '../src/types/commissions/sampleAdvancedQuery'
import { commissionAdvancedFields } from '../src/types/commissions/commissionAdvancedQuery'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { ManufacturerQuery } from '../src/types/commissions/manufacturer'
import { createReviewChecks } from './reviewChecks'
import { parseReportStage } from './reportCheck'
import { randomUUID } from 'node:crypto'
import { parseSampleDetails, parseSampleCommission } from './sampleForm'
import { parseTestBasisIds } from './sampleTestBases'
import { testBasisFilterFields, testBasisSorts, type TestBasisQuery } from '../src/types/commissions/testBasis'
import { createPrintQueue } from './commissionPrint'
import { createTaskPrintQueue } from './taskPrint'
import type { Plugin } from 'vite'
import { createRegistrationService, seedRegistration } from './registrationDomain'
import { parseAssignmentQuery } from './testingAssignment'
import { parsePickupQuery } from './testingPickup'
import { summaryCommission, summarySample, summaryInquirySample } from './registrationSummary'
import { createTaskProcessingService } from './taskProcessing'
import { demoActors } from '../src/services/storage/demoActors'
import { AppError } from '../src/services/common/errors'
import { commissionDetailKeys, contractSearchFields, type RegistrationContractQuery } from '../src/types/commissions/commissionForm'
import type { RegistrationWorkspace, RegistrationCommission, RegistrationSample, RegistrationQuery, RegistrationState, RegistrationKind, RegistrationCommissionInput, RegistrationSampleInput, DemoAttachment } from '../src/types/commissions/registration'
import { commissionSearchFields, sampleSearchFields, inquirySampleSearchFields, legacyCommissionSearchFields } from '../src/types/commissions/registration'

export const registrationApiPath = '/api/registration'
const cookieName = 'lims_registration_demo'
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '请求内容必须是对象。')
  return value as Record<string, unknown>
}
function parseWorkspace(value: unknown): RegistrationWorkspace {
  if (value === undefined || value === 'registration') return 'registration'
  if (value === 'review' || value === 'query' || value === 'changes') return value
  throw new AppError('BAD_REQUEST', '业务页面参数有误。')
}
export function parseRegistrationQuery(value: unknown, kind: RegistrationKind): RegistrationQuery {
  const input = object(value), query: RegistrationQuery = {}
  for (const key of ['sampleCode', 'reportCode', 'dataStatus', 'sampleType', 'commissionFrom', 'commissionTo', 'commissionCode', 'contains', 'keyword', 'status', 'from', 'to', 'customer', 'owner', 'contract', 'category', 'commissionId'] as const) {
    if (input[key] === undefined || input[key] === '') continue
    if (typeof input[key] !== 'string' || input[key].length > 200) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    query[key] = input[key].trim()
  }
  if (kind !== 'samples' && ['sampleCode', 'reportCode', 'dataStatus', 'sampleType', 'commissionFrom', 'commissionTo'].some(key => query[key as keyof RegistrationQuery])) throw new AppError('BAD_REQUEST', '样品筛选条件仅适用于样品查询。')
  if (query.commissionCode && kind !== 'commissions') throw new AppError('BAD_REQUEST', '委托编号条件仅适用于委托查询。')
  if (input.commissionAdvanced !== undefined) {
    if (kind !== 'commissions') throw new AppError('BAD_REQUEST', '委托高级条件仅适用于委托查询。')
    const fields = object(input.commissionAdvanced)
    if (Object.keys(fields).some(key => !commissionAdvancedFields.some(field => field.key === key))) throw new AppError('BAD_REQUEST', '不支持的委托高级查询字段。')
    query.commissionAdvanced = {}
    for (const { key } of commissionAdvancedFields) {
      if (fields[key] === undefined) continue
      if (typeof fields[key] !== 'string' || fields[key].length > 200) throw new AppError('BAD_REQUEST', '高级查询条件格式有误。')
      if (fields[key].trim()) query.commissionAdvanced[key] = fields[key].trim()
    }
  }
  if (input.sampleAdvanced !== undefined) {
    if (kind !== 'samples' || input.workspace !== 'query') throw new AppError('BAD_REQUEST', '样品高级条件仅适用于委托查询页的样品查询。')
    const fields = object(input.sampleAdvanced)
    if (Object.keys(fields).some(key => !sampleAdvancedFields.some(field => field.key === key))) throw new AppError('BAD_REQUEST', '不支持的样品高级查询字段。')
    query.sampleAdvanced = {}
    for (const { key } of sampleAdvancedFields) {
      if (fields[key] === undefined) continue
      if (typeof fields[key] !== 'string' || fields[key].length > 200) throw new AppError('BAD_REQUEST', '高级查询条件格式有误。')
      if (fields[key].trim()) query.sampleAdvanced[key] = fields[key].trim()
    }
  }
  if (input.sampleWorkflow !== undefined) {
    if (kind !== 'samples' || input.workspace !== 'query') throw new AppError('BAD_REQUEST', '流程查询条件仅适用于委托查询页的样品查询。')
    const workflow = object(input.sampleWorkflow)
    if (Object.keys(workflow).some(key => !['dates', 'conclusion'].includes(key))) throw new AppError('BAD_REQUEST', '不支持的流程查询字段。')
    query.sampleWorkflow = {}
    if (workflow.conclusion !== undefined) {
      const conclusion = sampleConclusions.find(option => option.value === workflow.conclusion)
      if (!conclusion) throw new AppError('BAD_REQUEST', '不支持的结论。')
      query.sampleWorkflow.conclusion = conclusion.value
    }
    if (workflow.dates !== undefined) {
      const dates = object(workflow.dates)
      if (Object.keys(dates).some(key => !sampleWorkflowDateFields.some(field => field.key === key))) throw new AppError('BAD_REQUEST', '不支持的流程日期。')
      query.sampleWorkflow.dates = {}
      for (const { key } of sampleWorkflowDateFields) {
        if (dates[key] === undefined) continue
        const range = object(dates[key])
        if (Object.keys(range).some(key => !['from', 'to'].includes(key)) || typeof range.from !== 'string' || typeof range.to !== 'string' || !range.from || !range.to || range.from.length > 10 || range.to.length > 10) throw new AppError('BAD_REQUEST', '请提交完整的流程日期范围。')
        query.sampleWorkflow.dates[key] = { from: range.from, to: range.to }
      }
    }
  }
  if (input.searchField !== undefined) {
    const fields = kind === 'commissions' ? [...commissionSearchFields.map(field => field.value), ...legacyCommissionSearchFields] : (input.workspace === 'query' ? inquirySampleSearchFields : sampleSearchFields).map(field => field.value)
    if (!fields.some(field => field === input.searchField)) throw new AppError('BAD_REQUEST', '不支持的查询内容。')
    query.searchField = input.searchField as RegistrationQuery['searchField']
  }
  for (const key of ['page', 'pageSize'] as const) {
    if (input[key] === undefined) continue
    if (typeof input[key] !== 'number' || !Number.isSafeInteger(input[key]) || input[key] < 1) throw new AppError('BAD_REQUEST', '分页参数有误。')
    query[key] = input[key]
  }
  if (query.pageSize && !(kind === 'commissions' ? [5, 10, 20] : [10, 20, 50]).includes(query.pageSize)) throw new AppError('BAD_REQUEST', '每页条数超出允许范围。')
  if (input.sort !== undefined) { if (!(kind === 'commissions' ? ['code', 'createdAt', 'commissionDate'] : ['code', 'createdAt']).includes(String(input.sort))) throw new AppError('BAD_REQUEST', '不支持的排序字段。'); query.sort = String(input.sort) }
  if (input.direction !== undefined) { if (!['asc', 'desc'].includes(String(input.direction))) throw new AppError('BAD_REQUEST', '不支持的排序方向。'); query.direction = String(input.direction) }
  if (input.ids !== undefined) query.ids = parseIds(input.ids)
  if (input.commissionIds !== undefined) query.commissionIds = parseIds(input.commissionIds)
  if (input.eligibleOnly !== undefined) { if (typeof input.eligibleOnly !== 'boolean') throw new AppError('BAD_REQUEST', '委托范围参数有误。'); query.eligibleOnly = input.eligibleOnly }
  return query
}
function parseIds(value: unknown) {
  if (!Array.isArray(value) || value.length > 50 || value.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('BAD_REQUEST', '请提交最多 50 个有效记录编号。')
  return [...new Set(value)] as string[]
}
function parseContractQuery(value: unknown): RegistrationContractQuery {
  const source = object(value), common = parseRegistrationQuery({ ...source, searchField: undefined }, 'commissions')
  const query: RegistrationContractQuery = { keyword: common.keyword, from: common.from, to: common.to, page: common.page, pageSize: common.pageSize }
  if (source.code !== undefined) { if (typeof source.code !== 'string' || source.code.length > 200) throw new AppError('BAD_REQUEST', '合同编号格式有误。'); query.code = source.code.trim() }
  if (source.ownDepartment !== undefined) { if (typeof source.ownDepartment !== 'boolean') throw new AppError('BAD_REQUEST', '部门范围格式有误。'); query.ownDepartment = source.ownDepartment }
  if (source.searchField !== undefined) { if (!contractSearchFields.some(f => f.value === source.searchField)) throw new AppError('BAD_REQUEST', '不支持的合同查询内容。'); query.searchField = source.searchField as RegistrationContractQuery['searchField'] }
  return query
}
function parseTestBasisQuery(value: unknown): TestBasisQuery {
  const source = object(value)
  if (typeof source.planId !== 'string' || !source.planId || source.planId.length > 100) throw new AppError('BAD_REQUEST', '请先选择有效的检测方案。')
  const common = parseRegistrationQuery({ page: source.page, pageSize: source.pageSize }, 'samples')
  const query: TestBasisQuery = { planId: source.planId, page: common.page, pageSize: common.pageSize }
  for (const key of [...testBasisFilterFields.map(field => field.key), 'departmentCategory'] as const) {
    if (source[key] === undefined) continue
    if (typeof source[key] !== 'string' || source[key].length > 200) throw new AppError('BAD_REQUEST', '检测依据查询条件格式有误。')
    query[key] = source[key].trim()
  }
  if (source.ownDepartment !== undefined) { if (typeof source.ownDepartment !== 'boolean') throw new AppError('BAD_REQUEST', '部门范围格式有误。'); query.ownDepartment = source.ownDepartment }
  if (source.sort !== undefined) { if (!testBasisSorts.some(sort => sort.value === source.sort)) throw new AppError('BAD_REQUEST', '检测依据排序格式有误。'); query.sort = source.sort as TestBasisQuery['sort'] }
  if (source.ids !== undefined) query.ids = parseTestBasisIds(source.ids)
  return query
}
function parseInput(value: unknown, kind: RegistrationKind) {
  const source = object(value), result: Record<string, unknown> = {}
  const strings = ['name', 'customer', 'contact', 'phone', 'notes', ...(kind === 'commissions' ? ['contract', 'dueDate', 'requirements', 'source', 'settlement'] : ['commissionId', 'category', 'unit', 'storage'])]
  for (const key of strings) {
    if (typeof source[key] !== 'string' || source[key].length > 4000) throw new AppError('VALIDATION', '请检查表单字段格式。')
    result[key] = source[key]
  }
  for (const key of kind === 'commissions' ? ['discount', 'taxRate'] : ['quantity']) {
    if (typeof source[key] !== 'number' || !Number.isFinite(source[key])) throw new AppError('VALIDATION', '请检查表单数值。')
    result[key] = source[key]
  }
  if (!Array.isArray(source.projects) || source.projects.length > 100 || source.projects.some(p => typeof p !== 'string')) throw new AppError('VALIDATION', '请检查检测项目。')
  result.projects = source.projects
  if (kind === 'samples') result.details = parseSampleDetails(source.details)
  if (kind === 'samples' && source.commissionInfo !== undefined) result.commissionInfo = parseSampleCommission(source.commissionInfo)
  if (kind === 'commissions') for (const key of commissionDetailKeys) {
    if (source[key] === undefined) continue
    if (typeof source[key] !== 'string' || source[key].length > 500) throw new AppError('VALIDATION', '请检查委托资料字段格式。')
    result[key] = source[key]
  }
  // Only editable fields cross the HTTP boundary; ignore status, scope and audit fields.
  return result
}
async function body(request: IncomingMessage) {
  if (!request.headers['content-type']?.startsWith('application/json')) throw new AppError('BAD_REQUEST', '请求必须使用 JSON。')
  const chunks: Buffer[] = []; let size = 0
  for await (const chunk of request) { size += chunk.length; if (size > 29 * 1024 * 1024) throw new AppError('BAD_REQUEST', '请求内容过大。'); chunks.push(Buffer.from(chunk)) }
  try { return object(JSON.parse(Buffer.concat(chunks).toString('utf8'))) }
  catch (e) { if (e instanceof AppError) throw e; throw new AppError('BAD_REQUEST', '请求不是有效 JSON。') }
}
function json(response: ServerResponse, data: unknown, status = 200) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  // Frozen binaries and signing configuration are server-owned; files use the authorized file endpoint.
  response.end(JSON.stringify(data, (key, value) => ['reportRelease', 'reportReleaseHistory'].includes(key) ? undefined : value))
}

// Central demo latency setting. Set to 0 to disable the simulated query wait.
export const registrationQueryDelayMs = 2000
async function waitForQuery(response: ServerResponse, delay: number): Promise<boolean> {
  if (response.destroyed) return false
  if (delay > 0) await new Promise<void>(resolve => {
    const timer = setTimeout(done, delay)
    function done() { clearTimeout(timer); response.off('close', done); resolve() }
    response.once('close', done)
  })
  return !response.destroyed
}

// Node-only mock backend. Each browser session owns a dataset; only requested pages cross HTTP.
export function createRegistrationMiddleware(options: { reviewCheckDelay?: number; queryDelayMs?: number } = {}) {
  const sessions = new Map<string, { state: RegistrationState; attachments: ReturnType<typeof createAttachmentDrafts>; touched: number; signingProvider: SigningProvider; lifecycleWorker?: ReturnType<typeof createReportLifecycleService>; entryPdfs: Map<string, Promise<Buffer>>; prints: ReturnType<typeof createPrintQueue>; taskPrints: ReturnType<typeof createTaskPrintQueue>; reviewChecks: ReturnType<typeof createReviewChecks> }>()
  const workerTimer = setInterval(() => {
    for (const [key, session] of sessions) {
      if (Date.now() - session.touched > 8 * 60 * 60 * 1000) { sessions.delete(key); continue }
      session.attachments.sweep()
      void session.lifecycleWorker?.tick().catch(() => { /* Task retains its query-first recovery state. */ })
    }
  }, 1500)
  workerTimer.unref()
  const middleware = (request: IncomingMessage, response: ServerResponse, next: () => void) => {
    const url = new URL(request.url || '/', 'http://localhost')
    if (!url.pathname.startsWith(registrationApiPath + '/')) return next()
    void (async () => {
      const origin = request.headers.origin
      if (origin && new URL(origin).host !== request.headers.host) throw new AppError('FORBIDDEN', '模拟接口仅接受同源请求。')
      const path = url.pathname.slice(registrationApiPath.length).split('/').filter(Boolean).map(decodeURIComponent)
      const sessionId = request.headers.cookie?.split(';').map(s => s.trim()).find(s => s.startsWith(cookieName + '='))?.slice(cookieName.length + 1)
      if (path[0] === 'session' && path.length === 1 && request.method === 'POST') {
        const now = Date.now()
        for (const [key, entry] of sessions) if (now - entry.touched > 8 * 60 * 60 * 1000) sessions.delete(key)
        let key = sessionId && sessions.has(sessionId) ? sessionId : ''
        if (!key) {
          if (sessions.size >= 100) sessions.delete(sessions.keys().next().value!)
          key = randomUUID()
          const state = seedRegistration(); seedPersonnelCertificates(state); state.equipmentLedger = seedEquipmentLedger(); seedEquipmentGroups(state); seedStandardGroups(state); seedStandards(state); seedTestEnvironments(state); seedDailyRequests(state); await seedReportLifecycleDemo(state)
          seedEquipmentCalibrationPlans(state); seedEquipmentLoans(state); seedEquipmentSuppliers(state); seedReferenceMaterials(state); seedEquipmentTypes(state); seedConsumables(state); seedMaintenanceCosts(state); seedDocumentLibrary(state); seedDocumentLibrary(state, new Date(), 'monitoring')
          sessions.set(key, { state, attachments: createAttachmentDrafts(), touched: now, signingProvider: createDemoSigningProvider(process.env.LIMS_SIGNING_CALLBACK_SECRET || randomUUID()), entryPdfs: new Map(), prints: createPrintQueue(), taskPrints: createTaskPrintQueue(), reviewChecks: createReviewChecks(options.reviewCheckDelay) })
          const created = sessions.get(key)!
          created.lifecycleWorker = createReportLifecycleService({ actor: () => demoActors[0]!, read: () => created.state, write: state => { created.state = state } }, created.signingProvider)
        }
        response.setHeader('Set-Cookie', `${cookieName}=${key}; Path=${registrationApiPath}; HttpOnly; SameSite=Strict`)
        json(response, { mode: 'mock' }); return
      }
      const session = sessionId ? sessions.get(sessionId) : undefined
      if (!session) throw new AppError('UNAUTHORIZED', '模拟会话已失效，请刷新页面重新连接。')
      session.touched = Date.now()
      if (path.join('/') === 'reports/signing/callback' && request.method === 'POST') {
        const data = await body(request)
        if (['sampleId', 'releaseId', 'taskKey', 'externalId'].some(key => typeof data[key] !== 'string') || !Number.isSafeInteger(data.revision)) throw new AppError('BAD_REQUEST', '签章回调格式有误。')
        json(response, await session.lifecycleWorker!.callback(String(request.headers['x-signing-token'] || ''), data as unknown as Parameters<ReturnType<typeof createReportLifecycleService>['callback']>[1])); return
      }
      // This header selects a fixed mock identity; it is not production authentication.
      const actor = demoActors.find(a => a.id === request.headers['x-demo-actor'])
      if (!actor) throw new AppError('UNAUTHORIZED', '请选择有效的演示身份。')
      if (path[0] === 'attachment-drafts' && path.length === 3 && request.method === 'POST') {
        const data = await body(request), scope = data.scope, recordId = typeof data.recordId === 'string' ? data.recordId : ''
        if (scope === 'daily-request') {
          const service = createDailyRequests({ actor: () => actor, read: () => session.state })
          const record = recordId ? service.detail(recordId) : undefined
          if (path[2] !== 'file' ? !canApplyDailyRequests(actor) || record && !record.canEdit : !record && !canApplyDailyRequests(actor)) throw new AppError('FORBIDDEN', '当前申请附件不可修改。')
          const args = [path[1]!, actor.id, scope, recordId] as const
          if (path[2] === 'upload') { json(response, session.attachments.upload(...args, data.file)); return }
          if (path[2] === 'discard') { session.attachments.discard(...args); json(response, { discarded: true }); return }
          if (path[2] === 'remove') { if (!record?.files.some(file => file.id === data.fileId)) session.attachments.remove(...args, String(data.fileId)); json(response, { removed: true }); return }
          if (path[2] === 'file') {
            const file = record?.files.find(file => file.id === data.fileId) || session.attachments.file(...args, String(data.fileId))
            response.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }); response.end(Buffer.from(file.dataUrl.split(',')[1]!, 'base64')); return
          }
          throw new AppError('NOT_FOUND', '附件接口不存在。')
        }
        if (scope !== 'personnel' && scope !== 'external' && scope !== 'certificate' && scope !== 'equipment' && scope !== 'document' && scope !== 'monitoring-document') throw new AppError('BAD_REQUEST', '附件业务类型有误。')
        const documentScope = scope === 'document' || scope === 'monitoring-document', documentModule = scope === 'monitoring-document' ? 'monitoring' : 'library'
        if (documentScope ? path[2] !== 'file' && !canManageDocuments(actor) : !actor.roles.some(role => (scope !== 'external' ? ['admin', 'quality'] : ['admin', 'reports']).includes(role))) throw new AppError('FORBIDDEN', '无权上传此业务附件。')
        if (recordId) {
          const deps = { actor: () => actor, read: () => session.state, write: (state: RegistrationState) => { session.state = state } }
          if (scope === 'personnel') createPersonnelService(deps).detail(recordId)
          else if (documentScope) createDocumentLibrary(deps, documentModule).detail(recordId)
          else if (scope === 'equipment') createEquipmentForms(deps).detail(recordId)
          else if (scope === 'certificate') createPersonnelCertificates(deps).certificate(recordId)
          else if (!createReportChanges(deps, 'external').detail(recordId).canEdit) throw new AppError('FORBIDDEN', '当前申请不可编辑。')
        }
        if (documentScope && !recordId) throw new AppError('BAD_REQUEST', '请先保存文件基础信息。')
        const args = [path[1]!, actor.id, scope, recordId] as const
        if (path[2] === 'upload') { if (scope === 'certificate' && !await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return; json(response, session.attachments.upload(...args, data.file)); return }
        if (path[2] === 'discard') { session.attachments.discard(...args); json(response, { discarded: true }); return }
        if (path[2] === 'remove') {
          if (documentScope && createDocumentLibrary({ actor: () => actor, read: () => session.state }, documentModule).detail(recordId).files.some(f => f.id === data.fileId)) { json(response, { removed: true }); return }
          if (scope === 'certificate' && recordId && createPersonnelCertificates({ actor: () => actor, read: () => session.state }).certificate(recordId).files.some(f => f.id === data.fileId)) { json(response, { removed: true }); return }
          session.attachments.remove(...args, String(data.fileId)); json(response, { removed: true }); return }
        if (path[2] === 'file') {
          const saved = documentScope ? createDocumentLibrary({ actor: () => actor, read: () => session.state }, documentModule).detail(recordId).files.find(f => f.id === data.fileId) : scope === 'certificate' && recordId ? createPersonnelCertificates({ actor: () => actor, read: () => session.state }).certificate(recordId).files.find(f => f.id === data.fileId) : undefined
          const file = saved || session.attachments.file(...args, String(data.fileId))
          response.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }); response.end(Buffer.from(file.dataUrl.split(',')[1]!, 'base64')); return
        }
        throw new AppError('NOT_FOUND', '附件接口不存在。')
      }
      if (path[0] === 'quality' && path[1] === 'documents' && (path[2] === 'library' || path[2] === 'monitoring')) {
        if (path.length !== 4 || request.method !== 'POST') throw new AppError('NOT_FOUND', '文件管理接口不存在。')
        const scope = path[2] === 'monitoring' ? 'monitoring-document' : 'document'
        const service = createDocumentLibrary({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, path[2]), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const kind = data.kind
        if (['move', 'history', 'export-history'].includes(path[3]!) && kind !== 'issue' && kind !== 'recover') throw new AppError('VALIDATION', '登记类型有误。')
        if (path[3] === 'query') json(response, service.query(data))
        else if (path[3] === 'detail') json(response, attachmentReferences(service.detail(data.id)))
        else if (path[3] === 'save') json(response, attachmentReferences(service.save(data)))
        else if (path[3] === 'delete') json(response, service.remove(data))
        else if (path[3] === 'move') json(response, service.move(kind as 'issue' | 'recover', data))
        else if (path[3] === 'history') json(response, service.history(kind as 'issue' | 'recover', data))
        else if (path[3] === 'files') {
          const previous = service.detail(data.id), resolved = session.attachments.resolve(data, previous.files, data.attachmentDraftId, actor.id, scope, previous.id)
          const saved = service.saveFiles(resolved)
          if (typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, scope, previous.id)
          json(response, attachmentReferences(saved))
        } else if (path[3] === 'export' || path[3] === 'export-history') {
          const csv = path[3] === 'export' ? service.export(data) : service.exportHistory(kind as 'issue' | 'recover', data)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv)
        } else throw new AppError('NOT_FOUND', '文件管理接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'plans' && path[3] === 'calibration') {
        if (path.length !== 5 || !['query', 'detail', 'save', 'submit', 'export'].includes(path[4]!) || request.method !== 'POST') throw new AppError('NOT_FOUND', '计量器具周期检定计划接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const plans = createEquipmentCalibrationPlans({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path[4] === 'export') { const csv = plans.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else json(response, path[4] === 'query' ? plans.query(data) : path[4] === 'detail' ? plans.detail(data.id) : plans.save(data, path[4] === 'submit'))
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'plans' && path[3] === 'interim') {
        const equipmentChoices = path.length === 6 && path[4] === 'equipment' && path[5] === 'query'
        if ((!equipmentChoices && (path.length !== 5 || !['query', 'detail', 'save', 'delete', 'export', 'print'].includes(path[4]!))) || request.method !== 'POST') throw new AppError('NOT_FOUND', '设备期间核查计划接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const plans = createEquipmentInterimPlans({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (equipmentChoices) json(response, plans.equipmentChoices(data))
        else if (path[4] === 'export') { const csv = plans.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else if (path[4] === 'query' || path[4] === 'print') json(response, plans.query(data, path[4] === 'print'))
        else if (path[4] === 'detail') json(response, plans.detail(data.id))
        else json(response, path[4] === 'save' ? plans.save(data) : plans.remove(data))
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'plans' && path[3] === 'overall') {
        if (path.length !== 5 || !['query', 'detail', 'save', 'batch', 'export', 'print'].includes(path[4]!) || request.method !== 'POST') throw new AppError('NOT_FOUND', '设备总体计划接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const plans = createEquipmentOverallPlans({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path[4] === 'export') { const csv = plans.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else if (path[4] === 'query' || path[4] === 'print') json(response, plans.query(data, path[4] === 'print'))
        else if (path[4] === 'detail') json(response, plans.detail(data.id))
        else json(response, plans.save(data))
        return
      }
      if (path[0] === 'quality' && ['requests', 'approvals'].includes(path[1]!)) {
        const approvalMode = path[1] === 'approvals'
        if (path.length !== 3 || request.method !== 'POST' || !(approvalMode ? ['query', 'detail', 'approve', 'revoke', 'void', 'export'] : ['query', 'detail', 'save', 'withdraw', 'delete', 'export']).includes(path[2]!)) throw new AppError('NOT_FOUND', '日常事务申请接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        seedDailyRequests(session.state)
        const service = createDailyRequests({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, approvalMode)
        if (path[2] === 'query') json(response, attachmentReferences(service.query(data)))
        else if (path[2] === 'detail') json(response, attachmentReferences(service.detail(data.id)))
        else if (path[2] === 'save') {
          const id = typeof data.id === 'string' ? data.id : '', previous = id ? service.detail(id) : undefined
          const resolved = session.attachments.resolve(data, previous?.files, data.attachmentDraftId, actor.id, 'daily-request', id)
          const saved = service.save(resolved)
          if (typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, 'daily-request', id)
          json(response, attachmentReferences(saved))
        } else if (path[2] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else if (approvalMode) json(response, attachmentReferences(service.approve(data, path[2] as 'approve' | 'revoke' | 'void')))
        else json(response, service.action(data, path[2] as 'withdraw' | 'delete'))
        return
      }
      if (path[0] === 'quality' && path[1] === 'environment') {
        if (path.length !== 3 || request.method !== 'POST' || !['query', 'detail', 'options', 'save', 'delete', 'export'].includes(path[2]!)) throw new AppError('NOT_FOUND', '试验环境接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        seedTestEnvironments(session.state)
        const service = createTestEnvironments({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path[2] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else json(response, path[2] === 'query' ? service.query(data) : path[2] === 'detail' ? service.detail(data.id) : path[2] === 'options' ? service.options() : path[2] === 'save' ? service.save(data) : service.remove(data))
        return
      }
      if (path[0] === 'quality' && (path[1] === 'equipment' && path[2] === 'groups' || path[1] === 'standards' && ['groups', 'categories'].includes(path[2]!))) {
        if (path.length !== 4 || !['query', 'detail', 'save', 'delete', 'export'].includes(path[3]!) || request.method !== 'POST') throw new AppError('NOT_FOUND', '列表项定义接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const groups = createEquipmentGroupDefinitions({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, path[1] === 'standards' ? 'standards' : 'equipment')
        if (path[3] === 'export') { const csv = groups.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else json(response, path[3] === 'query' ? groups.query(data) : path[3] === 'detail' ? groups.detail(data.id) : path[3] === 'save' ? groups.save(data) : groups.remove(data))
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && ['monthly-calibration', 'department-monthly-calibration'].includes(path[2]!)) {
        if (path.length !== 4 || !['query', 'export'].includes(path[3]!) || request.method !== 'POST') throw new AppError('NOT_FOUND', '月检定计划接口不存在。')
        const data = { ...await body(request), ...(path[2] === 'department-monthly-calibration' ? { ownDepartment: true } : {}) }
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const plans = createMonthlyCalibration({ actor: () => actor, read: () => session.state })
        if (path[3] === 'query') json(response, plans.query(data))
        else { const csv = plans.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'department-ledger') {
        if (path.length !== 4 || !['query', 'export'].includes(path[3]!) || request.method !== 'POST') throw new AppError('NOT_FOUND', '设备台账接口不存在。')
        const data = { ...await body(request), ownDepartment: true }
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const ledger = createEquipmentLedger({ actor: () => actor, read: () => session.state })
        if (path[3] === 'query') json(response, ledger.query(data))
        else { const csv = ledger.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        return
      }
      if (path[0] === 'quality' && path[1] === 'standards' && ['library', 'department-library'].includes(path[2]!)) {
        const operation = path[3], departmentMode = path[2] === 'department-library'
        if (path.length !== 4 || request.method !== 'POST' || !['query', 'detail', 'options', 'save', 'delete', 'group-context', 'group-associations', 'template', 'import', 'export'].includes(operation!)) throw new AppError('NOT_FOUND', '检测标准接口不存在。')
        if (departmentMode && !['query', 'detail', 'export', 'options', 'group-context', 'group-associations'].includes(operation!)) throw new AppError('FORBIDDEN', '请在检测标准基础信息库维护标准信息。')
        const data = await body(request), service = createStandards({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (departmentMode) {
          data.ownDepartment = true
          const ids = operation === 'detail' ? [data.id] : operation === 'group-context' ? data.ids : operation === 'group-associations' && Array.isArray(data.records) ? data.records.map((row: { id?: unknown }) => row?.id) : []
          if (Array.isArray(ids) && ids.some(id => !service.detail(id).departmentIds.includes(actor.departmentId))) throw new AppError('NOT_FOUND', '所选标准不属于本部门。')
        }
        if (operation === 'export' || operation === 'template') { const csv = operation === 'template' ? service.template() : service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else json(response, operation === 'query' ? service.query(data) : operation === 'detail' ? service.detail(data.id) : operation === 'options' ? service.options() : operation === 'save' ? service.save(data) : operation === 'delete' ? service.remove(data) : operation === 'group-context' ? service.context(data.ids) : operation === 'group-associations' ? service.associations(data) : service.importCsv(data.csv))
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'maintenance-costs') {
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '设备维护费用接口不存在。')
        const service = createMaintenanceCosts({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'query') json(response, service.query(data))
        else if (path[3] === 'detail') json(response, service.detail(data.id))
        else if (path[3] === 'save') json(response, service.save(data))
        else if (path[3] === 'delete') json(response, service.remove(data))
        else if (path[3] === 'import') json(response, service.importCsv(data.csv))
        else if (path[3] === 'template') { response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(service.template()) }
        else if (path[3] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '设备维护费用接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'consumables') {
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '易耗品接口不存在。')
        const service = createConsumables({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'query') json(response, service.query(data))
        else if (path[3] === 'detail') json(response, service.detail(data.id))
        else if (path[3] === 'save') json(response, service.save(data))
        else if (path[3] === 'delete') json(response, service.remove(data))
        else if (path[3] === 'import') json(response, service.importCsv(data.csv))
        else if (path[3] === 'template') { response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(service.template()) }
        else if (path[3] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '易耗品接口不存在。')
        return
      }
      if (path[0] === 'customers' && path[1] === 'projects') {
        if (request.method !== 'POST' || path.length !== 3) throw new AppError('NOT_FOUND', '工程登记接口不存在。')
        const service = createCustomerProjects({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (path[2] === 'query') json(response, service.query(data))
        else if (path[2] === 'detail') json(response, service.detail(data.id))
        else if (path[2] === 'options') json(response, service.options())
        else if (path[2] === 'save') json(response, service.save(data))
        else if (path[2] === 'batch') json(response, service.batch(data))
        else if (path[2] === 'delete') json(response, service.remove(data))
        else if (path[2] === 'import') json(response, service.importCsv(data.csv))
        else if (path[2] === 'template' || path[2] === 'export') { const csv = path[2] === 'template' ? service.template() : service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '工程登记接口不存在。')
        return
      }
      if (path[0] === 'customers' && path[1] === 'accounts') {
        if (request.method !== 'POST' || path.length !== 3) throw new AppError('NOT_FOUND', '客户账号接口不存在。')
        const service = createCustomerAccounts({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (path[2] === 'query') json(response, service.query(data))
        else if (path[2] === 'detail') json(response, service.detail(data.id))
        else if (path[2] === 'save') json(response, service.save(data))
        else if (path[2] === 'reset-password') json(response, service.resetPassword(data))
        else if (path[2] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '客户账号接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'types') {
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '设备类型接口不存在。')
        const service = createEquipmentTypes({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'query') json(response, service.query(data))
        else if (path[3] === 'detail') json(response, service.detail(data.id))
        else if (path[3] === 'save') json(response, service.save(data))
        else if (path[3] === 'delete') json(response, service.remove(data))
        else if (path[3] === 'export') { const csv = service.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '设备类型接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'reference-materials') {
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '标准物质接口不存在。')
        const service = createReferenceMaterials({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'people') { json(response, service.queryUsers(data)); return }
        if (path[3] === 'person') { json(response, service.person(data.id)); return }
        if (data.kind !== 'materials' && data.kind !== 'acceptances') throw new AppError('VALIDATION', '列表类型有误。')
        if (path[3] === 'query') json(response, service.query(data.kind, data))
        else if (path[3] === 'detail') json(response, service.detail(data.kind, data.id))
        else if (path[3] === 'save') json(response, service.save(data.kind, data))
        else if (path[3] === 'delete') json(response, service.remove(data.kind, data))
        else if (path[3] === 'export') { const csv = service.export(data.kind, data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '标准物质接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'suppliers') {
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '供应商及评价接口不存在。')
        const service = createEquipmentSuppliers({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }), data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'options') { json(response, service.options()); return }
        if (data.kind !== 'suppliers' && data.kind !== 'evaluations') throw new AppError('VALIDATION', '列表类型有误。')
        if (path[3] === 'query') json(response, service.query(data.kind, data))
        else if (path[3] === 'detail') json(response, service.detail(data.kind, data.id))
        else if (path[3] === 'save') json(response, service.save(data.kind, data))
        else if (path[3] === 'delete') json(response, service.remove(data.kind, data))
        else if (path[3] === 'export') { const csv = service.export(data.kind, data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else throw new AppError('NOT_FOUND', '供应商及评价接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'loans') {
        const loans = createEquipmentLoans({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (request.method !== 'POST' || path.length !== 4) throw new AppError('NOT_FOUND', '领用与归还接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path[3] === 'context') json(response, loans.context(data))
        else if (path[3] === 'options') json(response, loans.options())
        else if (path[3] === 'detail') json(response, loans.detail(data.id))
        else if (path[3] === 'borrow') json(response, loans.borrow(data))
        else if (path[3] === 'return') json(response, loans.returnDevices(data))
        else if (path[3] === 'history-export') { const csv = loans.exportHistory(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        else if (['query', 'export'].includes(path[3]!)) {
          if (data.kind !== 'available' && data.kind !== 'records') throw new AppError('VALIDATION', '列表类型有误。')
          if (path[3] === 'query') json(response, loans.query(data.kind, data))
          else { response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(loans.export(data.kind, data)) }
        } else throw new AppError('NOT_FOUND', '领用与归还接口不存在。')
        return
      }
      if (path[0] === 'quality' && path[1] === 'equipment' && path[2] === 'ledger') {
        const forms = createEquipmentForms({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path.length === 4 && path[3] === 'template' && request.method === 'GET') {
          const csv = forms.template()
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return
        }
        if (path.length === 4 && path[3] === 'import' && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, forms.importCsv(data.csv)); return
        }
        if (path.length === 4 && ['group-context', 'group-associations'].includes(path[3]!) && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          const groups = createEquipmentGroups({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
          json(response, path[3] === 'group-context' ? groups.context(data) : groups.save(data)); return
        }
        if (path.length === 4 && path[3] === 'batch-update' && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, forms.batchUpdate(data)); return
        }
        if (path.length === 4 && ['plans', 'plan-selection'].includes(path[3]!) && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, path[3] === 'plans' ? forms.plans(data) : forms.planSelection(data.selection, data.toggle)); return
        }
        if (path.length === 4 && path[3] === 'options' && request.method === 'GET') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, forms.options()); return
        }
        if (path.length === 5 && path[4] === 'detail' && request.method === 'GET') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, forms.detail(path[3]!)); return
        }
        if ((path.length === 4 && path[3] === 'save' || path.length === 5 && path[4] === 'save') && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          const id = path.length === 5 ? path[3]! : ''
          const previous = id ? forms.detail(id) : undefined
          const resolved = session.attachments.resolve(data, previous, data.attachmentDraftId, actor.id, 'equipment', id)
          const saved = forms.save(resolved, id || undefined)
          if (typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, 'equipment', id)
          json(response, saved); return
        }
        if (path.length === 5 && path[4] === 'delete' && request.method === 'POST') {
          const data = await body(request)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, forms.remove(path[3]!, data)); return
        }
        if (request.method !== 'POST' || path.length !== 4 || !['query', 'export'].includes(path[3]!)) throw new AppError('NOT_FOUND', '设备台账接口不存在。')
        const data = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const ledger = createEquipmentLedger({ actor: () => actor, read: () => session.state })
        if (path[3] === 'query') json(response, ledger.query(data))
        else { const csv = ledger.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv) }
        return
      }
      if (path[0] === 'quality' && path[1] === 'certificates') {
        const certificates = createPersonnelCertificates({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        if (path.length === 3 && path[2] === 'options' && request.method === 'GET') { json(response, certificates.options()); return }
        const kind = path[2] as CertificateListKind
        if (!['people', 'certificates', 'projects'].includes(kind)) throw new AppError('NOT_FOUND', '上岗证接口不存在。')
        if (request.method === 'GET' && kind !== 'people' && path.length === 4) {
          const detail = kind === 'certificates' ? certificates.certificate(path[3]!) : certificates.project(path[3]!)
          json(response, attachmentReferences(detail)); return
        }
        if (request.method === 'GET' && kind === 'certificates' && path.length === 6 && path[4] === 'files') {
          const file = certificates.certificate(path[3]!).files.find(f => f.id === path[5])
          if (!file) throw new AppError('NOT_FOUND', '附件不存在。')
          response.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
          response.end(Buffer.from(file.dataUrl.split(',')[1]!, 'base64')); return
        }
        if (request.method === 'POST') {
          const data = await body(request)
          if (path.length === 4 && path[3] === 'query') { json(response, certificates.query(kind, data)); return }
          if (path.length === 4 && path[3] === 'export') {
            const csv = certificates.export(kind, data)
            response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return
          }
          if (kind !== 'people' && (path.length === 3 || path.length === 5 && path[4] === 'save')) {
            const id = path.length === 5 ? path[3]! : undefined
            if (kind === 'projects') { json(response, certificates.saveProjects(data, id)); return }
            const previous = id ? certificates.certificate(id).files : []
            const resolved = session.attachments.resolve(data, previous, data.attachmentDraftId, actor.id, 'certificate', id || '')
            const saved = certificates.saveCertificate(resolved, id)
            if (typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, 'certificate', id || '')
            json(response, saved); return
          }
          if (kind !== 'people' && path.length === 5 && path[4] === 'delete') { json(response, certificates.remove(kind, path[3]!, data)); return }
        }
        throw new AppError('NOT_FOUND', '上岗证接口不存在。')
      }
      if (path[0] === 'quality' && path[1] === 'personnel') {
        const personnel = createPersonnelService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path.length === 4 && path[2] === 'users' && request.method === 'POST') {
          const data = await body(request)
          if (path[3] === 'query') { json(response, personnel.queryUsers(data)); return }
          if (path[3] === 'validate') { json(response, personnel.resolveUser(data.id)); return }
        }
        if (path.length === 3 && path[2] === 'template' && request.method === 'GET') {
          const csv = personnel.template()
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return
        }
        if (path.length === 3 && request.method === 'GET') { json(response, personnel.detail(path[2]!)); return }
        if (request.method === 'POST') {
          const data = await body(request)
          if (path.length === 3 && path[2] === 'query') {
            if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
            json(response, personnel.query(data)); return
          }
          if (path.length === 3 && path[2] === 'export') {
            const csv = personnel.export(data)
            response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return
          }
          if (path.length === 3 && path[2] === 'import') { json(response, personnel.importCsv(data.csv)); return }
          if (path.length === 2 || path.length === 4 && path[3] === 'save') {
            const id = path.length === 4 ? path[2]! : undefined
            const resolved = session.attachments.resolve(data, id ? personnel.detail(id).profile : undefined, data.attachmentDraftId, actor.id, 'personnel', id || '')
            const saved = personnel.save(resolved, id)
            if (typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, 'personnel', id || '')
            json(response, attachmentReferences(saved)); return
          }
          if (path.length === 4 && path[3] === 'delete') { json(response, personnel.remove(path[2]!, data.version)); return }
        }
        throw new AppError('NOT_FOUND', '人员登记接口不存在。')
      }
      const service = createRegistrationService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, session.reviewChecks)
      // Reject stale clients that still expose the former report-stage editor.
      if (path[0] === 'samples' && path[2] === 'report-form' && path.length === 3 && request.method === 'POST') {
        throw new AppError('FORBIDDEN', '报告形式由样品单确定，请通过样品信息更改流程修改。')
      }
      if (path[0] === 'reports' && path[1] === 'query' && request.method === 'POST') {
        const data = await body(request)
        if (path.length === 3 && path[2] === 'list') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.reportQuerySamples(data)); return
        }
        if (path.length === 3 && path[2] === 'export') {
          const csv = await service.exportReportQuerySamples(data)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return
        }
        if (path.length === 4 && path[3] === 'void') { json(response, await service.reportQueryVoid(path[2]!, data.version as number, data.reason)); return }
        if (path.length === 4 && path[3] === 'file') {
          if (typeof data.releaseId !== 'string') throw new AppError('BAD_REQUEST', '报告版本参数有误。')
          const file = await service.reportQueryFile(path[2]!, data.releaseId)
          response.writeHead(200, { 'Content-Type': 'application/pdf', 'Cache-Control': 'no-store', 'Content-Disposition': `inline; filename*=UTF-8''${encodeURIComponent(file.name)}` }); response.end(Buffer.from(file.base64, 'base64')); return
        }
        throw new AppError('NOT_FOUND', '报告查询接口不存在。')
      }
      if (path[0] === 'reports' && ['internal-changes', 'external-changes'].includes(path[1]!)) {
        const changes = createReportChanges({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, path[1] === 'external-changes' ? 'external' : 'internal')
        if (path.length === 4 && path[2] === 'handlers' && request.method === 'POST') {
          if (path[3] === 'query') { json(response, changes.queryHandlers(await body(request))); return }
          if (path[3] === 'validate') { json(response, changes.resolveHandler(await body(request))); return }
        }
        if (path.length === 3 && request.method === 'GET') { json(response, changes.detail(path[2]!)); return }
        if (request.method === 'POST') {
          const data = await body(request)
          if (path.length === 3 && path[2] === 'query') {
            if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
            json(response, changes.query(data)); return
          }
          if (path.length === 3 && path[2] === 'candidates') { json(response, changes.candidates(data)); return }
          if (path.length === 3 && path[2] === 'export') { const csv = changes.export(data); response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv); return }
          if (path.length === 2 || path.length === 4 && path[3] === 'save') {
            const id = path.length === 4 ? path[2]! : undefined
            const resolved = path[1] === 'external-changes' ? session.attachments.resolve(data, id ? changes.detail(id).external : undefined, data.attachmentDraftId, actor.id, 'external', id || '') : data
            const saved = changes.save(resolved, id)
            if (path[1] === 'external-changes' && typeof data.attachmentDraftId === 'string') session.attachments.discard(data.attachmentDraftId, actor.id, 'external', id || '')
            json(response, path[1] === 'external-changes' ? attachmentReferences(saved) : saved); return
          }
          if (path.length === 4 && path[3] === 'action') { json(response, changes.action(path[2]!, data)); return }
        }
        throw new AppError('NOT_FOUND', '报告更改申请接口不存在。')
      }
      if (path[0] === 'reports' && path[1] === 'lifecycle') {
        const lifecycle = createReportLifecycleService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } }, session.signingProvider)
        if (path.length === 3 && path[2] === 'query' && request.method === 'POST') { json(response, lifecycle.query(await body(request) as unknown as ReportLifecycleQuery)); return }
        if (path.length === 3 && ['print-query', 'signing-query', 'distribution-query', 'archive-query'].includes(path[2]!) && request.method === 'POST') {
          const mode = path[2] === 'archive-query' ? 'archive' : path[2] === 'distribution-query' ? 'distribution' : path[2] === 'signing-query' ? 'signing' : 'print'
          const query = parseReportPrintQuery(await body(request), mode)
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, lifecycle.printList({ ...query }, false, mode)); return
        }
        if (path.length === 3 && ['print-export', 'signing-export', 'distribution-export', 'archive-export'].includes(path[2]!) && request.method === 'POST') {
          const mode = path[2] === 'archive-export' ? 'archive' : path[2] === 'distribution-export' ? 'distribution' : path[2] === 'signing-export' ? 'signing' : 'print'
          const columns = mode === 'archive' ? reportArchiveColumns : mode === 'distribution' ? reportDistributionColumns : mode === 'print' ? reportPrintColumns : reportSigningColumns
          const rows = lifecycle.printList(await body(request), true, mode).items
          response.setHeader('Content-Type', 'text/csv;charset=utf-8')
          response.end(registrationCsv([columns.map(column => column.label), ...rows.map(row => columns.map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], column)))])); return
        }
        if (path.length === 4 && ['distribution-detail', 'pricing-detail'].includes(path[3]!) && request.method === 'POST') {
          const data = await body(request)
          if (!Number.isSafeInteger(data.version) || typeof data.releaseId !== 'string') throw new AppError('BAD_REQUEST', '报告版本参数有误。')
          json(response, path[3] === 'pricing-detail' ? lifecycle.pricingDetail(path[2]!, data.version as number, data.releaseId) : lifecycle.distributionDetail(path[2]!, data.version as number, data.releaseId)); return
        }
        if (path.length === 4 && path[3] === 'action' && request.method === 'POST') { json(response, lifecycle.action(path[2]!, await body(request))); return }
        if (path.length === 4 && path[3] === 'change' && request.method === 'POST') { json(response, lifecycle.requestChange(path[2]!, await body(request))); return }
        if (path.length === 4 && path[3] === 'progress' && request.method === 'GET') { json(response, lifecycle.progress(path[2]!)); return }
        if (path.length === 4 && path[3] === 'file' && request.method === 'POST') {
          const data = await body(request)
          if (typeof data.releaseId !== 'string' || !['preview', 'print', 'download', 'print-report'].includes(String(data.operation))) throw new AppError('BAD_REQUEST', '文件请求格式有误。')
          const file = lifecycle.file(path[2]!, data.releaseId, data.operation as 'preview' | 'print' | 'download' | 'print-report')
          response.setHeader('Content-Type', 'application/pdf'); response.setHeader('Cache-Control', 'no-store')
          response.setHeader('Content-Disposition', `inline; filename*=UTF-8''${encodeURIComponent(file.name)}`)
          response.end(Buffer.from(file.base64, 'base64')); return
        }
        throw new AppError('NOT_FOUND', '报告接口不存在。')
      }
      if (path[0] === 'samples' && path[2] === 'data-entry') {
        const entry = createDataEntryService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        const id = path[1]!
        if (path[3] === 'original-records') {
          const originals = createOriginalRecordService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
          if (path.length === 4 && request.method === 'GET') { json(response, originals.listing(id)); return }
          if (path.length === 5 && path[4] === 'preview' && request.method === 'GET') {
            const result = await originals.preview(id, Number(new URL(request.url!, 'http://localhost').searchParams.get('version')))
            response.writeHead(200, { 'Content-Type': 'application/pdf', 'Cache-Control': 'no-store', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(result.file.name)}`, 'X-Content-Type-Options': 'nosniff' }); response.end(Buffer.from(result.file.dataUrl.split(',')[1]!, 'base64')); return
          }
          if (path.length === 6 && path[4] === 'eln' && path[5] === 'query' && request.method === 'POST') { json(response, originals.elnQuery(id, await body(request))); return }
          if (path.length === 5 && request.method === 'POST') { const input = await body(request); json(response, path[4] === 'link' || path[4] === 'update-eln' ? await originals.importEln(id, path[4], input) : originals.mutate(id, path[4]!, input)); return }
          if (path.length === 5 && request.method === 'GET') { json(response, originals.detail(id, path[4]!)); return }
          if (path.length === 6 && path[5] === 'eln' && request.method === 'GET') { json(response, originals.live(id, path[4]!)); return }
          if (path.length === 6 && path[5] === 'eln-page' && request.method === 'GET') {
            const live = originals.live(id, path[4]!), escape = (value: string) => value.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]!))
            response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'none'; sandbox" })
            response.end(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>ELN 演示页面</title><body><h1>${escape(live.name)}</h1><p>模拟 ELN 页面，尚未连接外部系统。</p><p>版本 ${escape(live.version)} · ${escape(live.updatedAt)}</p><dl>${live.fields.map(field => `<dt>${escape(field.label)}</dt><dd>${escape(field.value)}</dd>`).join('')}</dl></body></html>`); return
          }
          if (path.length === 7 && path[5] === 'files' && request.method === 'GET') {
            const file = originals.file(id, path[4]!, path[6]!)
            response.writeHead(200, { 'Content-Type': file.type, 'Cache-Control': 'no-store', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(file.name)}`, 'X-Content-Type-Options': 'nosniff' }); response.end(Buffer.from(file.dataUrl.split(',')[1]!, 'base64')); return
          }
          throw new AppError('NOT_FOUND', '原始记录接口不存在。')
        }
        if (path.length === 3 && request.method === 'GET') { json(response, entry.detail(id)); return }
        if (path.length === 5 && path[3] === 'people' && request.method === 'POST' && ['query', 'validate'].includes(path[4]!)) { const input = await body(request); json(response, path[4] === 'query' ? entry.people(id, input) : entry.resolvePerson(id, input)); return }
        if (path.length === 5 && path[3] === 'template-tasks' && request.method === 'GET') { json(response, entry.taskStatus(id, path[4]!)); return }
        if (path.length === 5 && path[3] === 'records' && path[4] === 'query' && request.method === 'POST') { json(response, entry.records(id, await body(request))); return }
        if (path.length === 4 && request.method === 'POST') { json(response, entry.mutate(id, path[3]!, await body(request))); return }
        if (path.length === 5 && path[3] === 'files' && request.method === 'GET') {
          const file = entry.file(id, path[4]!)
          response.writeHead(200, { 'Content-Type': file.type, 'Cache-Control': 'no-store', 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(file.name)}`, 'X-Content-Type-Options': 'nosniff' }); response.end(Buffer.from(file.dataUrl.split(',')[1]!, 'base64')); return
        }
        if (path.length === 6 && request.method === 'GET' && (path[3] === 'template-tasks' && ['word', 'pdf'].includes(path[5]!) || path[3] === 'report-tasks' && path[5] === 'pdf')) {
          const taskId = path[4]!, word = path[5] === 'word', template = path[3] === 'template-tasks'
          const detail = entry.taskResult(id, taskId, template ? word ? 'word' : 'pdf' : 'final')
          if (!word && !session.entryPdfs.has(taskId)) {
            if (session.entryPdfs.size >= 20) session.entryPdfs.delete(session.entryPdfs.keys().next().value!)
            session.entryPdfs.set(taskId, entryPdf(detail, template).catch(error => { session.entryPdfs.delete(taskId); throw error }))
          }
          const file = word ? entryWord(detail, entry.taskStatus(id, taskId).kind === 'complete-report') : await session.entryPdfs.get(taskId)!
          entry.taskResult(id, taskId, template ? word ? 'word' : 'pdf' : 'final')
          response.writeHead(200, { 'Content-Type': word ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' : 'application/pdf', 'Cache-Control': 'no-store', 'Content-Disposition': `attachment; filename="report.${word ? 'docx' : 'pdf'}"` }); response.end(file); return
        }
        throw new AppError('NOT_FOUND', '数据录入接口不存在。')
      }
      if (path[0] === 'samples' && path[2] === 'task-processing-records') {
        const records = createTaskProcessingService({ actor: () => actor, read: () => session.state, write: state => { session.state = state } })
        if (path.length === 4 && path[3] === 'query' && request.method === 'POST') { json(response, records.query(path[1]!, await body(request))); return }
        if (path.length === 3 && request.method === 'POST') { json(response, records.create(path[1]!, await body(request))); return }
        if (path.length === 4 && request.method === 'GET') { json(response, records.detail(path[1]!, path[3]!)); return }
        if (path.length === 5 && path[4] === 'attachments' && request.method === 'GET') { json(response, records.attachments(path[1]!, path[3]!)); return }
        if (path.length === 5 && path[4] === 'attachments' && request.method === 'POST') { json(response, records.attachmentAction(path[1]!, path[3]!, await body(request))); return }
        if (path.length === 6 && path[4] === 'attachments' && request.method === 'DELETE') { json(response, records.attachmentAction(path[1]!, path[3]!, await body(request), path[5]!)); return }
        throw new AppError('NOT_FOUND', '处理记录接口不存在。')
      }
      if (path.length === 2 && path[0] === 'commissions' && path[1] === 'defaults' && request.method === 'GET') { json(response, await service.commissionDefaults()); return }
      if (path[0] === 'samples' && ['task-prints', 'task-print-context'].includes(path[2]!)) {
        // Read the request before taking the source snapshot so a slow upload cannot bypass a newer version or void state.
        const input = path[2] === 'task-prints' && path.length === 3 && request.method === 'POST' ? await body(request) : undefined
        const source = await service.taskPrintSource(path[1]!)
        if (path[2] === 'task-print-context' && path.length === 3 && request.method === 'GET') { const { snapshot, submittedBy, ...context } = source; json(response, context); return }
        if (path[2] !== 'task-prints') throw new AppError('NOT_FOUND', '接口不存在。')
        if (path.length === 3 && request.method === 'POST') { json(response, session.taskPrints.submit(source, input!), 202); return }
        if (path.length === 3 && request.method === 'GET') {
          const page = Number(url.searchParams.get('page') || 1), pageSize = Number(url.searchParams.get('pageSize') || 5)
          if (!Number.isSafeInteger(page) || page < 1 || ![5, 10, 20].includes(pageSize)) throw new AppError('BAD_REQUEST', '分页参数有误。')
          json(response, session.taskPrints.list(source, page, pageSize)); return
        }
        if (path.length === 4 && request.method === 'GET') { json(response, session.taskPrints.get(path[3]!, source)); return }
        if (path.length === 5 && path[4] === 'pdf' && request.method === 'GET') {
          const pdf = await session.taskPrints.pdf(path[3]!, source)
          await service.taskPrintSource(path[1]!)
          response.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Disposition': 'inline; filename="task.pdf"', 'Cache-Control': 'no-store' }); response.end(pdf); return
        }
        throw new AppError('NOT_FOUND', '接口不存在。')
      }
      if (['commissions', 'samples'].includes(path[0]) && ['prints', 'print-context'].includes(path[2])) {
        const source = await service.printSource(path[0] as RegistrationKind, path[1])
        if (path[2] === 'print-context' && path.length === 3 && request.method === 'GET') { const { preview, ...context } = source; json(response, context); return }
        if (path[2] !== 'prints') throw new AppError('NOT_FOUND', '接口不存在。')
        if (path.length === 3 && request.method === 'POST') { json(response, session.prints.submit(source, await body(request)), 202); return }
        if (path.length === 3 && request.method === 'GET') {
          const page = Number(url.searchParams.get('page') || 1), pageSize = Number(url.searchParams.get('pageSize') || 5)
          if (!Number.isSafeInteger(page) || page < 1 || ![5, 10, 20].includes(pageSize)) throw new AppError('BAD_REQUEST', '分页参数有误。')
          json(response, session.prints.list(source, page, pageSize)); return
        }
        if (path.length === 4 && request.method === 'GET') { json(response, session.prints.get(path[3], source)); return }
        if (path.length === 5 && path[4] === 'pdf' && request.method === 'GET') {
          const pdf = await session.prints.pdf(path[3], source)
          response.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Disposition': 'inline; filename="commission.pdf"', 'Cache-Control': 'no-store' }); response.end(pdf); return
        }
        throw new AppError('NOT_FOUND', '接口不存在。')
      }
      if (path[0] === 'manufacturers' && path[1] === 'query' && path.length === 2 && request.method === 'POST') {
        const input = await body(request)
        const { page, pageSize } = parseRegistrationQuery({ page: input.page, pageSize: input.pageSize }, 'commissions')
        const query: ManufacturerQuery = { page, pageSize }
        for (const key of ['code', 'name', 'type'] as const) {
          if (input[key] === undefined) continue
          if (typeof input[key] !== 'string' || input[key].length > 200) throw new AppError('BAD_REQUEST', '厂家查询条件格式有误。')
          query[key] = input[key].trim()
        }
        json(response, await service.manufacturers(query)); return
      }
      if (path[0] === 'organizations' && path[1] === 'query' && path.length === 2 && request.method === 'POST') {
        const input = await body(request)
        if (input.keyword !== undefined && (typeof input.keyword !== 'string' || input.keyword.length > 500)) throw new AppError('BAD_REQUEST', '单位名称查询格式有误。')
        const { page, pageSize } = parseRegistrationQuery({ ...input, keyword: undefined }, 'commissions')
        json(response, await service.organizations({ keyword: typeof input.keyword === 'string' ? input.keyword.trim() : '', page, pageSize })); return
      }
      if (path[0] === 'contracts' && path[1] === 'query' && path.length === 2 && request.method === 'POST') {
        json(response, await service.contracts(parseContractQuery(await body(request)))); return
      }
      if (path[0] === 'test-plans' && path[1] === 'selection' && path.length === 2 && request.method === 'POST') {
        const input = await body(request)
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        json(response, await service.testPlanSelection(input.selection, input.toggle, input.sampleScope)); return
      }
      if (path[0] === 'test-plans' && path[1] === 'query' && path.length === 2 && request.method === 'POST') {
        const input = await body(request)
        if (input.parentId !== undefined && (typeof input.parentId !== 'string' || input.parentId.length > 100)) throw new AppError('BAD_REQUEST', '检测方案分组格式有误。')
        const { keyword, page, pageSize } = parseRegistrationQuery(input, 'samples')
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        json(response, await service.testPlans({ parentId: input.parentId as string | undefined, keyword, page, pageSize })); return
      }
      if (path[0] === 'test-bases' && path.length === 2 && request.method === 'POST') {
        const input = await body(request), query = parseTestBasisQuery(input)
        if (path[1] === 'query') { json(response, await service.testBases(query)); return }
        if (path[1] === 'resolve') {
          if (input.englishBookMarks !== undefined && typeof input.englishBookMarks !== 'boolean') throw new AppError('BAD_REQUEST', '书名号格式选项有误。')
          json(response, await service.resolveTestBases(query.planId, parseTestBasisIds(input.ids), input.englishBookMarks === true, input.separators)); return
        }
      }
      const kind = path[0] as RegistrationKind
      if (!['commissions', 'samples'].includes(kind)) throw new AppError('NOT_FOUND', '接口不存在。')
      if (kind === 'samples' && path[1] === 'bulk-commission' && request.method === 'POST') {
        const data = await body(request)
        if (path.length === 3 && path[2] === 'context') { json(response, await service.bulkCommissionContext(parseIds(data.ids), parseWorkspace(data.workspace))); return }
        if (path.length === 3 && path[2] === 'source') { json(response, await service.bulkCommissionSource(parseIds(data.ids), parseWorkspace(data.workspace))); return }
        if (path.length === 2) { json(response, await service.saveBulkCommission(data.targets as import('../src/types/commissions/bulkCommission').BulkCommissionTarget[], object(data.changes), parseWorkspace(data.workspace))); return }
      }
      if (kind === 'samples' && path[1] === 'report-settings-config' && path.length === 2 && request.method === 'GET') { json(response, await service.reportSettingsConfig()); return }
      if (kind === 'samples' && path[1] === 'defaults' && path.length === 2 && request.method === 'GET') { json(response, await service.sampleDefaults()); return }
      if (request.method === 'POST' && path.length === 2 && ['query', 'export'].includes(path[1])) {
        const data = await body(request), query = parseRegistrationQuery(data, kind), workspace = parseWorkspace(data.workspace)
        if (path[1] === 'export') {
          const blob = await service.export(kind, query, workspace)
          response.writeHead(200, { 'Content-Type': blob.type, 'Content-Disposition': `attachment; filename="${kind}.csv"`, 'Cache-Control': 'no-store' }); response.end(Buffer.from(await blob.arrayBuffer())); return
        }
        if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
        const result = kind === 'commissions' ? await service.commissions(query) : await service.samples(query, workspace)
        json(response, { ...result, items: kind === 'commissions' ? (result.items as RegistrationCommission[]).map(row => summaryCommission(row, session.state.samples.filter(sample => sample.commissionId === row.id).length)) : (result.items as (RegistrationSample & { commissionCode: string; commissionName: string })[]).map(workspace === 'query' ? summaryInquirySample : summarySample) }); return
      }
      if (kind === 'commissions' && path.length === 3 && path[2] === 'summary' && request.method === 'GET') { json(response, summaryCommission(await service.commission(path[1]), session.state.samples.filter(sample => sample.commissionId === path[1]).length)); return }
      if (path.length === 2 && request.method === 'GET') { json(response, kind === 'commissions' ? await service.commission(path[1]) : await service.sample(path[1])); return }
      if (path.length === 1 && request.method === 'POST' || path.length === 2 && request.method === 'PUT') {
        const data = await body(request), input = parseInput(data.input, kind), id = path[1], version = data.version as number | undefined
        if (kind === 'samples' && data.reportConfigVersion !== undefined && (typeof data.reportConfigVersion !== 'string' || data.reportConfigVersion.length > 100)) throw new AppError('BAD_REQUEST', '报告配置版本格式有误。')
        json(response, kind === 'commissions' ? await service.saveCommission(input as unknown as RegistrationCommissionInput, id, version, parseWorkspace(data.workspace)) : await service.saveSample(input as unknown as RegistrationSampleInput, id, version, data.reportConfigVersion as string | undefined, parseWorkspace(data.workspace))); return
      }
      if (kind === 'samples' && path[1] === 'cancellation-approvals' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseCancellationQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.cancellationApprovals(query))
        } else {
          response.setHeader('Content-Type', 'text/csv; charset=utf-8')
          response.end(await service.exportCancellationApprovals(query))
        }
        return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'cancellation-approval' && request.method === 'POST') {
        json(response, await service.approveCancellation(path[1]!, await body(request))); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'task-return' && request.method === 'POST') {
        const data = await body(request)
        if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        json(response, await service.taskQueryReturn(path[1]!, Number(data.version), data.returned)); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'pickup-action' && request.method === 'POST') {
        const data = await body(request)
        if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        json(response, await service.pickupAction(path[1]!, Number(data.version), data.receipt)); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'assignment-action' && request.method === 'POST') {
        const data = await body(request)
        if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        if (data.action !== undefined && data.action !== 'assign' && data.action !== 'undo' && data.action !== 'auto') throw new AppError('BAD_REQUEST', '不支持的分配操作。')
        json(response, await service.assignmentAction(path[1]!, Number(data.version), data, data.action === 'auto' ? 'auto' : data.action === 'undo' ? 'undo' : 'assign')); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'sample-completion-action' && request.method === 'POST') {
        const data = await body(request)
        if (data.action !== 'process' && data.action !== 'undo') throw new AppError('BAD_REQUEST', '不支持的样品处理操作。')
        if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        json(response, await service.sampleCompletionAction(path[1]!, data.action, Number(data.version), data.result)); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'disposal-action' && request.method === 'POST') {
        const data = await body(request)
        if (data.action !== 'dispose' && data.action !== 'undo') throw new AppError('BAD_REQUEST', '不支持的处置操作。')
        if (!Number.isSafeInteger(data.version) || Number(data.version) < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        json(response, await service.disposalAction(path[1]!, data.action, Number(data.version), data.receipt)); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'inbound-action' && request.method === 'POST') {
        const data = await body(request)
        if (data.action !== 'receive' && data.action !== 'undo') throw new AppError('BAD_REQUEST', '不支持的入库操作。')
        if (typeof data.version !== 'number' || !Number.isSafeInteger(data.version) || data.version < 1) throw new AppError('BAD_REQUEST', '样品版本格式有误。')
        json(response, await service.inboundAction(path[1]!, data.action, data.version, data.receipt)); return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'outbound-action' && request.method === 'POST') {
        const data = await body(request)
        if (data.action !== 'dispatch' && data.action !== 'undo' && data.action !== 'return') throw new AppError('BAD_REQUEST', '不支持的出库操作。')
        if (typeof data.version !== 'number' || !Number.isSafeInteger(data.version) || data.version < 1) throw new AppError('BAD_REQUEST', '样品版本格式有误。')
        json(response, await service.outboundAction(path[1]!, data.action, data.version, data.action === 'return' ? data.returned : data.receipt)); return
      }
      if (kind === 'samples' && path[2] === 'report-check-recipients' && path.length === 4 && ['query', 'resolve'].includes(path[3]!) && request.method === 'POST') {
        const data = await body(request)
        json(response, await service.reportCheckRecipients(path[1]!, data, path[3] === 'resolve', parseReportStage(data.stage))); return
      }
      if (kind === 'samples' && path[2] === 'report-compliance-check' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (typeof data.version !== 'number') throw new AppError('BAD_REQUEST', '报告校验请求格式有误。')
        json(response, await service.reportComplianceCheck(path[1]!, data.version, parseReportStage(data.stage))); return
      }
      if (kind === 'samples' && path[2] === 'report-void-action' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (typeof data.version !== 'number') throw new AppError('BAD_REQUEST', '记录版本有误。')
        json(response, await service.reportVoidAction(path[1]!, data.version, data.reason, parseReportStage(data.stage))); return
      }
      if (kind === 'samples' && path[2] === 'report-check-action' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (typeof data.action !== 'string' || typeof data.version !== 'number') throw new AppError('BAD_REQUEST', '报告校核请求格式有误。')
        json(response, await service.reportCheckAction(path[1]!, data.action, data.version, data.confirmation, data.rejection, parseReportStage(data.stage))); return
      }
      if (kind === 'samples' && path[2] === 'data-check-action' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (typeof data.action !== 'string' || typeof data.version !== 'number') throw new AppError('BAD_REQUEST', '校核请求格式有误。')
        json(response, await service.dataCheckAction(path[1]!, data.action, data.version)); return
      }
      if (kind === 'samples' && path[2] === 'complete-data-change' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (!Number.isSafeInteger(data.version)) throw new AppError('BAD_REQUEST', '更改请求版本有误。')
        json(response, await service.completeDataChange(path[1]!, data.version as number, data.acknowledgeMissingOriginals === true)); return
      }
      if (kind === 'samples' && path[1] === 'sample-completion' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseSampleCompletionQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.sampleCompletionSamples(query))
        } else {
          const csv = await service.exportSampleCompletionSamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'data-changes' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseDataChangeQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.dataChanges(query))
        } else {
          const csv = await service.exportDataChanges(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'data-query' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseDataQueryQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.dataQuerySamples(query))
        } else {
          const csv = await service.exportDataQuerySamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[2] === 'copy' && path.length === 3 && request.method === 'POST') {
        json(response, await service.copySample(path[1]!, await body(request))); return
      }
      if (kind === 'samples' && path[1] === 'sample-copy' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseSampleCopyQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.sampleCopySamples(query))
        } else {
          const csv = await service.exportSampleCopySamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'report-check' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const input = await body(request), stage = parseReportStage(input.stage), query = parseReportCheckQuery(input, stage)
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.reportCheckSamples(query, stage))
        } else {
          const csv = await service.exportReportCheckSamples(query, stage)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' }); response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'data-check' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseDataCheckQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.dataCheckSamples(query))
        } else {
          const csv = await service.exportDataCheckSamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'data-entry' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseDataEntryQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.dataEntrySamples(query))
        } else {
          const csv = await service.exportDataEntrySamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'task-query' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseTaskQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.taskQuerySamples(query))
        } else {
          const csv = await service.exportTaskQuerySamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'pickup' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parsePickupQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.pickupSamples(query))
        } else {
          const csv = await service.exportPickupSamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'assignment' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseAssignmentQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.assignmentSamples(query))
        } else {
          const csv = await service.exportAssignmentSamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && path[1] === 'flow' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseFlowQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.flowSamples(query))
        }
        else {
          const csv = await service.exportFlowSamples(query)
          response.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Cache-Control': 'no-store' })
          response.end(csv)
        }
        return
      }
      if (kind === 'samples' && ['inbound', 'outbound', 'disposal'].includes(path[1]!) && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const outbound = path[1] === 'outbound', disposal = path[1] === 'disposal'
        const query = (disposal ? parseDisposalQuery : outbound ? parseOutboundQuery : parseInboundQuery)(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await (disposal ? service.disposalSamples(query) : outbound ? service.outboundSamples(query) : service.inboundSamples(query)))
        } else {
          response.setHeader('Content-Type', 'text/csv; charset=utf-8')
          response.end(await (disposal ? service.exportDisposalSamples(query) : outbound ? service.exportOutboundSamples(query) : service.exportInboundSamples(query)))
        }
        return
      }
      if (kind === 'samples' && path[1] === 'changes' && path.length === 3 && ['query', 'export'].includes(path[2]!) && request.method === 'POST') {
        const query = parseCommissionChangeQuery(await body(request))
        if (path[2] === 'query') {
          if (!await waitForQuery(response, options.queryDelayMs ?? registrationQueryDelayMs)) return
          json(response, await service.sampleChanges(query))
        } else {
          response.setHeader('Content-Type', 'text/csv; charset=utf-8')
          response.end(await service.exportSampleChanges(query))
        }
        return
      }
      if (kind === 'samples' && path[1] === 'report-batch' && path.length === 3 && request.method === 'POST') {
        const data = await body(request), stage = parseReportStage(data.stage)
        if (path[2] === 'context') json(response, await service.reportBatchContext(data.ids, stage))
        else if (path[2] === 'check') json(response, await service.reportBatchCheck(data.targets, stage))
        else if (path[2] === 'submit') json(response, await service.reportBatchSubmit(data.targets, data.action, data.confirmation, data.checks, data.rejection, stage))
        else throw new AppError('NOT_FOUND', '接口不存在。')
        return
      }
      if (kind === 'samples' && path[1] === 'batch-review' && path.length === 3 && request.method === 'POST') {
        const data = await body(request)
        if (path[2] === 'start') json(response, await service.startBatchReview(data.targets))
        else if (path[2] === 'context') json(response, await service.batchReviewContext(data.ids))
        else if (path[2] === 'check') json(response, await service.batchReviewCheck(data.targets, data.reviewOptions))
        else if (path[2] === 'submit') json(response, await service.submitBatchReview(data.targets, data.review, data.checks))
        else throw new AppError('NOT_FOUND', '接口不存在。')
        return
      }
      if (kind === 'samples' && path.length === 3 && path[2] === 'review-check' && request.method === 'POST') {
        const data = await body(request)
        if (typeof data.version !== 'number' || !Number.isSafeInteger(data.version) || data.version < 1) throw new AppError('BAD_REQUEST', '样品版本格式有误。')
        json(response, await service.reviewCheck(path[1]!, data.version, data.reviewOptions)); return
      }
      if (path.length === 3 && path[2] === 'actions' && request.method === 'POST') {
        const data = await body(request)
        json(response, await service.act(kind, path[1], String(data.actionId), Number(data.version), typeof data.reason === 'string' ? data.reason : '', data.review)); return
      }
      if (path.length === 3 && path[2] === 'attachments' && request.method === 'GET') { json(response, await service.attachments(path[1], kind)); return }
      if (path.length === 3 && path[2] === 'attachments' && request.method === 'POST') { const data = await body(request); json(response, await service.attach(path[1], Number(data.version), object(data.file) as unknown as Omit<DemoAttachment, 'id'>, kind, parseWorkspace(data.workspace))); return }
      if (path.length === 4 && path[2] === 'attachments' && request.method === 'DELETE') { const data = await body(request); json(response, await service.deleteAttachment(path[1], Number(data.version), path[3], kind, parseWorkspace(data.workspace))); return }
      throw new AppError('NOT_FOUND', '接口不存在。')
    })().catch(error => {
      const issue = error instanceof AppError ? error : new AppError('INTERNAL', '模拟服务暂时不可用。')
      if (!response.headersSent) json(response, { error: { code: issue.code, message: issue.message, fieldErrors: issue.fieldErrors, diagnosticId: issue.diagnosticId } }, issue.status ?? 500)
      else response.end()
    })
  }
  return Object.assign(middleware, { dispose: () => { clearInterval(workerTimer); sessions.clear() } })
}
export function registrationMockApi(): Plugin {
  const queryDelayMs = Number(process.env.LIMS_MOCK_QUERY_DELAY_MS ?? registrationQueryDelayMs)
  if (!Number.isFinite(queryDelayMs) || queryDelayMs < 0 || queryDelayMs > 30000) throw new Error('LIMS_MOCK_QUERY_DELAY_MS 必须为 0 至 30000 的毫秒数。')
  const middleware = createRegistrationMiddleware({ queryDelayMs })
  return { name: 'registration-mock-api', configureServer(server) { server.middlewares.use(middleware); server.httpServer?.once('close', middleware.dispose) }, configurePreviewServer(server) { server.middlewares.use(middleware); server.httpServer?.once('close', middleware.dispose) } }
}

