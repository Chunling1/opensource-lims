import { AppError } from '../src/services/common/errors'
import { registrationCanReadSamples } from '../src/services/commissions/registrationService'
import { demoActors } from '../src/services/storage/demoActors'
import type { Actor } from '../src/types/lims'
import type { DemoAttachment, RegistrationDependencies, RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import type { TaskProcessingInput, TaskProcessingQuery, TaskProcessingRecord, TaskProcessingRow } from '../src/types/testing/taskProcessing'
import { stockDate, stockField } from './stockReceipt'

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '请求格式有误。')
  return value as Record<string, unknown>
}
function canWrite(actor: Actor, sample: RegistrationSample) {
  return actor.roles.some(role => ['admin', 'testing'].includes(role)) && !['voided', 'void_pending'].includes(sample.status) && ['任务分配中', '任务分配完成'].includes(sample.dataStatus)
}
function requireWrite(actor: Actor, sample: RegistrationSample) {
  if (!actor.roles.some(role => ['admin', 'testing'].includes(role))) throw new AppError('FORBIDDEN', '当前身份无权管理任务处理记录。')
  if (!canWrite(actor, sample)) throw new AppError('BUSINESS_RULE', '样品状态已变化，当前仅支持查看处理记录和下载附件。')
}
function summary(record: TaskProcessingRecord): TaskProcessingRow {
  const { requestId: _requestId, attachments, events: _events, ...row } = record
  return { ...row, attachmentCount: attachments.length }
}
function queryInput(value: unknown): TaskProcessingQuery {
  const input = object(value), query: TaskProcessingQuery = {}
  if (input.handler !== undefined) query.handler = stockField(input, 'handler', '处理人', 100, false)
  for (const key of ['from', 'to'] as const) if (input[key] !== undefined && input[key] !== '') query[key] = stockDate({ date: input[key] }, '处理日期')
  if (query.from && query.to && query.from > query.to) throw new AppError('VALIDATION', '开始日期不能晚于结束日期。')
  for (const key of ['page', 'pageSize'] as const) if (input[key] !== undefined) {
    if (!Number.isSafeInteger(input[key]) || Number(input[key]) < 1 || key === 'pageSize' && ![10, 20, 50].includes(Number(input[key]))) throw new AppError('BAD_REQUEST', '分页参数有误。')
    query[key] = Number(input[key])
  }
  return query
}
function recordInput(value: unknown): TaskProcessingInput {
  const input = object(value), account = stockField(input, 'account', '处理人工号'), name = stockField(input, 'name', '处理人姓名')
  const person = demoActors.find(actor => actor.id === account)
  if (!person || person.name !== name) throw new AppError('VALIDATION', '处理人工号与姓名不匹配。', { fieldErrors: { account: '请核对处理人工号。', name: '请核对处理人姓名。' } })
  return { requestId: stockField(input, 'requestId', '请求标识', 100), account, name, date: stockDate(input, '处理时间'),
    contactMethod: stockField(input, 'contactMethod', '联系方式', 100, false), contactTarget: stockField(input, 'contactTarget', '沟通对象', 100, false),
    content: stockField(input, 'content', '处理内容', 500), notes: stockField(input, 'notes', '备注', 500, false) }
}
function fileInput(value: unknown): Omit<DemoAttachment, 'id'> {
  const input = object(value)
  if (typeof input.name !== 'string' || !input.name.trim() || input.name.length > 255 || typeof input.type !== 'string' || typeof input.dataUrl !== 'string' || !Number.isSafeInteger(input.size) || Number(input.size) < 0 || Number(input.size) > 20 * 1024 * 1024) throw new AppError('VALIDATION', '请选择不超过 20 MB 的有效附件。')
  const encoded = input.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
  if (encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== input.size) throw new AppError('VALIDATION', '附件内容或大小不正确。')
  return { name: input.name, type: input.type, dataUrl: input.dataUrl, size: Number(input.size) }
}

export function createTaskProcessingService(deps: RegistrationDependencies) {
  function context(sampleId: string) {
    if (deps.locked?.()) throw new AppError('LOCKED', '工作空间已锁定。')
    const actor = deps.actor()
    if (!registrationCanReadSamples(actor)) throw new AppError('FORBIDDEN', '当前身份无权查看样品。')
    const state = structuredClone(deps.read?.())
    if (!state) throw new AppError('UNAVAILABLE', '记录服务暂不可用。')
    const sample = state.samples.find(row => row.id === sampleId && (actor.scope === 'all' || row.departmentId === actor.departmentId))
    if (!sample) throw new AppError('NOT_FOUND', '样品不存在或已不可访问。')
    return { actor, state, sample }
  }
  function find(state: RegistrationState, sampleId: string, recordId: string) {
    const record = state.taskProcessingRecords?.find(row => row.id === recordId && row.sampleId === sampleId)
    if (!record) throw new AppError('NOT_FOUND', '处理记录不存在或已不可访问。')
    return record
  }
  function detail(record: TaskProcessingRecord, actor: Actor, sample: RegistrationSample) { return { ...summary(record), canManageAttachments: canWrite(actor, sample) } }
  return {
    query(sampleId: string, input: unknown) {
      const { actor, sample, state } = context(sampleId), query = queryInput(input), handler = query.handler?.toLocaleLowerCase()
      const rows = (state.taskProcessingRecords || []).filter(row => row.sampleId === sampleId && (!handler || row.name.toLocaleLowerCase().includes(handler) || row.account.toLocaleLowerCase().includes(handler)) && (!query.from || row.date >= query.from) && (!query.to || row.date <= query.to))
        .sort((a, b) => b.date.localeCompare(a.date) || b.submittedAt.localeCompare(a.submittedAt) || b.id.localeCompare(a.id))
      const pageSize = query.pageSize || 10, page = Math.min(query.page || 1, Math.max(1, Math.ceil(rows.length / pageSize)))
      return { sample: { id: sample.id, code: sample.code, name: sample.name, testPlan: sample.details?.testPlan || '' }, canCreate: canWrite(actor, sample),
        items: rows.slice((page - 1) * pageSize, page * pageSize).map(summary), total: rows.length, page, pageSize }
    },
    create(sampleId: string, input: unknown) {
      const { actor, sample, state } = context(sampleId)
      requireWrite(actor, sample)
      const values = recordInput(input), records = state.taskProcessingRecords ??= []
      const existing = records.find(row => row.sampleId === sampleId && row.submittedBy.id === actor.id && row.requestId === values.requestId)
      if (existing) {
        if ((Object.keys(values) as (keyof TaskProcessingInput)[]).some(key => existing[key] !== values[key])) throw new AppError('BUSINESS_RULE', '该请求已保存其他内容，请刷新记录后重试。')
        return detail(existing, actor, sample)
      }
      const now = new Date().toISOString(), record: TaskProcessingRecord = { ...values, id: crypto.randomUUID(), sampleId, sampleCode: sample.code, sampleName: sample.name, testPlan: sample.details?.testPlan || '',
        submittedBy: { id: actor.id, name: actor.name }, submittedAt: now, version: 1, attachments: [], events: [{ at: now, actor: actor.name, action: '新增处理记录', reason: '' }] }
      records.push(record); deps.write?.(state)
      return detail(record, actor, sample)
    },
    detail(sampleId: string, recordId: string) {
      const { actor, sample, state } = context(sampleId)
      return detail(find(state, sampleId, recordId), actor, sample)
    },
    attachments(sampleId: string, recordId: string) {
      const { actor, sample, state } = context(sampleId), record = find(state, sampleId, recordId)
      return { ...detail(record, actor, sample), attachments: record.attachments }
    },
    attachmentAction(sampleId: string, recordId: string, value: unknown, attachmentId?: string) {
      const input = object(value), { actor, sample, state } = context(sampleId)
      requireWrite(actor, sample)
      const record = find(state, sampleId, recordId)
      
      let name: string
      if (attachmentId !== undefined) {
        const index = record.attachments.findIndex(file => file.id === attachmentId)
        if (index < 0) throw new AppError('NOT_FOUND', '附件不存在或已被删除。')
        name = record.attachments.splice(index, 1)[0]!.name
      } else {
        const file = fileInput(input.file); name = file.name
        record.attachments.push({ ...file, id: crypto.randomUUID() })
      }
      record.version++; record.events.push({ at: new Date().toISOString(), actor: actor.name, action: attachmentId === undefined ? '添加附件' : '删除附件', reason: name })
      deps.write?.(state)
      return { ...detail(record, actor, sample), attachments: record.attachments }
    },
  }
}
