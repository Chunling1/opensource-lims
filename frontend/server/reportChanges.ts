import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationDependencies, RegistrationSample } from '../src/types/commissions/registration'
import { reportChangeColumns, reportChangeStatuses, reportChangeTypes, type ReportChangeDraft, type ReportChangeQuery, type ReportChangeRecord, type ReportChangeReference } from '../src/types/reports/reportChange'
import { hasApprovedReport } from './reportLifecycle'
import { registrationCsv } from './registrationDomain'
import { tableCellText } from '../src/services/common/table'
import { demoActors } from '../src/services/storage/demoActors'
import type { ReportChangeSource, ExternalReportChange } from '../src/types/reports/reportChange'
import type { EntryPeoplePage, EntryPersonCandidate } from '../src/types/testing/dataEntryDetail'

const fail = (message: string): never => { throw new AppError('BUSINESS_RULE', message) }
const applicationDate = (at: string) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(at))
const references = (r: ReportChangeDraft): ReportChangeReference[] => r.reports?.length ? r.reports : [{ sampleId: r.sampleId, sampleVersion: r.sampleVersion, releaseId: r.releaseId }]
function text(input: Record<string, unknown>, key: string, max = 1000, required = false) {
  const value = input[key] ?? ''
  if (typeof value !== 'string' || value.length > max || required && !value.trim()) throw problem('VALIDATION', `请正确填写${({ before: '更改前内容', after: '更改后内容', reason: '原因', responsibility: '更改责任方' } as Record<string, string>)[key] || key}。`, key)
  return value.trim()
}
export function createReportChanges(deps: RegistrationDependencies, source: ReportChangeSource = 'internal') {
  const actor = () => { const a = deps.actor(); if (deps.locked?.() || !a.roles.some(r => ['admin', 'reports'].includes(r))) throw new AppError('FORBIDDEN', '无权操作报告更改申请。'); return a }
  const read = () => {
    const state = structuredClone(deps.read!()!)
    for (const r of state.reportChangeRequests || []) {
      // Preserve applications saved by the previous page while aligning their labels.
      r.status = ({ '已批准': '审批通过', '已驳回': '不通过', '已撤回': '申请中' } as Record<string, ReportChangeRecord['status']>)[r.status] || r.status
      r.changeType ||= '委托信息更改'
    }
    return state
  }
  const visible = (s: { departmentId: string }) => actor().scope === 'all' || s.departmentId === actor().departmentId
  const eligible = (s: RegistrationSample) => s.status === 'completed' && hasApprovedReport(s) && !s.reportRelease?.supersededAt && !['委托更改中', '检测更改中', '报告更改中', '报告更改审批中'].includes(s.dataStatus)
  const editable = (r: ReportChangeRecord) => actor().roles.includes('admin') || r.applicantId === actor().id
  function handlers(): EntryPersonCandidate[] {
    const a = actor()
    return demoActors.filter(p => p.active !== false && (a.scope === 'all' || p.departmentId === a.departmentId))
      .map(p => ({ id: p.id, name: p.name, departmentId: p.departmentId, departmentName: registrationDepartments.find(d => d.id === p.departmentId)?.name || p.departmentId, certificateNumber: p.certificateNumber || '', phone: p.phone || '' }))
  }
  function queryHandlers(input: Record<string, unknown>): EntryPeoplePage {
    const a = actor(), scope = input.scope ?? 'department'
    if (scope !== 'department' && scope !== 'all') throw new AppError('BAD_REQUEST', '人员范围有误。')
    const keyword = text(input, 'keyword', 200).toLocaleLowerCase(), requestedPage = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (!Number.isSafeInteger(requestedPage) || Number(requestedPage) < 1 || typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize)) throw new AppError('BAD_REQUEST', '人员分页参数有误。')
    const rows = handlers().filter(p => (scope === 'all' || p.departmentId === a.departmentId) && (!keyword || p.id.toLocaleLowerCase().includes(keyword) || p.name.toLocaleLowerCase().includes(keyword)))
      .sort((a, b) => a.id.localeCompare(b.id, 'zh-CN', { numeric: true }))
    const total = rows.length, page = Math.min(Number(requestedPage), Math.max(1, Math.ceil(total / pageSize)))
    return { items: rows.slice((page - 1) * pageSize, page * pageSize), total, page, pageSize, scope, presetConfigured: false, departmentName: registrationDepartments.find(d => d.id === a.departmentId)?.name || a.departmentId }
  }
  function resolveHandler(input: Record<string, unknown>): EntryPersonCandidate {
    const id = text(input, 'id', 100), person = handlers().find(p => p.id === id)
    if (!person) throw problem('VALIDATION', '指定处理人不可选，请重新选择。', 'handlerId')
    return person
  }
  function externalFields(input: Record<string, unknown>): ExternalReportChange {
    if (typeof input.charge !== 'boolean' || typeof input.amount !== 'number' || !Number.isFinite(input.amount) || input.amount < 0 || input.amount > 999999999 || Math.abs(input.amount * 100 - Math.round(input.amount * 100)) > 0.0001) throw problem('VALIDATION', '收费金额须为非负金额，最多两位小数。', 'amount')
    if (!input.external || typeof input.external !== 'object' || Array.isArray(input.external)) throw new AppError('VALIDATION', '请填写外部申请信息。')
    const value = input.external as Record<string, unknown>, handlerId = text(value, 'handlerId', 100)
    const handler = handlerId ? resolveHandler({ id: handlerId }) : undefined
    if (typeof value.isCommissionCustomer !== 'boolean' || typeof value.allReturned !== 'boolean') throw new AppError('VALIDATION', '请选择申请单位资格和是否全部收回。')
    if (!Array.isArray(value.evidence)) throw new AppError('VALIDATION', '证明附件格式有误。')
    let totalSize = 0
    const evidence = value.evidence.map(raw => {
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new AppError('VALIDATION', '附件格式有误。')
      const file = raw as Record<string, unknown>, name = text(file, 'name', 255, true), type = text(file, 'type', 200)
      if (typeof file.dataUrl !== 'string' || !Number.isSafeInteger(file.size) || Number(file.size) < 0) throw new AppError('VALIDATION', '附件内容或大小不正确。')
      totalSize += Number(file.size)
      if (totalSize > 20 * 1024 * 1024) throw new AppError('VALIDATION', '证明附件总大小不能超过 20 MB。')
      const encoded = file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
      if (encoded === undefined || encoded.length % 4 !== 0 || Buffer.from(encoded, 'base64').length !== file.size) throw new AppError('VALIDATION', '附件内容或大小不正确。')
      return { id: typeof file.id === 'string' && file.id.length <= 100 ? file.id : randomUUID(), name, type, size: Number(file.size), dataUrl: file.dataUrl }
    })
    return { handlerId, handlerName: handler?.name || '', isCommissionCustomer: value.isCommissionCustomer, allReturned: value.allReturned, evidence }
  }
  const row = (r: ReportChangeRecord) => {
    const samples = deps.read!()?.samples || []
    const valid = references(r).every(report => { const sample = samples.find(s => s.id === report.sampleId); return !!sample && visible(sample) && eligible(sample) && (sample.reportRelease?.id || '') === report.releaseId })
    return { ...r, canEdit: editable(r) && ['申请中', '退回', '不通过'].includes(r.status) && valid, canWithdraw: editable(r) && r.status === '待审批', canDelete: editable(r) && ['申请中', '退回', '不通过'].includes(r.status) }
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    const q: ReportChangeQuery = {}
    for (const key of ['from', 'to', 'code', 'departmentId', 'applicant', 'sampleCode', 'status'] as const) q[key] = text(input, key, 200)
    for (const date of [q.from, q.to]) if (date && (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date)) throw new AppError('VALIDATION', '日期格式有误。')
    if (q.from && q.to && q.from > q.to) throw new AppError('VALIDATION', '开始日期不能晚于结束日期。')
    if (q.status && !(reportChangeStatuses as readonly string[]).includes(q.status)) throw new AppError('VALIDATION', '审批状态无效。')
    const sort = input.sort ?? 'code', direction = input.direction ?? 'asc'
    if (!['code', 'appliedAt', 'sampleCode'].includes(String(sort)) || !['asc', 'desc'].includes(String(direction))) throw new AppError('BAD_REQUEST', '排序参数有误。')
    const page = Number(input.page ?? 1), pageSize = Number(input.pageSize ?? 10)
    if (!Number.isSafeInteger(page) || page < 1 || ![10, 20, 50].includes(pageSize)) throw new AppError('BAD_REQUEST', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.some(id => typeof id !== 'string'))) throw new AppError('BAD_REQUEST', '选择记录参数有误。')
    const items = (read().reportChangeRequests || []).filter(r => (r.source || 'internal') === source && !r.deletedAt && visible(r)
      && (!q.from || applicationDate(r.appliedAt) >= q.from) && (!q.to || applicationDate(r.appliedAt) <= q.to)
      && (!q.departmentId || r.departmentId === q.departmentId) && (!q.status || r.status === q.status)
      && (['code', 'applicant', 'sampleCode'] as const).every(key => !q[key] || r[key].toLowerCase().includes(q[key]!.toLowerCase()))
      && (!input.ids || (input.ids as string[]).includes(r.id)))
      .sort((a, b) => (direction === 'desc' ? -1 : 1) * a[sort as 'code'].localeCompare(b[sort as 'code'], 'zh-CN', { numeric: true }))
    const actualPage = Math.min(page, Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: (all ? items : items.slice((actualPage - 1) * pageSize, actualPage * pageSize)).map(row), total: items.length, page: actualPage, pageSize }
  }
  function candidates(input: Record<string, unknown>) {
    actor(); const keyword = text(input, 'keyword', 200).toLowerCase(), state = read()
    const commissionCode = text(input, 'commissionCode', 200).toLowerCase(), reportCode = text(input, 'reportCode', 200).toLowerCase()
    const commissions = new Map(state.commissions.map(c => [c.id, c]))
    return state.samples.filter(s => visible(s) && eligible(s) && (!keyword || [s.code, s.reportCode, s.name].some(v => v?.toLowerCase().includes(keyword)))
      && (!commissionCode || commissions.get(s.commissionId)?.code.toLowerCase().includes(commissionCode))
      && (!reportCode || s.reportCode.toLowerCase().includes(reportCode))
      && !(state.reportChangeRequests || []).some(r => references(r).some(report => report.sampleId === s.id) && !r.deletedAt && ['申请中', '待审批', '退回'].includes(r.status)))
      .map(s => ({ id: s.id, version: s.version, releaseId: s.reportRelease?.id || '', code: s.code, reportCode: s.reportCode, name: s.name, contractCode: s.commissionInfo.contract || commissions.get(s.commissionId)?.contract || '', commissionCode: commissions.get(s.commissionId)?.code || '', commissionId: s.commissionId }))
  }
  function find(state: ReturnType<typeof read>, id: string) {
    const r = state.reportChangeRequests?.find(r => r.id === id && !r.deletedAt)
    if (!r || (r.source || 'internal') !== source || !visible(r)) throw new AppError('NOT_FOUND', '申请记录不存在或无权访问。')
    return r
  }
  function save(input: Record<string, unknown>, id?: string) {
    const a = actor(), state = read(), existing = id ? find(state, id) : undefined
    const intent = input.intent ?? 'save'
    if (!['save', 'submit'].includes(String(intent))) throw new AppError('BAD_REQUEST', '申请操作有误。')
    
    if (existing && !row(existing).canEdit) fail('当前申请不能修改。')
    const rawReports = input.reports === undefined ? [{ sampleId: existing?.sampleId || input.sampleId, sampleVersion: input.sampleVersion, releaseId: input.releaseId }] : input.reports
    if (!Array.isArray(rawReports) || !rawReports.length || rawReports.some(r => !r || typeof r !== 'object' || Array.isArray(r))) throw new AppError('VALIDATION', '请选择报告。')
    const requested = rawReports as Record<string, unknown>[]
    if (new Set(requested.map(r => r.sampleId)).size !== requested.length) throw new AppError('VALIDATION', '不能重复选择同一报告。')
    if (existing && (references(existing).length !== requested.length || references(existing).some(r => !requested.some(value => value.sampleId === r.sampleId && value.releaseId === r.releaseId)))) throw new AppError('BUSINESS_RULE', '申请关联报告不能更换，请刷新后重试。')
    let commissionId: string | undefined
    const reports: ReportChangeReference[] = requested.map(value => {
      const sampleId = text(value, 'sampleId', 200, true), sample = state.samples.find(s => s.id === sampleId && visible(s))
      if (!sample || !eligible(sample)) throw new AppError('BUSINESS_RULE', '当前报告不能申请更改。')
      if (commissionId !== undefined && commissionId !== sample.commissionId) fail('只能选择同一委托单下的报告。')
      commissionId = sample.commissionId
      if ((sample.reportRelease?.id || '') !== value.releaseId) throw new AppError('BUSINESS_RULE', '报告已更新，请重新选择报告。')
      if ((state.reportChangeRequests || []).some(r => r.id !== id && references(r).some(report => report.sampleId === sampleId) && !r.deletedAt && ['申请中', '待审批', '退回'].includes(r.status))) fail('该报告已有未完成的更改申请。')
      return { sampleId, sampleVersion: sample.version, releaseId: sample.reportRelease?.id || '', sampleCode: sample.code, reportCode: sample.reportCode }
    })
    const first = reports[0]!
    if (!(reportChangeTypes as readonly unknown[]).includes(input.changeType)) throw new AppError('VALIDATION', '请选择有效的更改类型。')
    // Historical pricing/content fields remain on the record; this application form does not edit them.
    const draft: ReportChangeDraft = { sampleId: first.sampleId, sampleVersion: first.sampleVersion, releaseId: first.releaseId, reports, changeType: input.changeType as ReportChangeDraft['changeType'], responsibility: existing?.responsibility || '', before: existing?.before || '', after: existing?.after || '', reason: text(input, 'reason', 1000, intent === 'submit'), charge: existing?.charge || false, amount: existing?.amount || 0 }
    const at = new Date().toISOString()
    const r: ReportChangeRecord = existing || { ...draft, id: randomUUID(), version: 0, code: `BGG${at.slice(0, 10).replaceAll('-', '')}${String((state.reportChangeRequests?.length || 0) + 1).padStart(4, '0')}`, departmentId: a.departmentId, department: registrationDepartments.find(d => d.id === a.departmentId)?.name || a.departmentId, applicantId: a.id, applicant: a.name, appliedAt: at, status: '待审批', sampleCode: reports.map(r => r.sampleCode).join('、'), reportCode: reports.map(r => r.reportCode).join('、'), withdrawalReason: '', events: [] }
    if (source === 'external') {
      const fields = { ...existing?.external, ...externalFields(input) }
      Object.assign(draft, { responsibility: text(input, 'responsibility', 200), before: text(input, 'before'), after: text(input, 'after'), charge: input.charge, amount: input.charge ? input.amount : 0, external: fields })
    }
    Object.assign(r, draft, { source }); r.version++; r.status = intent === 'submit' ? '待审批' : '申请中'
    if (intent === 'submit') r.withdrawalReason = ''
    r.events.push({ at, actorId: a.id, actor: a.name, action: intent === 'submit' ? '提交申请' : existing ? '修改申请' : '新增申请', reason: r.reason })
    if (!existing) (state.reportChangeRequests ||= []).push(r)
    deps.write!(state); return row(r)
  }
  function action(id: string, input: Record<string, unknown>) {
    const a = actor(), state = read(), r = find(state, id)
    
    const at = new Date().toISOString(), permissions = row(r)
    if (input.action === 'withdraw') { if (!permissions.canWithdraw) fail('当前申请不能撤销。'); r.withdrawalReason = text(input, 'reason', 1000, true); r.status = '申请中' }
    else if (input.action === 'delete') { if (!permissions.canDelete) fail('请先撤销申请后再删除。'); r.deletedAt = at }
    else throw new AppError('BAD_REQUEST', '不支持的申请操作。')
    r.version++; r.events.push({ at, actorId: a.id, actor: a.name, action: input.action === 'withdraw' ? '撤销申请' : '删除申请', reason: input.action === 'withdraw' ? r.withdrawalReason : '' })
    deps.write!(state); return row(r)
  }
  return { query, candidates, save, action, queryHandlers, resolveHandler, detail: (id: string) => {
    actor(); const state = read(), r = find(state, id), result = row(r)
    result.reports = references(r).map(report => {
      const sample = state.samples.find(s => s.id === report.sampleId && visible(s))
      if (!sample || !eligible(sample) || (sample.reportRelease?.id || '') !== report.releaseId) { result.canEdit = false; return report }
      return { ...report, sampleVersion: sample.version }
    })
    result.sampleVersion = result.reports[0]!.sampleVersion
    return result
  }, export: (input: Record<string, unknown>) => registrationCsv([reportChangeColumns.map(c => c.label), ...query(input, true).items.map(r => reportChangeColumns.map(c => c.key === 'charge' ? r.charge ? '是' : '否' : tableCellText(r[c.key], { money: c.key === 'amount' })))]) }
}
