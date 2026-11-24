import { reportCollectionMethod, reportDistributionStates, type ReportDistributionDetail } from '../src/types/reports/reportDistribution'
import type { ReportPricingDetail } from '../src/types/reports/reportPricing'
import { randomUUID, createHash } from 'node:crypto'
import { PDFDocument } from 'pdf-lib'
import { AppError } from '../src/services/common/errors'
import type { Actor } from '../src/types/lims'
import type { RegistrationDependencies, RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import { reportOperationLabels, type ReportForm, type ReportRelease, type ReportLifecycleRow, type ReportLifecycleQuery, type ReportOperation, type SigningConfig, type SigningStatus } from '../src/types/reports/reportLifecycle'
import { createDataEntryService } from './dataEntryDetail'
import { entryPdf } from './dataEntryDocuments'
import { reportFile, type SigningProvider, type SigningResult } from './reportSigning'
import { parseReportPrintQuery } from './reportPrint'
import { dataEntryRows } from './testingDataEntry'
import { resolvePlanSelection } from './testPlanSelection'
import { summarySample } from './registrationSummary'
import { reportSigningStates } from '../src/types/reports/reportSigning'
import { reportPrintStates, type ReportPrintRow } from '../src/types/reports/reportPrint'

export interface ReportLifecycleConfig {
  signing: (sample: RegistrationSample, actor: Actor) => SigningConfig | undefined
  signingProviders?: readonly string[]
  price?: (sample: RegistrationSample) => { amount: number; rule: string }
  distributionFinance?: (sample: RegistrationSample) => Pick<ReportDistributionDetail, 'receivedAmount' | 'contractBalance' | 'availableCredit'>
}
export const demoLifecycleConfig: ReportLifecycleConfig = {
  signingProviders: ['demo'],
  signing: (sample, actor) => ({ provider: 'demo', sealId: `${sample.departmentId}-demo-seal`, signers: [sample.reportReviewInfo?.actorId || 'reviewer', actor.id], positions: [{ kind: 'signature', page: 1, x: 40, y: 60 }, { kind: 'seal', page: 1, x: 400, y: 60 }] }),
}
const fail = (message: string): never => { throw new AppError('BUSINESS_RULE', message) }
export function reportForm(sample: RegistrationSample): ReportForm {
  const value = sample.details?.reportForm || '纸质'
  if (value !== '纸质' && value !== '电子') fail('原报告形式为纸质及电子，请明确选择一种形式；已批准报告需通过报告更改处理。')
  return value as ReportForm
}
export const hasApprovedReport = (sample: RegistrationSample) => !!sample.reportRelease || !!sample.reportApprovalInfo && sample.reportApprovalInfo.nextAction !== 'transfer'
export const isReportPrintSample = (sample: RegistrationSample) => sample.status === 'completed' && hasApprovedReport(sample) && !['委托更改中', '检测更改中'].includes(sample.dataStatus) && !sample.reportRelease?.supersededAt && (sample.reportRelease?.form || sample.details?.reportForm || '纸质') === '纸质'
export const isReportSigningSample = (sample: RegistrationSample) => sample.status === 'completed' && hasApprovedReport(sample) && !['委托更改中', '检测更改中'].includes(sample.dataStatus) && !sample.reportRelease?.supersededAt && (sample.reportRelease?.form || sample.details?.reportForm || '纸质') === '电子'
export const isReportArchiveSample = (sample: RegistrationSample) => isReportDistributionSample(sample) && sample.reportRelease?.distributionStatus === '已发放'
export const isReportDistributionSample = (sample: RegistrationSample) => isReportPrintSample(sample) || isReportSigningSample(sample)
const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex')
export const approvalSource = (state: RegistrationState, sample: RegistrationSample) => {
  const { version: _sampleVersion, ...content } = sample
  const entry = state.dataEntries?.[sample.id]
  const { version: _entryVersion, ...entryContent } = entry || {}
  // Record counters do not block submission; generated files still need matching content.
  return digest([content, entry ? entryContent : undefined])
}
export async function prepareReportRelease(state: RegistrationState, sample: RegistrationSample, actor: Actor, config = demoLifecycleConfig) {
  if (sample.reportRelease && !sample.reportRelease.supersededAt) fail('报告已批准，不允许重复批准。')
  const form = reportForm(sample), signingConfig = form === '电子' ? config.signing(sample, actor) : undefined
  if (form === '电子' && (!signingConfig?.provider || !signingConfig.sealId || !signingConfig.signers.length || signingConfig.signers.some(id => !id) || !['signature', 'seal'].every(kind => signingConfig.positions.some(p => p.kind === kind && Number.isSafeInteger(p.page) && p.page > 0 && Number.isFinite(p.x) && p.x >= 0 && Number.isFinite(p.y) && p.y >= 0)))) fail('电子签章的人员、印章或位置配置不完整，不能批准。')
  if (signingConfig && !(config.signingProviders || ['demo']).includes(signingConfig.provider)) fail('签章服务商尚未配置，不能批准。')
  const service = createDataEntryService({ actor: () => actor, read: () => state }), detail = service.detail(sample.id)
  if (detail.template.error || detail.reportStatus !== 'ready' || !detail.job) fail('最新最终报告尚未生成，请先完成报告文件。')
  const source = approvalSource(state, sample), id = randomUUID(), at = new Date().toISOString()
  const sourceTaskId = detail.job!.id
  const bytes = await entryPdf(service.taskResult(sample.id, sourceTaskId, 'final'))
  if (signingConfig) {
    const pages = (await PDFDocument.load(bytes)).getPages()
    if (signingConfig.positions.some(position => !pages[position.page - 1] || position.x > pages[position.page - 1]!.getWidth() || position.y > pages[position.page - 1]!.getHeight())) fail('签章位置超出最终报告页面范围。')
  }
  const release: ReportRelease = {
    id, revision: Math.max(detail.reportRevision, ...(sample.reportReleaseHistory || []).map(item => item.revision + 1)), form,
    approvedAt: at, approvedBy: { id: actor.id, name: actor.name }, sourceTaskId,
    people: { checker: sample.reportCheckInfo?.actorName || '', reviewer: sample.reportReviewInfo?.actorName || '', approver: actor.name },
    original: reportFile(bytes, `${id}-original`, `${sample.reportCode || sample.code}.pdf`),
    ...(signingConfig ? { signingConfig: structuredClone(signingConfig), signing: { id: randomUUID(), key: `${id}:1`, attempt: 1, status: '待签章' as const, signature: '待处理' as const, seal: '待处理' as const, updatedAt: at, events: [{ at, status: '待签章' as const, message: '批准完成，自动进入签章队列。' }] } } : {}),
    printStatus: form === '纸质' ? '待打印' : '不适用', distributionStatus: '未发放', archiveStatus: '待归档', history: [],
  }
  return { source, release }
}
export function commitReportRelease(state: RegistrationState, sample: RegistrationSample, prepared: Awaited<ReturnType<typeof prepareReportRelease>>) {
  if (approvalSource(state, sample) !== prepared.source) throw new AppError('BUSINESS_RULE', '报告资料在批准期间发生变化，请重新核验。')
  sample.reportRelease = prepared.release
}
export function supersedeReportRelease(sample: RegistrationSample, actor: Actor, reason: string) {
  if (!sample.reportRelease) return
  const release = sample.reportRelease
  release.supersededAt = new Date().toISOString()
  release.history.push({ at: release.supersededAt, actorId: actor.id, actorName: actor.name, action: '报告版本被替代', reason })
  ;(sample.reportReleaseHistory ??= []).push(release)
  delete sample.reportRelease
}
const valid = (sample: RegistrationSample) => sample.status === 'completed' && hasApprovedReport(sample) && !['委托更改中', '检测更改中'].includes(sample.dataStatus) && !!sample.reportRelease && !sample.reportRelease.supersededAt
const visible = (actor: Actor, sample: RegistrationSample) => actor.scope === 'all' || actor.departmentId === sample.departmentId
const hasRole = (actor: Actor, roles: string[]) => actor.roles.some(role => ['admin', ...roles].includes(role))

export function createReportLifecycleService(deps: RegistrationDependencies, provider: SigningProvider, config = demoLifecycleConfig) {
  const read = () => structuredClone(deps.read!()!)
  function actor() {
    if (deps.locked?.()) throw new AppError('LOCKED', '工作空间已锁定。')
    const current = deps.actor()
    if (!hasRole(current, ['reports', 'reviewer', 'approver', 'finance'])) throw new AppError('FORBIDDEN', '无权访问报告后续流程。')
    return current
  }
  function find(state: RegistrationState, id: string) {
    const a = actor(), sample = state.samples.find(row => row.id === id && visible(a, row))
    if (!sample) throw new AppError('NOT_FOUND', '报告不存在或不可访问。')
    return sample
  }
  function get(id: string, version?: number, releaseId?: string) {
    const state = read(), sample = find(state, id), release = sample.reportRelease
    if (releaseId !== undefined && release?.id !== releaseId) throw new AppError('BUSINESS_RULE', '报告已更新，请刷新后操作。')
    if (!valid(sample) || !release) fail('此报告未批准、正在更改或已作废，不能操作。')
    return { state, sample, release: release! }
  }
  function allowed(sample: RegistrationSample, operation: ReportOperation) {
    const r = sample.reportRelease, a = actor(), writable = hasRole(a, ['reports'])
    if (operation === 'attachments') return true
    if (!valid(sample) || !r) return false
    switch (operation) {
      case 'archive': return writable && isReportArchiveSample(sample) && r.archiveStatus === '待归档'
      case 'undo-archive': return writable && isReportArchiveSample(sample) && r.archiveStatus === '已归档'
      case 'print-report': return writable && isReportArchiveSample(sample) && (r.form === '纸质' || r.signing?.status === '签章完成' && !!r.signed)
      case 'print-task': case 'print-commission': return writable && isReportArchiveSample(sample)
      case 'preview': return true
      case 'print': return writable && r.form === '纸质'
      case 'download': return writable && r.form === '电子' && r.signing?.status === '签章完成' && !!r.signed
      case 'progress': return r.form === '电子'
      case 'retry': return writable && r.signing?.status === '签章失败'
      case 'complete-print': return writable && r.form === '纸质' && r.printStatus === '待打印' && r.distributionStatus === '未发放'
      case 'undo-print': return writable && r.printStatus === '打印完成' && r.distributionStatus === '未发放'
      case 'distribute': return writable && r.distributionStatus === '未发放' && (r.form === '纸质' ? r.printStatus === '打印完成' : r.signing?.status === '签章完成' && !!r.signed)
      case 'undo-distribute': return writable && r.distributionStatus === '已发放' && r.archiveStatus !== '已归档'
      case 'reprice': return hasRole(a, ['finance']) && r.archiveStatus !== '已归档'
    }
  }
  function event(sample: RegistrationSample, action: string, reason = '') {
    const a = actor(), at = new Date().toISOString(), r = sample.reportRelease!
    sample.version++; r.history.push({ at, actorId: a.id, actorName: a.name, action, reason })
    sample.events.push({ at, actor: a.name, action, reason: `报告版本 ${r.revision}：${reason}` })
  }
  function row(sample: RegistrationSample, queue: ReportLifecycleQuery['queue']): ReportLifecycleRow {
    const r = sample.reportRelease, form = r?.form || sample.details?.reportForm || '纸质'
    const menus: ReportOperation[] = queue === 'print' ? ['preview', 'print', 'attachments', 'complete-print', 'undo-print'] : queue === 'signing' ? ['preview', 'progress', 'retry', 'download', 'attachments'] : queue === 'archive' ? ['archive', 'undo-archive', 'print-report', 'print-task', 'print-commission'] : ['preview', form === '电子' ? 'download' : 'print', 'distribute', 'undo-distribute', 'reprice']
    return { id: sample.id, version: sample.version, releaseId: r?.id || '', code: sample.code, reportCode: sample.reportCode, name: sample.name, customer: sample.customer, testPlan: sample.details?.testPlan || '', form, revision: r?.revision || 0, approvedAt: r?.approvedAt || sample.reportApprovalInfo?.at || '', printStatus: r?.printStatus || '待确认', signingStatus: r?.signing?.status || (form === '纸质' ? '不适用' : '待确认'), distributionStatus: r?.distributionStatus || '待确认', archiveStatus: r?.archiveStatus || '待确认', recipient: r?.receipt?.recipient || '', distributionDate: r?.receipt?.date || '', actualPrice: sample.reportPricing?.amount ?? null,
      unavailableReason: !r ? '历史报告未建立文件快照，请通过报告更改核实，原历史记录保留。' : '',
      actions: menus.map(id => ({ id, label: reportOperationLabels[id], enabled: allowed(sample, id) })) }
  }
  function query(input: ReportLifecycleQuery) {
    const a = actor()
    if (!['print', 'signing', 'distribution', 'archive'].includes(input.queue)) throw new AppError('BAD_REQUEST', '无效报告列表。')
    for (const key of ['keyword', 'form', 'status', 'from', 'to'] as const) if (input[key] !== undefined && (typeof input[key] !== 'string' || input[key]!.length > 200)) throw new AppError('BAD_REQUEST', '查询条件格式有误。')
    if (input.form && !['纸质', '电子'].includes(input.form)) throw new AppError('BAD_REQUEST', '无效报告形式。')
    for (const value of [input.from, input.to]) if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new AppError('BAD_REQUEST', '无效日期。')
    if (input.from && input.to && input.from > input.to) throw new AppError('BAD_REQUEST', '结束日期不能早于开始日期。')
    const page = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (!Number.isSafeInteger(page) || page < 1 || ![10, 20, 50].includes(pageSize)) throw new AppError('BAD_REQUEST', '无效分页。')
    const rows = read().samples.filter(s => visible(a, s) && s.status === 'completed' && hasApprovedReport(s) && !['委托更改中', '检测更改中'].includes(s.dataStatus)).map(s => row(s, input.queue)).filter(r => {
      if (input.queue === 'print' && r.form !== '纸质' || input.queue === 'signing' && r.form !== '电子' || input.queue === 'archive' && r.distributionStatus !== '已发放') return false
      if (input.form && r.form !== input.form || input.keyword && ![r.code, r.reportCode, r.name, r.customer].some(v => v.toLowerCase().includes(input.keyword!.toLowerCase()))) return false
      const status = input.queue === 'print' ? r.printStatus : input.queue === 'signing' ? r.signingStatus : input.queue === 'distribution' ? r.distributionStatus : r.archiveStatus
      return (!input.status || status === input.status) && (!input.from || r.approvedAt.slice(0, 10) >= input.from) && (!input.to || r.approvedAt.slice(0, 10) <= input.to)
    }).sort((a, b) => a.code.localeCompare(b.code))
    return { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize }
  }
  function printList(input: Record<string, unknown>, all = false, mode: 'print' | 'signing' | 'distribution' | 'archive' = 'print') {
    const a = actor(), state = read(), query = parseReportPrintQuery(input, mode), selected = resolvePlanSelection(a, query.plans)
    const commissions = new Map(state.commissions.map(commission => [commission.id, commission]))
    const sources = state.samples.filter(sample => visible(a, sample) && (mode === 'archive' ? isReportArchiveSample(sample) : mode === 'distribution' ? isReportDistributionSample(sample) : mode === 'print' ? isReportPrintSample(sample) : isReportSigningSample(sample)) && (!selected.restricted || selected.ids.has(sample.details?.testPlanId || '')))
    const lookup = new Map(sources.map(sample => [sample.id, sample]))
    const samples = sources.map(sample => ({ ...sample, commissionCode: commissions.get(sample.commissionId)?.code || '', commissionName: commissions.get(sample.commissionId)?.name || sample.commissionInfo.name,
      dataStatus: mode === 'archive' ? sample.reportRelease?.archiveStatus === '已归档' ? '报告归档完成' : '报告发放完成' : mode === 'distribution' && sample.reportRelease?.distributionStatus === '已发放' ? '报告发放完成' : mode === 'signing' || mode === 'distribution' && sample.reportRelease?.form === '电子' ? sample.reportRelease?.signing?.status === '签章完成' ? '报告签章完成' : '报告签章中' : sample.reportRelease ? sample.reportRelease.printStatus === '打印完成' ? '报告打印完成' : '报告打印中' : sample.dataStatus }))
    const { dateField, searchField, ...baseFilters } = query
    const filters = { ...baseFilters, searchField: searchField === 'recipient' ? undefined : searchField, contains: searchField === 'recipient' ? undefined : query.contains }
    const rows = dataEntryRows(samples, dateField === 'approvalDate' || dateField === 'printDate' || dateField === 'distributionDate' || dateField === 'archiveDate' ? { ...filters, from: undefined, to: undefined } : { ...filters, dateField }, [...(mode === 'archive' ? [] : mode === 'distribution' ? reportDistributionStates : mode === 'print' ? reportPrintStates : reportSigningStates), ...samples.map(sample => sample.dataStatus)])
      .map((entry): ReportPrintRow => {
        const sample = lookup.get(entry.id)!, release = sample.reportRelease, prices = summarySample({ ...sample, commissionCode: entry.commissionCode, commissionName: entry.engineeringName })
        const printed = release?.printStatus === '打印完成' ? [...release.history].reverse().find(event => event.action === '打印完成') : undefined
        const date = (at: string | undefined) => at && Number.isFinite(Date.parse(at)) ? new Date(at).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) : ''
        return { ...entry, ...row(sample, mode), deliveryMethod: release?.receipt?.method || '', trackingNumber: release?.receipt?.trackingNumber || '', mailingAddress: release?.receipt?.mailingAddress ?? sample.details?.mailingAddress ?? '', signatureStatus: release?.signing?.signature || '', sealStatus: release?.signing?.seal || '', signingDate: release?.signing?.status === '签章完成' ? date(release.signing.updatedAt) : '', reportCopies: sample.details?.reportCopies || '', changeCount: sample.reportChangeCount ?? null,
          archivePerson: release?.archiveStatus === '已归档' ? release.archive?.actorName || '' : '', archiveDate: release?.archiveStatus === '已归档' ? release.archive?.date || '' : '',
          printPerson: printed?.actorName || '', printDate: date(printed?.at), approvalDate: date(release?.approvedAt) || sample.reportApprovalInfo?.date || date(sample.reportApprovalInfo?.at),
          paymentStatus: sample.details?.paymentStatus || '', priceAdjustmentStatus: sample.reportPricing ? '已调整' : '', standardPrice: prices.standardPrice, discountPrice: prices.discountPrice }
      }).filter(row => (searchField !== 'recipient' || !query.contains || row.recipient.toLocaleLowerCase().includes(query.contains.toLocaleLowerCase())) && (!query.collectionMethod || reportCollectionMethod(row.deliveryMethod || '') === query.collectionMethod) && (!query.form || row.form === query.form) && (!query.archiveStatus || row.archiveStatus === query.archiveStatus) && (!query.distributionStatus || row.distributionStatus === query.distributionStatus) && (!query.signingStatus || row.signingStatus === query.signingStatus) && (!query.printStatus || row.printStatus === (query.printStatus === '已打印' ? '打印完成' : '待打印')) && (!dateField || !['approvalDate', 'printDate', 'distributionDate', 'archiveDate'].includes(dateField) || (!query.from || !!row[dateField] && row[dateField] >= query.from) && (!query.to || !!row[dateField] && row[dateField] <= query.to)))
    const pageSize = query.pageSize || 10
    const page = Math.min(query.page || 1, Math.max(1, Math.ceil(rows.length / pageSize)))
    return { items: all ? rows : rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize, planSelection: selected.state }
  }
  function distributionDetail(id: string, version: number, releaseId: string): ReportDistributionDetail {
    const { state, sample, release } = get(id, version, releaseId)
    if (!allowed(sample, 'distribute')) throw new AppError('FORBIDDEN', '当前状态或权限不允许发放报告。')
    const commission = state.commissions.find(value => value.id === sample.commissionId)
    const finance = config.distributionFinance?.(structuredClone(sample))
    const amount = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value) ? value : null
    const totalAmount = amount(sample.reportPricing?.amount)
    return {
      id, version: sample.version, releaseId: release.id, form: release.form,
      contract: commission?.contract || sample.commissionInfo.contract || '', contractCustomer: commission?.customer || sample.commissionInfo.customer || '',
      commissionCode: commission?.code || sample.commissionInfo.code, customer: sample.customer, projectName: commission?.name || sample.commissionInfo.name,
      receivedAmount: amount(finance?.receivedAmount), contractBalance: amount(finance?.contractBalance), availableCredit: amount(finance?.availableCredit),
      fees: [{ id, testPlan: sample.details?.testPlan || '', code: sample.code, quantity: sample.quantity, amount: totalAmount, paymentStatus: sample.details?.paymentStatus || '' }],
      totalAmount, mailingAddress: sample.details?.mailingAddress || '',
    }
  }
  function pricingDetail(id: string, version: number, releaseId: string): ReportPricingDetail {
    const { sample } = get(id, version, releaseId)
    if (!allowed(sample, 'reprice')) throw new AppError('FORBIDDEN', '当前权限或报告状态不允许重新计价。')
    const prices = summarySample({ ...sample, commissionCode: sample.commissionInfo.code, commissionName: sample.commissionInfo.name })
    const quote = config.price?.(structuredClone(sample))
    if (quote && (!Number.isFinite(quote.amount) || quote.amount < 0 || !quote.rule)) fail('收费规则返回结果无效。')
    return { id, version, releaseId, code: sample.code, testPlan: sample.details?.testPlan || '', quantity: sample.quantity,
      pricingMethod: quote ? '收费规则计价' : '手工计价',
      standardPrice: prices.standardPrice, discountPrice: prices.discountPrice, actualPrice: quote?.amount ?? prices.actualPrice,
      parameterItems: sample.projects.map((name, index) => ({ id: `${id}-parameter-${index}`, name, quantity: null, standardPrice: null, discountRate: null, discountPrice: null, actualPrice: null })), otherItems: [] }
  }
  function action(id: string, input: Record<string, unknown>) {
    if (!Number.isSafeInteger(input.version) || typeof input.releaseId !== 'string' || typeof input.action !== 'string') throw new AppError('BAD_REQUEST', '报告操作参数有误。')
    const { state, sample, release } = get(id, input.version as number, input.releaseId), operation = input.action as ReportOperation
    if (!['complete-print', 'undo-print', 'retry', 'distribute', 'undo-distribute', 'reprice', 'archive', 'undo-archive'].includes(operation)) throw new AppError('BAD_REQUEST', '不支持的报告操作。')
    if (!allowed(sample, operation)) throw new AppError('BUSINESS_RULE', '当前权限或报告状态不允许此操作。')
    const text = (key: string, max: number, required = false) => {
      const value = input[key] ?? ''
      if (typeof value !== 'string' || value.length > max || required && !value.trim()) throw new AppError('VALIDATION', `请检查${({ recipient: '领取人', method: '领取方式', date: '日期', reason: '原因', notes: '备注', trackingNumber: '快递单号', mailingAddress: '邮寄地址' } as Record<string, string>)[key] || key}。`)
      return value.trim()
    }
    let reason = ''
    if (operation === 'archive') {
      const date = text('date', 10, true), a = actor()
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw new AppError('VALIDATION', '请填写有效归档日期。')
      release.archive = { date, at: new Date().toISOString(), actorId: a.id, actorName: a.name }
      release.archiveStatus = '已归档'; reason = JSON.stringify(release.archive)
    } else if (operation === 'undo-archive') {
      reason = `原归档记录：${JSON.stringify(release.archive)}`
      release.archiveStatus = '待归档'; delete release.archive
    } else if (operation === 'complete-print') {
      if (input.confirmed !== true) throw new AppError('VALIDATION', '请确认已完成打印和必要的人工签字、盖章。')
      release.printStatus = '打印完成'
    } else if (operation === 'undo-print') release.printStatus = '待打印'
    else if (operation === 'retry') {
      const task = release.signing!, at = new Date().toISOString()
      ;(task.attempts ??= []).push({ attempt: task.attempt, key: task.key, externalId: task.externalId, status: task.status, error: task.error, endedAt: at })
      // Only a definitive failure may create a new attempt. Unknown outcomes retain the original key.
      task.attempt++; task.key = `${release.id}:${task.attempt}`; task.status = '待签章'; task.externalId = undefined; task.error = undefined
      task.signature = '待处理'; task.seal = '待处理'; task.updatedAt = at; task.events.push({ at, status: task.status, message: '已申请重试签章。' })
    } else if (operation === 'distribute') {
      const recipient = text('recipient', 100, true), method = text('method', 50, true), date = text('date', 10, true), notes = text('notes', 1000)
      if (!(release.form === '纸质' ? ['领取', '自取', '邮寄', '其他'] : ['其他']).includes(method)) throw new AppError('VALIDATION', '领取方式与报告形式不匹配。')
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw new AppError('VALIDATION', '请填写有效发放日期。')
      const a = actor()
      const postal = release.form === '纸质' && method === '邮寄' ? { trackingNumber: text('trackingNumber', 100), mailingAddress: text('mailingAddress', 500) } : {}
      release.receipt = { recipient, method, date, notes, ...postal, at: new Date().toISOString(), actorId: a.id, actorName: a.name }
      release.distributionStatus = '已发放'; reason = JSON.stringify(release.receipt)
    } else if (operation === 'undo-distribute') {
      reason = `${text('reason', 1000, true)}；原发放记录：${JSON.stringify(release.receipt)}`
      release.distributionStatus = '未发放'; delete release.receipt
    } else if (operation === 'reprice') {
      let price: NonNullable<RegistrationSample['reportPricing']>
      if (input.prices !== undefined) {
        if (!input.prices || typeof input.prices !== 'object' || Array.isArray(input.prices)) throw new AppError('VALIDATION', '计价金额格式有误。')
        const values = input.prices as Record<string, unknown>
        const money = (key: string) => {
          const value = values[key]
          if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 999999999.99 || Math.abs(value * 100 - Math.round(value * 100)) > 0.00001) throw new AppError('VALIDATION', '请填写有效的标准价格、折扣价格和实际价格，最多保留两位小数。')
          return Math.round(value * 100) / 100
        }
        price = { standardPrice: money('standardPrice'), discountPrice: money('discountPrice'), amount: money('actualPrice'), rule: '手工重新计价', at: new Date().toISOString() }
      } else {
        if (!config.price) fail('尚未配置收费规则，请填写计价金额。')
        price = { ...config.price!(structuredClone(sample)), at: new Date().toISOString() }
      }
      if (!Number.isFinite(price.amount) || price.amount < 0 || !price.rule) fail('收费规则返回结果无效。')
      const previous = summarySample({ ...sample, commissionCode: sample.commissionInfo.code, commissionName: sample.commissionInfo.name })
      reason = `原计价：${JSON.stringify({ standardPrice: previous.standardPrice, discountPrice: previous.discountPrice, actualPrice: previous.actualPrice })}；新计价：${JSON.stringify(price)}`
      sample.reportPricing = price
    }
    event(sample, reportOperationLabels[operation], reason); deps.write!(state)
    return row(sample, 'distribution')
  }
  function file(id: string, releaseId: string, operation: 'preview' | 'download' | 'print' | 'print-report') {
    const { sample, release } = get(id)
    if (release.id !== releaseId) throw new AppError('BUSINESS_RULE', '报告版本已变化，请刷新。')
    if (!allowed(sample, operation)) throw new AppError('FORBIDDEN', '当前状态或权限不允许获取此报告文件。')
    return release.form === '电子' && release.signing?.status === '签章完成' ? release.signed! : release.original
  }
  function progress(id: string) {
    const { release } = get(id)
    return { id: release.id, revision: release.revision, form: release.form, signing: release.signing, history: release.history, receipt: release.receipt, simulated: provider.name === 'demo' }
  }
  function applyResult(id: string, releaseId: string, taskKey: string, result: SigningResult) {
    const state = read(), sample = state.samples.find(row => row.id === id), release = sample?.reportRelease, task = release?.signing
    if (!sample || !valid(sample) || !release || release.id !== releaseId || !task || task.key !== taskKey || task.status === '签章完成' || task.status === '签章失败') return false
    if (task.externalId && result.externalId && task.externalId !== result.externalId) return false
    if (result.externalId) task.externalId = result.externalId
    const stepsChanged = result.signature && task.signature !== '已完成' || result.seal && task.seal !== '已完成'
    task.signature = result.signature ? '已完成' : task.signature; task.seal = result.seal ? '已完成' : task.seal
    let status: SigningStatus = result.status === 'failed' ? '签章失败' : result.status === 'unknown' ? '待确认' : '签章中'
    if (result.status === 'complete') {
      if (!result.signature || !result.seal || !result.file) { status = '待确认'; result.error = '等待签名、盖章及最终文件全部完成。' }
      else {
        const bytes = Buffer.from(result.file.base64, 'base64')
        if (bytes.length > 30 * 1024 * 1024 || bytes.subarray(0, 5).toString() !== '%PDF-' || createHash('sha256').update(bytes).digest('hex') !== result.file.sha256) fail('签章结果文件校验失败。')
        release.signed = { ...result.file, name: release.original.name }; status = '签章完成'
      }
    }
    if (task.status === status && task.error === result.error && !release.signed && !stepsChanged) { deps.write!(state); return true }
    task.status = status; task.error = result.error; task.updatedAt = new Date().toISOString()
    task.events.push({ at: task.updatedAt, status, message: result.error || status })
    sample.version++; sample.events.push({ at: task.updatedAt, actor: '签章服务', action: status, reason: `报告版本 ${release.revision}；任务 ${task.key}` })
    deps.write!(state); return true
  }
  // Background worker is independent of page visits. Persist '待确认' before submit to make recovery query-first.
  const inFlight = new Set<string>()
  async function tick() {
    const candidates = read().samples.filter(s => valid(s) && s.reportRelease?.signing && ['待签章', '签章中', '待确认'].includes(s.reportRelease.signing.status))
    await Promise.all(candidates.map(async sample => {
      const release = sample.reportRelease!, task = release.signing!
      if (inFlight.has(task.key) || release.signingConfig?.provider !== provider.name) return
      inFlight.add(task.key)
      try {
        const submit = task.status === '待签章'
        if (submit) applyResult(sample.id, release.id, task.key, { externalId: task.externalId || '', status: 'unknown', signature: false, seal: false })
        const result = await (submit ? provider.submit(release) : provider.query(release))
        applyResult(sample.id, release.id, task.key, result)
      } catch (error) {
        const latest = read().samples.find(s => s.id === sample.id)?.reportRelease?.signing
        applyResult(sample.id, release.id, task.key, { externalId: latest?.externalId || '', status: 'unknown', signature: false, seal: false, error: '签章服务响应尚未确认，将继续查询原任务。' })
      } finally { inFlight.delete(task.key) }
    }))
  }
  async function callback(token: string, input: { sampleId: string; releaseId: string; taskKey: string; revision: number; externalId: string }) {
    if (!provider.verifyCallback(token)) throw new AppError('FORBIDDEN', '签章回调验证失败。')
    const sample = read().samples.find(s => s.id === input.sampleId), release = sample?.reportRelease
    if (!sample || !valid(sample) || !release || release.id !== input.releaseId || release.revision !== input.revision || release.signing?.key !== input.taskKey) return { accepted: false }
    // Treat callbacks as notifications; retrieve and verify the result through the authenticated provider.
    const result = await provider.query(release)
    if (result.externalId !== input.externalId) return { accepted: false }
    return { accepted: applyResult(sample.id, release.id, input.taskKey, result) }
  }
  function requestChange(id: string, input: Record<string, unknown>) {
    const a = actor(), state = read(), sample = find(state, id)
    if (!hasRole(a, ['reports'])) throw new AppError('FORBIDDEN', '无权申请报告更改。')
    
    if (sample.status !== 'completed' || !hasApprovedReport(sample) || ['委托更改中', '检测更改中'].includes(sample.dataStatus)) fail('当前报告不能申请更改。')
    if (typeof input.reason !== 'string' || !input.reason.trim() || input.reason.length > 1000 || !['internal', 'external'].includes(String(input.source)) || !['commission', 'testing'].includes(String(input.destination))) throw new AppError('VALIDATION', '请填写更改原因并选择更改内容。')
    const at = new Date().toISOString(), reason = input.reason.trim()
    supersedeReportRelease(sample, a, reason)
    const change = { source: '报告更改', submittedBy: a.name, submittedAt: at, type: input.source === 'internal' ? '内部申请' : '外部申请', description: reason, result: '问题处理中' as const }
    if (input.destination === 'commission') { sample.commissionChange = change; sample.dataStatus = '委托更改中' }
    else { sample.dataChange = change; sample.dataStatus = '检测更改中' }
    sample.reportChangeCount = (sample.reportChangeCount || 0) + 1
    sample.version++; sample.events.push({ at, actor: a.name, action: '申请报告更改', reason: `${change.type}；${input.destination === 'commission' ? '委托更改' : '检测数据更改'}；${reason}` })
    deps.write!(state)
    return { id, version: sample.version, destination: input.destination === 'commission' ? '/commissions/changes' : '/testing/data-changes' }
  }
  return { query, printList, archiveList: (input: Record<string, unknown>, all = false) => printList(input, all, 'archive'), distributionDetail, pricingDetail, distributionList: (input: Record<string, unknown>, all = false) => printList(input, all, 'distribution'), signingList: (input: Record<string, unknown>, all = false) => printList(input, all, 'signing'), action, file, progress, tick, callback, requestChange }
}
