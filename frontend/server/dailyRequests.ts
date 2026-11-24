import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { canApplyDailyRequests, canApproveDailyRequests, type DailyApprovalOperation } from '../src/types/quality/dailyRequests'
import { dailyRequestItems, dailyRequestStatuses, dailyRequestColumns, type DailyRequestDraft, type DailyRequestRecord, type DailyRequestRow } from '../src/types/quality/dailyRequests'
import type { RegistrationDependencies, RegistrationState, DemoAttachment } from '../src/types/commissions/registration'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import { registrationCsv } from './registrationDomain'

const date = (value: string) => new Date(value).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
const fieldError = (key: string, message: string): never => { throw new AppError('VALIDATION', message, { fieldErrors: { [key]: message } }) }
function text(input: Record<string, unknown>, key: string, max: number) {
  const value = input[key] ?? ''
  if (typeof value !== 'string' || value.trim().length > max) return fieldError(key, `填写内容不能超过 ${max} 个字符。`)
  return value.trim()
}
function files(value: unknown): DemoAttachment[] {
  if (!Array.isArray(value) || value.length > 100) return fieldError('files', '附件不能超过 100 个。')
  let total = 0
  const ids = new Set<string>()
  return value.map(file => {
    if (!file || typeof file !== 'object' || typeof file.id !== 'string' || !/^[a-f0-9-]{36}$/.test(file.id) || ids.has(file.id) || typeof file.name !== 'string' || !file.name.trim() || file.name.length > 255 || typeof file.type !== 'string' || file.type.length > 200 || !Number.isSafeInteger(file.size) || file.size <= 0 || typeof file.dataUrl !== 'string') return fieldError('files', '附件信息有误，请重新上传。')
    const encoded = file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
    if (encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== file.size) return fieldError('files', '附件内容或大小不正确。')
    total += file.size
    if (total > 20 * 1024 * 1024) return fieldError('files', '附件总计不能超过 20 MB。')
    ids.add(file.id)
    return { id: file.id, name: file.name.trim(), type: file.type, size: file.size, dataUrl: file.dataUrl }
  })
}
export function seedDailyRequests(state: RegistrationState) {
  const at = new Date().toISOString()
  state.dailyRequests ??= dailyRequestStatuses.map((status, i) => ({
    id: `daily-request-${i + 1}`, version: 1, code: `RCSW${date(at).replaceAll('-', '')}${String(i + 1).padStart(4, '0')}`,
    departmentId: i === 5 ? 'lab2' : 'lab', department: i === 5 ? '第二实验室' : '实验室', applicantId: i === 5 ? 'other' : 'admin', applicant: i === 5 ? '第二实验室检测员' : '演示用户', appliedAt: at, status,
    reason: ['检测业务资料用印（示例）', '检测合同用印（示例）', '补充资质资料（示例）', '关系证明申请（示例）', '客户备案资料（示例）', '取消的用印申请（示例）'][i]!,
    items: [dailyRequestItems[i]!], other: '', copies: 1, files: [], withdrawalReason: status === '退回' ? '请补充办理事由（示例）' : '',
    events: [{ at, actorId: 'admin', actor: '演示用户', action: '演示记录', reason: '用于页面演示，非真实业务申请' }],
    ...(['审批通过', '不通过'].includes(status) ? { approval: { result: status as '审批通过' | '不通过', opinion: status === '不通过' ? '办理资料不完整（示例）' : '', actorId: 'approver', actor: '陈批准', at } } : {}),
  }))
}
export function createDailyRequests(deps: RegistrationDependencies, approvalMode = false) {
  const visible = (row: { departmentId: string }) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function actor() {
    const user = deps.actor()
    if (deps.locked?.() || !(approvalMode ? canApproveDailyRequests(user) : canApplyDailyRequests(user))) throw new AppError('FORBIDDEN', '无权执行日常事务申请操作。')
    return user
  }
  function row(record: DailyRequestRecord): DailyRequestRow {
    const user = deps.actor(), owner = canApplyDailyRequests(user) && (user.roles.includes('admin') || user.id === record.applicantId)
    const editable = owner && ['申请中', '退回', '不通过'].includes(record.status)
    const approver = canApproveDailyRequests(user)
    return { ...structuredClone(record), matters: record.items.map(item => item === '其他' && record.other ? `其他：${record.other}` : item).join('、'), canEdit: editable, canDelete: editable, canWithdraw: owner && record.status === '待审批', canApprove: approver && record.status === '待审批', canRevoke: approver && ['审批通过', '不通过'].includes(record.status) && (user.roles.includes('admin') || record.approval?.actorId === user.id), canVoid: approver && ['待审批', '审批通过', '不通过'].includes(record.status) }
  }
  function detail(id: unknown) {
    actor()
    const record = deps.read!()!.dailyRequests?.find(item => item.id === id && !item.deletedAt && visible(item) && (!approvalMode || item.status !== '申请中'))
    if (!record) throw new AppError('NOT_FOUND', '申请记录不存在或无权访问，请刷新列表。')
    return row(record)
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    const q = Object.fromEntries(['from', 'to', 'code', 'departmentId', 'applicant', 'reason', 'item', 'status'].map(key => [key, text(input, key, 200)]))
    for (const value of [q.from, q.to]) if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new AppError('VALIDATION', '日期格式有误。')
    if (q.from && q.to && q.from > q.to) throw new AppError('VALIDATION', '开始日期不能晚于结束日期。')
    if (q.status && !(dailyRequestStatuses as readonly string[]).includes(q.status)) throw new AppError('VALIDATION', '审批状态有误。')
    if (q.item && !(dailyRequestItems as readonly string[]).includes(q.item)) throw new AppError('VALIDATION', '办理事项有误。')
    if (q.departmentId && !registrationDepartments.some(d => d.id === q.departmentId && visible({ departmentId: d.id }))) throw new AppError('FORBIDDEN', '无权查询该部门。')
    const requested = input.page ?? 1, pageSize = input.pageSize ?? 10
    if (typeof requested !== 'number' || !Number.isSafeInteger(requested) || requested < 1 || typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize)) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string'))) throw new AppError('VALIDATION', '申请选择有误。')
    const ids = input.ids as string[] | undefined
    const records = (deps.read!()!.dailyRequests || []).filter(record => !record.deletedAt && visible(record) && (!approvalMode || record.status !== '申请中')
      && (!q.from || date(record.appliedAt) >= q.from) && (!q.to || date(record.appliedAt) <= q.to)
      && (!q.departmentId || record.departmentId === q.departmentId) && (!q.status || record.status === q.status) && (!q.item || record.items.includes(q.item))
      && (['code', 'applicant', 'reason'] as const).every(key => !q[key] || record[key].toLocaleLowerCase().includes(q[key]!.toLocaleLowerCase()))
      && (!ids || ids.includes(record.id))).sort((a, b) => b.appliedAt.localeCompare(a.appliedAt) || b.code.localeCompare(a.code))
    const page = Math.min(requested, Math.max(1, Math.ceil(records.length / pageSize)))
    return { items: (all ? records : records.slice((page - 1) * pageSize, page * pageSize)).map(row), total: records.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(), previous = input.id === undefined ? undefined : detail(input.id), submit = input.intent === 'submit'
    if (!['save', 'submit'].includes(String(input.intent ?? 'save'))) throw new AppError('VALIDATION', '申请操作有误。')
    
    if (previous && !previous.canEdit) denyOperation(previous, '修改')
    const reason = text(input, 'reason', 2000), other = text(input, 'other', 500)
    if (submit && !reason) return fieldError('reason', '请填写办理事由。')
    if (!Array.isArray(input.items) || input.items.length > dailyRequestItems.length || input.items.some(item => !(dailyRequestItems as readonly unknown[]).includes(item)) || new Set(input.items).size !== input.items.length) return fieldError('items', '请选择有效的办理事项。')
    if (submit && !input.items.length) return fieldError('items', '请至少选择一项办理事项。')
    if (submit && input.items.includes('其他') && !other) return fieldError('other', '请填写其他办理事项。')
    const copies = input.copies ?? null
    if (copies !== null && (typeof copies !== 'number' || !Number.isSafeInteger(copies) || copies < 1 || copies > 99999) || submit && copies === null) return fieldError('copies', '请填写 1 至 99999 的整数份数。')
    const draft: DailyRequestDraft = { reason, items: [...input.items] as string[], other: input.items.includes('其他') ? other : '', copies: copies as number | null, files: files(input.files ?? []) }
    const state = structuredClone(deps.read!()!), records = state.dailyRequests ??= [], at = new Date().toISOString()
    const record: DailyRequestRecord = previous ? records.find(r => r.id === previous.id)! : {
      ...draft, id: randomUUID(), version: 0, code: `RCSW${date(at).replaceAll('-', '')}${String(records.length + 1).padStart(4, '0')}`,
      departmentId: user.departmentId, department: registrationDepartments.find(d => d.id === user.departmentId)?.name || user.departmentId,
      applicantId: user.id, applicant: user.name, appliedAt: at, status: '申请中', withdrawalReason: '', events: [],
    }
    Object.assign(record, draft); record.status = submit ? '待审批' : '申请中'; record.version++
    if (submit) { record.withdrawalReason = ''; delete record.approval }
    record.events.push({ at, actorId: user.id, actor: user.name, action: submit ? '提交申请' : previous ? '修改申请' : '新增申请', reason })
    if (!previous) records.push(record)
    deps.write!(state)
    return row(record)
  }
  function action(input: Record<string, unknown>, kind: 'withdraw' | 'delete') {
    const user = actor(), previous = detail(input.id)
    
    if (!(kind === 'withdraw' ? previous.canWithdraw : previous.canDelete)) denyOperation(previous, kind === 'withdraw' ? '撤销' : '删除')
    const reason = kind === 'withdraw' ? text(input, 'withdrawalReason', 1000) : ''
    if (kind === 'withdraw' && !reason) return fieldError('withdrawalReason', '请填写撤回原因。')
    const state = structuredClone(deps.read!()!), record = state.dailyRequests!.find(item => item.id === previous.id)!, at = new Date().toISOString()
    if (kind === 'withdraw') { record.status = '申请中'; record.withdrawalReason = reason }
    else record.deletedAt = at
    record.version++; record.events.push({ at, actorId: user.id, actor: user.name, action: kind === 'withdraw' ? '撤销申请' : '删除申请', reason })
    deps.write!(state)
    return { id: record.id }
  }
  function denyOperation(record: DailyRequestRecord, operation: '修改' | '撤销' | '删除'): never {
    const user = actor()
    if (!user.roles.includes('admin') && user.id !== record.applicantId) throw new AppError('FORBIDDEN', `不能${operation}他人的申请。`)
    if (record.status === '待审批' && operation !== '撤销') throw new AppError('BUSINESS_RULE', `待审批申请不能直接${operation}，请先撤销申请。`)
    throw new AppError('BUSINESS_RULE', `当前申请为“${record.status}”，不能${operation}。`)
  }
  function approve(input: Record<string, unknown>, operation: DailyApprovalOperation) {
    const user = actor()
    if (!canApproveDailyRequests(user)) throw new AppError('FORBIDDEN', '无权审批日常事务申请。')
    const previous = detail(input.id)
    
    if (!(operation === 'approve' ? previous.canApprove : operation === 'revoke' ? previous.canRevoke : operation === 'void' && previous.canVoid)) throw new AppError('BUSINESS_RULE', '当前状态或审批权限不允许此操作，请刷新列表。')
    const opinion = text(input, 'opinion', 1000)
    if (operation === 'approve' && !['审批通过', '不通过'].includes(String(input.result))) return fieldError('result', '请选择审批结果。')
    if (!opinion && (operation !== 'approve' || input.result === '不通过')) return fieldError('opinion', operation === 'approve' ? '审批不通过时请填写审批意见。' : operation === 'revoke' ? '请填写撤回原因。' : '请填写作废原因。')
    const state = structuredClone(deps.read!()!), record = state.dailyRequests!.find(item => item.id === previous.id)!, at = new Date().toISOString()
    if (operation === 'approve') {
      record.status = input.result as '审批通过' | '不通过'
      record.approval = { result: record.status, opinion, actorId: user.id, actor: user.name, at }
    } else if (operation === 'revoke') { record.status = '待审批'; record.withdrawalReason = opinion; delete record.approval }
    else { record.status = '已作废'; record.voidReason = opinion }
    record.version++
    record.events.push({ at, actorId: user.id, actor: user.name, action: operation === 'approve' ? record.status : operation === 'revoke' ? '撤回审批' : '作废申请', reason: opinion })
    deps.write!(state)
    return row(record)
  }
  return { query, detail, save, action, approve, export: (input: Record<string, unknown>) => registrationCsv([dailyRequestColumns.map(c => c.label), ...query(input, true).items.map(item => dailyRequestColumns.map(c => c.key === 'appliedAt' ? new Date(item.appliedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : item[c.key]))]) }
}
