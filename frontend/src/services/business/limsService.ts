import { AppError, problem } from '../common/errors'
import { initialFields, moduleMap, modules } from './modules'
import type { Actor, ApprovalInstance, BusinessRecord, FieldDefinition, Fields, LimsDatabase, ListQuery, Value } from '../../types/lims'
import { repository, type Repository } from '../storage/database'
import { assertRole, assertScope, canRead, currentActor, hasRole, inScope, resolveActor, sessionLocked } from '../../stores/session'
import { calculateFormula } from '../common/formula'

const now = () => new Date().toISOString()
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
const ids = (value: Value | undefined) => Array.isArray(value) ? value : []
const number = (value: Value | undefined) => Number(value ?? 0)
export const cents = (value: Value | undefined) => Math.round(number(value) * 100)
export const currency = (value: number) => (value / 100).toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' })
export function recordConfiguration(record: BusinessRecord) {
  const method = record.data.methodSnapshot ? JSON.parse(String(record.data.methodSnapshot)) as BusinessRecord : undefined
  const split = (value: unknown) => String(value || '').split(/[,，]/).map(s => s.trim()).filter(Boolean).slice(0, 20)
  return { fields: split(method?.data.recordFields).map((label, i): FieldDefinition => ({ key: `recordField${i}`, label, required: true })), columns: split(method?.data.tableColumns) }
}
const get = (state: LimsDatabase, id: Value | undefined, kind?: string) => { const r = state.records.find(r => r.id === id && (!kind || r.kind === kind)); if (!r) throw new AppError('NOT_FOUND', '关联记录不存在。'); return r }
const active = (r: BusinessRecord) => { if (!['有效', '已批准', '已发布'].includes(r.status)) throw new AppError('BUSINESS_RULE', `${r.name}尚未生效或已停用。`); return r }
const validDate = (value: Value | undefined) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !isNaN(Date.parse(value))
const unexpired = (r: BusinessRecord, key = 'validUntil') => { active(r); if (!validDate(r.data[key]) || String(r.data[key]) < today()) throw new AppError('BUSINESS_RULE', `${r.name}已过有效期。`) }
function audit(state: LimsDatabase, actor: Actor, entity: BusinessRecord, action: string, reason = '', before?: BusinessRecord) {
  state.audits.push({ id: crypto.randomUUID(), entityId: entity.id, kind: entity.kind, actorId: actor.id, actor: actor.name, at: now(), action, reason, before, after: structuredClone(entity) })
}
function newRecord(state: LimsDatabase, actor: Actor, kind: string, name: string, data: Fields, status?: string) {
  const definition = moduleMap[kind]
  if (!definition) throw new AppError('NOT_FOUND', '未知业务模块。')
  const rule = state.records.find(r => r.kind === 'settings' && r.status === '有效' && r.data.setting === '编号前缀' && r.data.moduleId === kind)
  const prefix = String(rule?.data.value || definition.prefix), stamp = now().slice(0, 10).replaceAll('-', '')
  let seq = state.records.filter(r => r.kind === kind).length + 1
  while (state.records.some(r => r.code === `${prefix}${stamp}-${String(seq).padStart(5, '0')}`)) seq++
  const r: BusinessRecord = { id: crypto.randomUUID(), kind, name: name.trim(), code: `${prefix}${stamp}-${String(seq).padStart(5, '0')}`, status: status ?? definition.initial, version: 1, departmentId: actor.departmentId, ownerId: actor.id, createdAt: now(), updatedAt: now(), data: { ...initialFields(definition), ...JSON.parse(JSON.stringify(data)) } }
  state.records.push(r); audit(state, actor, r, '新建'); return r
}
function validateFields(state: LimsDatabase, actor: Actor, fields: FieldDefinition[], data: Fields) {
  for (const f of fields) {
    const v = data[f.key]
    if (f.required && (v === undefined || v === '' || (typeof v === 'string' && !v.trim()) || (Array.isArray(v) && !v.length))) throw problem('VALIDATION', `请填写${f.label}。`, f.key)
    if (v === undefined || v === '') continue
    if (typeof v === 'string' && v.length > 20000) throw problem('VALIDATION', `${f.label}过长。`, f.key)
    if (f.type === 'number' && (!Number.isFinite(Number(v)) || Number(v) < (f.min ?? -Infinity))) throw problem('VALIDATION', `${f.label}超出允许范围。`, f.key)
    if (f.type === 'number' && f.label.includes('元') && !Number.isSafeInteger(cents(v))) throw problem('VALIDATION', `${f.label}超出金额精度范围。`, f.key)
    if (f.type === 'date' && !validDate(v)) throw problem('VALIDATION', `${f.label}日期无效。`, f.key)
    if (f.type === 'multi' && !Array.isArray(v)) throw problem('VALIDATION', `${f.label}格式无效。`, f.key)
    const values = Array.isArray(v) ? v : [v]
    if (f.options && values.some(x => !f.options!.includes(String(x)))) throw problem('VALIDATION', `${f.label}选项无效。`, f.key)
    if (f.reference) for (const item of values) {
      if (f.reference === 'actors') { const a = resolveActor(state, String(item)); if (actor.scope !== 'all' && actor.departmentId !== a.departmentId) throw new AppError('FORBIDDEN', '不能选择其他部门人员。') }
      else if (f.reference === 'samples') { if (!state.samples.some(s => s.id === item)) throw new AppError('NOT_FOUND', '样品不存在。'); assertScope(actor, state.sampleMeta[String(item)] ?? { departmentId: 'lab' }) }
      else { const r = get(state, item, f.reference); assertScope(actor, r) }
    }
  }
}
function validateBusiness(state: LimsDatabase, r: BusinessRecord) {
  const d = r.data
  if (['commissions', 'quotations'].includes(r.kind) && (number(d.discount) < 0 || number(d.discount) > 100 || number(d.taxRate) < 0 || number(d.taxRate) > 100)) throw new AppError('BUSINESS_RULE', '折扣和税率必须在 0–100 之间。')
  if (r.kind === 'projects' && (number(d.lower) > number(d.upper) || !Number.isInteger(number(d.precision)) || number(d.precision) > 8)) throw new AppError('BUSINESS_RULE', '限值或小数位数无效。')
  if (r.kind === 'methods') { calculateFormula(String(d.formula), 1); const p = active(get(state, d.projectId, 'projects')); if (!p) throw new AppError('BUSINESS_RULE', '检测项目不可用。') }
  if (r.kind === 'reportTemplates') { const columns = String(d.resultColumns).split(/[,，]/).map(s => s.trim()); if (!columns.length || new Set(columns).size !== columns.length || columns.some(c => !['样品', '项目', '方法', '结果', '单位', '判定', '来源'].includes(c)) || !columns.includes('结果')) throw new AppError('BUSINESS_RULE', '结果表列名须从样品、项目、方法、结果、单位、判定、来源中选择，并包含结果。') }
  if (r.kind === 'contracts' && String(d.endDate) < String(d.startDate)) throw new AppError('BUSINESS_RULE', '合同结束日期不能早于开始日期。')
  if (r.kind === 'commissions' && d.contractId) { const contract = get(state, d.contractId, 'contracts'); if (contract.status !== '已批准' || contract.data.customerId !== d.customerId) throw new AppError('BUSINESS_RULE', '合同须评审通过且与委托客户一致。') }
  if (r.kind === 'tasks' || r.kind === 'outsourcing') {
    const order = get(state, d.commissionId, 'commissions')
    if (!['已受理', '执行中'].includes(order.status)) throw new AppError('BUSINESS_RULE', '委托尚未受理或已结束。')
    if (!ids(order.data.projectIds).includes(String(d.projectId))) throw new AppError('BUSINESS_RULE', '检测项目不在委托范围内。')
    if (!state.records.some(x => x.kind === 'sampleLinks' && x.status === '已关联' && x.data.sampleId === d.sampleId && x.data.commissionId === d.commissionId)) throw new AppError('BUSINESS_RULE', '样品须先与当前委托关联。')
    const sample = state.samples.find(x => x.id === d.sampleId)
    if (sample?.status !== 'received') throw new AppError('BUSINESS_RULE', '样品尚未接收。')
    const method = get(state, d.methodId, 'methods'); if (method.data.projectId !== d.projectId) throw new AppError('BUSINESS_RULE', '检测方法与项目不匹配。')
  }
  if (r.kind === 'users' && !ids(d.roles).length) throw new AppError('BUSINESS_RULE', '至少选择一个角色。')
  if (r.kind === 'users' && state.records.some(x => x.kind === 'users' && x.id !== r.id && x.data.login === d.login)) throw new AppError('BUSINESS_RULE', '账号已经存在。')
  if (r.kind === 'users' && r.status === '有效' && !state.records.some(x => x.kind === 'users' && x.status === '有效' && ids(x.data.roles).includes('admin'))) throw new AppError('BUSINESS_RULE', '必须保留至少一个有效管理员。')
  if (r.kind === 'customers' && state.records.some(x => x.kind === 'customers' && x.id !== r.id && x.name === r.name)) throw new AppError('BUSINESS_RULE', '客户名称已经存在。')
  if (r.kind === 'projects' && state.records.some(x => x.kind === 'projects' && x.id !== r.id && x.name === r.name)) throw new AppError('BUSINESS_RULE', '检测项目名称已经存在。')
  if (r.kind === 'settings' && d.setting === '编号前缀' && (!moduleMap[String(d.moduleId)] || !/^[A-Za-z0-9-]{1,12}$/.test(String(d.value)))) throw new AppError('BUSINESS_RULE', '编号规则需要有效模块及 1–12 位字母数字前缀。')
}
function approvalRoles(kind: string, action: string) {
  if (kind === 'reports' && ['sign', 'exception'].includes(action)) return ['approver']
  if (kind === 'refunds') return ['finance', 'approver']
  if (kind === 'qualityCases' || kind === 'equipmentPlans') return ['quality', 'reviewer']
  return ['reviewer', 'approver']
}
function amountSnapshot(state: LimsDatabase, r: BusinessRecord) {
  const lines = ids(r.data.projectIds).map(id => {
    const p = active(get(state, id, 'projects'))
    const prices = state.records.filter(x => x.kind === 'prices' && x.status === '有效' && x.data.projectId === id && String(x.data.effectiveDate) <= today()).sort((a, b) => String(b.data.effectiveDate).localeCompare(String(a.data.effectiveDate)))
    const price = prices[0]?.data.price ?? p.data.price
    const methods = state.records.filter(x => x.kind === 'methods' && x.status === '有效' && x.data.projectId === id).map(m => ({ id: m.id, name: m.name, revision: m.data.revision, standard: m.data.standard }))
    return { id, name: p.name, unit: p.data.unit, priceCents: cents(price), laborCents: cents(prices[0]?.data.laborCost ?? p.data.laborCost), methods }
  })
  const subtotal = lines.reduce((sum, l) => sum + l.priceCents, 0), discounted = Math.round(subtotal * (100 - number(r.data.discount)) / 100)
  const amount = discounted + Math.round(discounted * number(r.data.taxRate) / 100)
  return { customer: structuredClone(active(get(state, r.data.customerId, 'customers'))), lines, amountCents: amount, requirements: r.data.requirements, at: now() }
}
export function paidCents(state: LimsDatabase, orderId: string) {
  const payments = state.records.filter(r => r.kind === 'payments' && r.status === '已入账' && r.data.commissionId === orderId)
  return payments.reduce((sum, p) => sum + cents(p.data.amount) - state.records.filter(r => r.kind === 'refunds' && r.status === '已批准' && r.data.paymentId === p.id).reduce((s, r) => s + cents(r.data.amount), 0), 0)
}
function dueCents(state: LimsDatabase, orderId: string) { return state.records.filter(r => r.kind === 'receivables' && r.data.commissionId === orderId).reduce((sum, r) => sum + cents(r.data.amount), 0) }
function releaseCheck(state: LimsDatabase, report: BusinessRecord) {
  const order = get(state, report.data.commissionId, 'commissions'), due = dueCents(state, order.id), paid = paidCents(state, order.id)
  if (order.status === '已作废') throw new AppError('BUSINESS_RULE', '委托已作废。')
  if (paid >= due) return
  if (order.data.settlement !== '信用') throw new AppError('BUSINESS_RULE', '预付委托尚未结清，不能发放报告。')
  const customer = get(state, order.data.customerId, 'customers'); unexpired({ ...customer, data: { ...customer.data, validUntil: customer.data.creditUntil } })
  const orders = state.records.filter(r => r.kind === 'commissions' && r.data.customerId === customer.id)
  const balance = orders.reduce((sum, r) => sum + Math.max(0, dueCents(state, r.id) - paidCents(state, r.id)), 0)
  if (balance > cents(customer.data.creditLimit)) throw new AppError('BUSINESS_RULE', '客户应收余额超过信用额度。')
  if (state.records.some(r => r.kind === 'receivables' && orders.some(o => o.id === r.data.commissionId) && String(r.data.dueDate) < today() && paidCents(state, String(r.data.commissionId)) < dueCents(state, String(r.data.commissionId)))) throw new AppError('BUSINESS_RULE', '客户存在逾期应收，不能发放报告。')
}
function touch(r: BusinessRecord) { r.version++; r.updatedAt = now() }
function syncUser(state: LimsDatabase, r: BusinessRecord) {
  if (r.kind !== 'users') return
  const actor: Actor = { id: r.id, name: r.name, roles: ids(r.data.roles), departmentId: String(r.data.departmentId), scope: r.data.scope === 'all' ? 'all' : 'department' }
  const index = state.actors.findIndex(a => a.id === r.id); if (index < 0) state.actors.push(actor); else state.actors[index] = actor
}
function settleReceivables(state: LimsDatabase) {
  for (const due of state.records.filter(r => r.kind === 'receivables')) {
    const paid = paidCents(state, String(due.data.commissionId)), total = dueCents(state, String(due.data.commissionId))
    const status = paid >= total ? '已结清' : paid > 0 ? '部分收款' : '待收款'
    if (due.status !== status) { due.status = status; touch(due) }
  }
}
function inventoryChange(state: LimsDatabase, id: Value | undefined, delta: number) { const lot = get(state, id, 'inventory'); const qty = number(lot.data.quantity) + delta; if (qty < 0) throw new AppError('BUSINESS_RULE', '物料库存不足。'); lot.data.quantity = Math.round(qty * 1000000) / 1000000; touch(lot) }
function samplePosition(state: LimsDatabase, sampleId: string) {
  const moves = state.records.filter(r => r.kind === 'movements' && r.status === '已完成' && r.data.sampleId === sampleId)
  return moves.at(-1)?.data.operation || '未入库'
}
function executeMovement(state: LimsDatabase, actor: Actor, r: BusinessRecord) {
  const s = state.samples.find(s => s.id === r.data.sampleId); if (!s || s.status !== 'received') throw new AppError('BUSINESS_RULE', '仅已接收样品可以流转。')
  const position = samplePosition(state, s.id), operation = r.data.operation
  if (position === '处置') throw new AppError('BUSINESS_RULE', '样品已处置。')
  if (number(r.data.quantity) > s.quantity) throw new AppError('BUSINESS_RULE', '流转数量超过样品数量。')
  if (operation !== '分样' && number(r.data.quantity) !== s.quantity) throw new AppError('BUSINESS_RULE', '整份样品流转数量须与样品数量一致；部分流转请先分样。')
  if (operation === '入库' && position !== '未入库') throw new AppError('BUSINESS_RULE', '已入库样品不能重复入库。')
  if (operation === '领用' && !['入库', '归还', '留样', '分样'].includes(String(position))) throw new AppError('BUSINESS_RULE', '样品须先入库或归还，不能重复领用。')
  if (operation === '归还' && position !== '领用') throw new AppError('BUSINESS_RULE', '仅已领用样品可以归还。')
  if (['入库', '归还', '留样'].includes(String(operation))) {
    const location = active(get(state, r.data.locationId, 'locations'))
    const occupancy = state.samples.filter(s => { const last = state.records.filter(x => x.kind === 'movements' && x.status === '已完成' && x.data.sampleId === s.id).at(-1); return last?.data.locationId === location.id && last.data.operation !== '领用' && last.data.operation !== '处置' }).length
    if (occupancy >= number(location.data.capacity)) throw new AppError('BUSINESS_RULE', '库位容量已满。')
  }
  if (operation === '处置' && state.records.some(t => t.kind === 'tasks' && t.data.sampleId === s.id && t.status !== '已完成')) throw new AppError('BUSINESS_RULE', '存在未完成检测任务，不能处置样品。')
  if (operation === '分样') {
    if (number(r.data.quantity) >= s.quantity) throw new AppError('BUSINESS_RULE', '分样数量须小于原样品数量。')
    const split = structuredClone(s); split.id = crypto.randomUUID(); split.code = `${s.code}-S${state.samples.filter(x => x.code.startsWith(`${s.code}-S`)).length + 1}`; split.name = `${s.name}（分样）`; split.quantity = number(r.data.quantity); split.createdAt = now(); split.updatedAt = now(); split.events = [{ id: crypto.randomUUID(), at: now(), actor: actor.name, action: 'created', reason: `来源 ${s.code}` }]; s.quantity -= split.quantity; state.samples.push(split); state.sampleMeta[split.id] = { departmentId: r.departmentId, ownerId: actor.id, version: 1 }; r.data.childSampleId = split.id
    const link = state.records.find(x => x.kind === 'sampleLinks' && x.status === '已关联' && x.data.sampleId === s.id)
    if (link) newRecord(state, actor, 'sampleLinks', `${split.code} 委托关联`, { sampleId: split.id, commissionId: link.data.commissionId! }, '已关联')
  }
}
function beforeAction(state: LimsDatabase, actor: Actor, r: BusinessRecord, action: string) {
  const d = r.data
  validateBusiness(state, r)
  if (r.kind === 'sampleLinks' && action === 'link') {
    const order = get(state, d.commissionId, 'commissions'), s = state.samples.find(s => s.id === d.sampleId)!
    if (!['已受理', '执行中'].includes(order.status)) throw new AppError('BUSINESS_RULE', '只能关联已受理或执行中的委托。')
    if (state.records.some(x => x.kind === 'sampleLinks' && x.status === '已关联' && x.data.sampleId === s.id)) throw new AppError('BUSINESS_RULE', '样品已关联委托。')
    if (s.customer !== get(state, order.data.customerId, 'customers').name) throw new AppError('BUSINESS_RULE', '样品客户与委托客户不一致。')
  }
  if (r.kind === 'commissions' && action === 'complete') {
    if (!state.records.some(x => x.kind === 'reports' && x.data.commissionId === r.id && ['已发放', '已归档'].includes(x.status))) throw new AppError('BUSINESS_RULE', '委托尚无已发放报告。')
    if (state.records.some(x => x.kind === 'tasks' && x.data.commissionId === r.id && x.status !== '已完成')) throw new AppError('BUSINESS_RULE', '还有未完成的检测任务。')
  }
  if (r.kind === 'sampling' && action === 'dispatch') { const o = get(state, d.commissionId, 'commissions'); if (!['已受理', '执行中'].includes(o.status) || o.data.source !== '现场采样') throw new AppError('BUSINESS_RULE', '需要已受理的现场采样委托。') }
  if (r.kind === 'movements' && action === 'post') executeMovement(state, actor, r)
  if (r.kind === 'tasks' && action === 'start') {
    if (d.assigneeId !== actor.id && !actor.roles.includes('admin')) throw new AppError('FORBIDDEN', '仅任务检测人员可以开始检测。')
    const authorization = state.records.find(x => x.kind === 'personnel' && x.status === '有效' && x.data.actorId === d.assigneeId && ids(x.data.projectIds).includes(String(d.projectId)))
    if (!authorization) throw new AppError('BUSINESS_RULE', '检测人员尚未获得项目授权。'); unexpired(authorization)
    const equipment = get(state, d.equipmentId, 'equipment'); unexpired(equipment); unexpired(equipment, 'checkUntil'); if (equipment.data.condition !== '正常') throw new AppError('BUSINESS_RULE', '设备当前不可用。')
    const method = get(state, d.methodId, 'methods'); unexpired(method); d.methodSnapshot = JSON.stringify(method)
    d.projectSnapshot = JSON.stringify(get(state, d.projectId, 'projects'))
    if (d.lotId) { unexpired(get(state, d.lotId, 'inventory')); inventoryChange(state, d.lotId, -number(d.consumption)); d.materialCostCents = Math.round(number(d.consumption) * cents(get(state, d.lotId).data.unitCost)) }
    const position = samplePosition(state, String(d.sampleId))
    if (position === '领用') {
      if (state.records.some(t => t.kind === 'tasks' && t.id !== r.id && t.data.sampleId === d.sampleId && t.status === '执行中' && t.data.assigneeId !== d.assigneeId)) throw new AppError('BUSINESS_RULE', '样品已由其他检测人员领用。')
    } else { const m = newRecord(state, actor, 'movements', `${r.name}领样`, { sampleId: d.sampleId!, operation: '领用', quantity: state.samples.find(s => s.id === d.sampleId)!.quantity, assigneeId: d.assigneeId!, destination: r.code }, '草稿'); executeMovement(state, actor, m); m.status = '已完成' }
  }
  if (r.kind === 'tasks' && action === 'record') {
    if (d.assigneeId !== actor.id && !actor.roles.includes('admin')) throw new AppError('FORBIDDEN', '仅检测人员可以填写记录。')
    const method = JSON.parse(String(d.methodSnapshot)) as BusinessRecord, p = d.projectSnapshot ? JSON.parse(String(d.projectSnapshot)) as BusinessRecord : get(state, d.projectId, 'projects')
    const result = d.resultType === '定性' ? String(d.qualitative || '').trim() : calculateFormula(String(method.data.formula), number(d.rawValue)).toFixed(number(p.data.precision))
    if (!result) throw new AppError('BUSINESS_RULE', '请填写定性结果。')
    d.result = result; d.formula = method.data.formula!; d.unit = p.data.unit!; d.judgment = d.resultType === '定量' ? (Number(result) >= number(p.data.lower) && Number(result) <= number(p.data.upper) ? '符合' : '不符合') : '定性结果'; d.recordedBy = actor.id
  }
  if (r.kind === 'tasks' && action === 'submit' && (!d.result || !d.rawRecord || d.qc !== '通过')) throw new AppError('BUSINESS_RULE', '请完成原始记录并确认质控通过。')
  if (r.kind === 'tasks' && action === 'finishSample') { const m = newRecord(state, actor, 'movements', `${r.code}检毕归还`, { sampleId: d.sampleId!, operation: '归还', quantity: state.samples.find(s => s.id === d.sampleId)!.quantity, assigneeId: actor.id, locationId: d.locationId!, destination: '检毕归还' }); executeMovement(state, actor, m); m.status = '已完成' }
  if (r.kind === 'batches' && action === 'complete' && state.records.some(x => x.kind === 'tasks' && x.data.batchId === r.id && x.status !== '已完成')) throw new AppError('BUSINESS_RULE', '批次仍有未完成任务。')
  if (r.kind === 'reports' && ['submit', 'sign'].includes(action)) checkReport(state, r)
  if (r.kind === 'reports' && action === 'release') releaseCheck(state, r)
  if (r.kind === 'payments' && action === 'post') { const remaining = dueCents(state, String(d.commissionId)) - paidCents(state, String(d.commissionId)); if (cents(d.amount) > remaining) throw new AppError('BUSINESS_RULE', '收款金额超过未核销应收。') }
  if (r.kind === 'invoices' && action === 'post') {
    if (state.records.some(x => x.id !== r.id && x.kind === 'invoices' && x.status === '已登记' && x.data.invoiceNumber === d.invoiceNumber)) throw new AppError('BUSINESS_RULE', '发票号码已登记。')
    const invoiced = state.records.filter(x => x.kind === 'invoices' && x.status === '已登记' && x.data.commissionId === d.commissionId).reduce((s, x) => s + cents(x.data.amount), 0)
    if (invoiced + cents(d.amount) > dueCents(state, String(d.commissionId))) throw new AppError('BUSINESS_RULE', '开票金额超过委托应收。')
  }
  if (r.kind === 'stockMoves' && action === 'post') { const positive = ['退库', '盘盈'].includes(String(d.operation)); if (!positive) unexpired(get(state, d.lotId)); inventoryChange(state, d.lotId, number(d.quantity) * (positive ? 1 : -1)) }
  if (r.kind === 'equipmentLoans' && action === 'borrow') { unexpired(get(state, d.equipmentId)); if (state.records.some(x => x.kind === 'equipmentLoans' && x.status === '使用中' && x.data.equipmentId === d.equipmentId)) throw new AppError('BUSINESS_RULE', '设备已被领用。') }
  if (r.kind === 'outsourcing' && action === 'submit') unexpired(get(state, d.supplierId, 'suppliers'))
  if (r.kind === 'outsourcing' && action === 'accept' && !state.attachments.some(a => a.entityId === r.id)) throw new AppError('BUSINESS_RULE', '请上传外包报告或验收证据。')
  if (r.kind === 'users' && action === 'disable' && ids(d.roles).includes('admin') && !state.records.some(x => x.id !== r.id && x.kind === 'users' && x.status === '有效' && ids(x.data.roles).includes('admin'))) throw new AppError('BUSINESS_RULE', '不能停用最后一个有效管理员。')
  if (r.kind === 'reportChanges' && action === 'submit') { const report = get(state, d.reportId, 'reports'); if (!['已签发', '已发放', '已归档'].includes(report.status)) throw new AppError('BUSINESS_RULE', '仅已签发报告可以申请更改。') }
}
function checkReport(state: LimsDatabase, r: BusinessRecord) {
  const order = get(state, r.data.commissionId, 'commissions'); if (!['已受理', '执行中', '已完成'].includes(order.status)) throw new AppError('BUSINESS_RULE', '委托状态不允许签发报告。')
  active(get(state, r.data.templateId, 'reportTemplates'))
  const tasks = state.records.filter(x => x.kind === 'tasks' && x.data.commissionId === order.id)
  const outside = state.records.filter(x => x.kind === 'outsourcing' && x.data.commissionId === order.id)
  const links = state.records.filter(x => x.kind === 'sampleLinks' && x.status === '已关联' && x.data.commissionId === order.id)
  if (!links.length) throw new AppError('BUSINESS_RULE', '委托尚未关联样品。')
  for (const link of links) for (const project of ids(order.data.projectIds)) {
    if (!tasks.some(t => t.data.sampleId === link.data.sampleId && t.data.projectId === project && t.status === '已完成') && !outside.some(t => t.data.sampleId === link.data.sampleId && t.data.projectId === project && t.status === '已验收')) throw new AppError('BUSINESS_RULE', '样品检测项目尚未全部完成并复核。')
  }
  if (tasks.some(t => t.status !== '已完成' || t.data.qc !== '通过')) throw new AppError('BUSINESS_RULE', '存在未完成任务或失败的质控。')
  if (state.records.some(q => q.kind === 'qualityCases' && q.data.blocking === '是' && q.status !== '已关闭' && (q.data.commissionId === order.id || tasks.some(t => t.id === q.data.taskId)))) throw new AppError('BUSINESS_RULE', '存在未关闭的阻断质量事项。')
}
function afterApproved(state: LimsDatabase, actor: Actor, r: BusinessRecord, approval: ApprovalInstance) {
  const d = r.data, action = approval.action
  if (r.kind === 'commissions' && action === 'submit') {
    const snapshot = amountSnapshot(state, r); d.snapshot = JSON.stringify(snapshot); d.amountCents = snapshot.amountCents; r.status = '已受理'
    const customer = get(state, d.customerId), due = new Date(); due.setDate(due.getDate() + (d.settlement === '信用' ? number(customer.data.creditDays) : 0))
    newRecord(state, { ...actor, departmentId: r.departmentId }, 'receivables', `${r.code}应收`, { commissionId: r.id, amount: snapshot.amountCents / 100, dueDate: due.toISOString().slice(0, 10) }, '待收款')
  } else if (r.kind === 'quotations') { const snapshot = amountSnapshot(state, r); d.snapshot = JSON.stringify(snapshot); d.amountCents = snapshot.amountCents }
  else if (r.kind === 'commissions' && action === 'change') { r.status = String(d.previousStatus); d.requirements = d.proposedRequirements!; d.dueDate = d.proposedDueDate!; d.changeVersion = number(d.changeVersion) + 1; const previous = String(d.snapshot); d.snapshotHistory = [...ids(d.snapshotHistory), previous]; d.snapshot = JSON.stringify({ ...JSON.parse(previous), requirements: d.requirements, dueDate: d.dueDate, at: now(), revision: d.changeVersion }) }
  else if (r.kind === 'commissions' && action === 'cancel') { if (state.records.some(x => x.kind === 'reports' && x.data.commissionId === r.id && ['已发放', '已归档'].includes(x.status))) throw new AppError('BUSINESS_RULE', '已有发放报告的委托不能直接作废。'); r.status = '已作废' }
  else if (r.kind === 'tasks') {
    if (action === 'change') { r.status = '已完成'; const copy = { ...d }; for (const key of ['result', 'rawRecord', 'qualitative', 'rawValue', 'qc', 'recordedBy', 'methodSnapshot']) delete copy[key]; copy.previousTaskId = r.id; newRecord(state, { ...actor, departmentId: r.departmentId }, 'tasks', `${r.name}（更正）`, copy, '待分派') }
    else { if (approval.applicantId === actor.id || d.recordedBy === actor.id) throw new AppError('FORBIDDEN', '不能复核本人检测的结果。'); if (d.qc !== '通过') throw new AppError('BUSINESS_RULE', '质控未通过。'); r.status = '已完成'; d.reviewedBy = actor.name; d.reviewedAt = now() }
  } else if (r.kind === 'reports') {
    if (action === 'submit') { checkReport(state, r); r.status = '已审核'; d.reviewerId = actor.id; d.reviewerName = actor.name }
    if (action === 'sign') {
      checkReport(state, r); if (r.ownerId === actor.id || d.reviewerId === actor.id) throw new AppError('FORBIDDEN', '编制、审核和批准须由不同人员完成。')
      const order = get(state, d.commissionId), template = get(state, d.templateId)
      const results = state.records.filter(t => ['tasks', 'outsourcing'].includes(t.kind) && t.data.commissionId === order.id && ['已完成', '已验收'].includes(t.status)).map(t => ({ sample: state.samples.find(s => s.id === t.data.sampleId)?.name || '', sampleCode: state.samples.find(s => s.id === t.data.sampleId)?.code || '', project: get(state, t.data.projectId).name, method: t.data.methodSnapshot ? (JSON.parse(String(t.data.methodSnapshot)) as BusinessRecord).data.standard : get(state, t.data.methodId).data.standard, result: t.data.result, unit: t.data.unit || get(state, t.data.projectId).data.unit, judgment: t.data.judgment || '外包结果', source: t.kind === 'outsourcing' ? '外包' : '本实验室' }))
      d.signedSnapshot = JSON.stringify({ code: r.code, name: r.name, conclusion: d.conclusion, customer: get(state, order.data.customerId).name, orderCode: order.code, template: template.data, results, reviewer: d.reviewerName, approver: actor.name, signedAt: now() }); d.signedBy = actor.name; d.signedAt = now(); r.status = '已签发'
    }
    if (action === 'exception') { r.status = '已发放'; d.exceptionReason = approval.reason; d.releasedAt = now() }
  } else if (r.kind === 'reportChanges') {
    const old = get(state, d.reportId, 'reports'); if (!['已签发', '已发放', '已归档'].includes(old.status)) throw new AppError('BUSINESS_RULE', '原报告已更改或作废。')
    old.status = '已替代'; touch(old)
    const revised = newRecord(state, { ...actor, departmentId: old.departmentId }, 'reports', `${old.name}（修订）`, { commissionId: old.data.commissionId!, templateId: old.data.templateId!, conclusion: d.conclusion!, previousReportId: old.id, reportRevision: number(old.data.reportRevision) + 1 })
    d.newReportId = revised.id; audit(state, actor, old, '批准报告更改', String(d.reason))
  } else if (r.kind === 'refunds') {
    const p = get(state, d.paymentId, 'payments'); if (p.status !== '已入账') throw new AppError('BUSINESS_RULE', '原收款尚未入账。')
    const refunded = state.records.filter(x => x.kind === 'refunds' && x.id !== r.id && x.status === '已批准' && x.data.paymentId === p.id).reduce((s, x) => s + cents(x.data.amount), 0)
    if (refunded + cents(d.amount) > cents(p.data.amount)) throw new AppError('BUSINESS_RULE', '退款冲销金额超过原收款剩余金额。')
    settleReceivables(state)
  } else if (r.kind === 'qualityCases') r.status = '已验证'
  else if (r.kind === 'equipmentPlans') {
    const equipment = get(state, d.equipmentId); if (d.result === '合格') { equipment.data[['期间核查'].includes(String(d.type)) ? 'checkUntil' : 'validUntil'] = d.validUntil!; equipment.data.condition = '正常' } else equipment.data.condition = '停用'; touch(equipment); r.status = '已完成'; audit(state, actor, equipment, '设备计划执行验证')
  } else if (r.kind === 'outsourcing' && action === 'accept') {
    r.status = '已验收'; newRecord(state, { ...actor, departmentId: r.departmentId }, 'payables', `${r.code}应付`, { outsourcingId: r.id, amount: d.amount!, dueDate: d.dueDate! }, '待付款')
  }
}
export function createLimsService(repo: Repository, actorId: () => string = () => currentActor.value.id) {
  function actor(state: LimsDatabase) { if (repo === repository && sessionLocked.value) throw new AppError('LOCKED', '工作空间已锁定。'); return resolveActor(state, actorId()) }
  function access(state: LimsDatabase, kind: string, id?: string) { const a = actor(state); if (!canRead(a, kind)) throw new AppError('FORBIDDEN', '当前身份无权访问此模块。'); const r = id ? get(state, id, kind) : undefined; if (r) assertScope(a, r); return { a, r } }
  return {
    async list(kind: string, query: ListQuery = {}) {
      const state = await repo.read(), { a } = access(state, kind)
      let items = state.records.filter(r => r.kind === kind && inScope(a, r))
      if (query.keyword?.trim()) { const q = query.keyword.trim().toLowerCase(); items = items.filter(r => `${r.code} ${r.name} ${Object.values(r.data).filter(v => typeof v === 'string' && v.length < 1000).join(' ')}`.toLowerCase().includes(q)) }
      if (query.status) items = items.filter(r => r.status === query.status)
      if (query.from) items = items.filter(r => r.createdAt.slice(0, 10) >= query.from!)
      if (query.to) items = items.filter(r => r.createdAt.slice(0, 10) <= query.to!)
      const sort = ['code', 'name', 'status', 'createdAt'].includes(query.sort || '') ? query.sort as 'code' | 'name' | 'status' | 'createdAt' : 'createdAt'
      items.sort((a, b) => String(a[sort]).localeCompare(String(b[sort]), 'zh-CN', { numeric: true }) * (query.direction === 'asc' ? 1 : -1))
      const pageSize = [10, 20, 50].includes(query.pageSize || 0) ? query.pageSize! : 10, page = Math.min(Math.max(1, Number.isFinite(query.page) ? Math.floor(query.page || 1) : 1), Math.max(1, Math.ceil(items.length / pageSize)))
      return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
    },
    async detail(kind: string, id: string) { const state = await repo.read(); const { r } = access(state, kind, id); return { record: r!, audits: state.audits.filter(x => x.entityId === id), approvals: state.approvals.filter(x => x.entityId === id), attachments: state.attachments.filter(x => x.entityId === id).map(({ blob: _blob, ...meta }) => meta) } },
    async options(reference: string) {
      const state = await repo.read(), a = actor(state)
      if (reference === 'actors') return state.actors.filter(x => a.scope === 'all' || x.departmentId === a.departmentId).filter(x => state.records.find(r => r.kind === 'users' && r.id === x.id)?.status === '有效').map(x => ({ id: x.id, name: x.name }))
      if (reference === 'samples') return state.samples.filter(s => inScope(a, state.sampleMeta[s.id] ?? { departmentId: 'lab' })).map(s => ({ id: s.id, name: `${s.code} · ${s.name}` }))
      return state.records.filter(r => r.kind === reference && inScope(a, r) && !['已停用', '已作废', '已替代'].includes(r.status)).map(r => ({ id: r.id, name: `${r.name} · ${r.code}` }))
    },
    async save(kind: string, input: { name: string; data: Fields; id?: string; version?: number }) {
      return repo.write(state => {
        const { a, r } = access(state, kind, input.id), def = moduleMap[kind]!
        assertRole(a, def.roles); if (!input.name.trim() || input.name.length > 150) throw problem('VALIDATION', '请输入名称（不超过 150 字）。', 'name')
        if (!input.id && ['receivables', 'payables'].includes(kind)) throw new AppError('BUSINESS_RULE', '此记录由业务流程自动生成。')
        validateFields(state, a, def.fields, input.data)
        const clean = Object.fromEntries(def.fields.map(f => [f.key, input.data[f.key] ?? (f.type === 'multi' ? [] : '')])) as Fields
        if (r) {
          
          if (!def.editable.includes(r.status)) throw new AppError('BUSINESS_RULE', '当前状态不可编辑。')
          const before = structuredClone(r); r.name = input.name.trim(); r.data = { ...r.data, ...clean }; validateBusiness(state, r); touch(r); syncUser(state, r); audit(state, a, r, '编辑', '', before); return r
        }
        const created = newRecord(state, a, kind, input.name, clean); validateBusiness(state, created); syncUser(state, created); return created
      })
    },
    async act(kind: string, id: string, actionId: string, version: number, reason = '', fields: Fields = {}) {
      return repo.write(state => {
        const { a, r: entity } = access(state, kind, id), r = entity!, def = moduleMap[kind]!, action = def.actions.find(x => x.id === actionId)
        if (!action || !action.from.includes(r.status)) throw new AppError('BUSINESS_RULE', '当前状态不允许此操作，请刷新。')
        assertRole(a, action.roles ?? def.roles); 
        if (action.reason && !reason.trim()) throw problem('VALIDATION', '请填写操作原因。', 'reason')
        const recordConfig = kind === 'tasks' && actionId === 'record' ? recordConfiguration(r) : undefined
        const actionDefinitions = [...(action.fields ?? []), ...(recordConfig?.fields ?? [])]
        validateFields(state, a, actionDefinitions, fields)
        if (recordConfig?.columns.length) {
          let rows: unknown
          try { rows = JSON.parse(String(fields.recordTable || '[]')) } catch { throw new AppError('BUSINESS_RULE', '明细表数据无效。') }
          if (!Array.isArray(rows) || !rows.length || rows.length > 100 || rows.some(row => !Array.isArray(row) || row.length !== recordConfig.columns.length || row.some(v => typeof v !== 'string' || !v.trim()))) throw new AppError('BUSINESS_RULE', '请完整填写至少一行原始记录明细。')
        }
        const before = structuredClone(r), oldStatus = r.status
        const safeFields = Object.fromEntries(actionDefinitions.map(f => [f.key, fields[f.key] ?? '']))
        if (recordConfig) { safeFields.recordTable = String(fields.recordTable || '[]'); safeFields.recordColumns = JSON.stringify(recordConfig.columns) }
        if (kind === 'commissions' && actionId === 'change') { r.data.proposedRequirements = safeFields.requirements!; r.data.proposedDueDate = safeFields.dueDate! } else Object.assign(r.data, safeFields)
        beforeAction(state, a, r, actionId)
        r.status = action.to
        if (action.approval) {
          const config = state.records.filter(x => x.kind === 'approvalConfigs' && x.status === '有效' && x.data.moduleId === kind).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0]
          const approval: ApprovalInstance = { id: crypto.randomUUID(), kind, entityId: id, action: actionId, applicantId: a.id, applicantName: a.name, approverRoles: approvalRoles(kind, actionId), approverIds: ids(config?.data.approverIds), configVersion: config?.version ?? 1, status: 'pending', createdAt: now(), reason: reason.trim() }
          r.data.previousStatus = oldStatus; state.approvals.push(approval)
        }
        if (kind === 'tasks' && ['retest', 'copyStructure'].includes(actionId)) { const copy = Object.fromEntries(moduleMap.tasks!.fields.map(f => [f.key, r.data[f.key] ?? ''])) as Fields; copy.previousTaskId = r.id; const task = newRecord(state, a, 'tasks', `${r.name}（${actionId === 'retest' ? '复测' : '记录结构副本'}）`, copy, '待分派'); r.data.retestId = task.id }
        if (kind === 'sampling' && actionId === 'handover') {
          const order = get(state, r.data.commissionId), customer = get(state, order.data.customerId), sid = crypto.randomUUID(), code = `SP${now().slice(0, 10).replaceAll('-', '')}-${sid.slice(0, 8)}`
          state.samples.push({ id: sid, code, name: r.name, customer: customer.name, category: '其他', quantity: number(r.data.quantity), unit: String(r.data.unit), projects: ids(order.data.projectIds).map(p => get(state, p).name), contact: String(customer.data.contact), phone: String(customer.data.phone), storage: String(r.data.containers), notes: String(r.data.fieldRecord), status: 'pending', createdAt: now(), updatedAt: now(), events: [{ id: crypto.randomUUID(), actor: a.name, action: 'created', at: now(), reason: `采样任务 ${r.code}` }] }); state.sampleMeta[sid] = { departmentId: r.departmentId, ownerId: a.id, version: 1 }; r.data.sampleId = sid; newRecord(state, a, 'sampleLinks', `${code} 委托关联`, { sampleId: sid, commissionId: order.id }, '已关联')
        }
        if (kind === 'purchases' && actionId === 'receive') newRecord(state, a, 'inventory', String(r.data.material), { type: '耗材', batch: r.data.batch!, quantity: r.data.quantity!, unit: r.data.unit!, unitCost: number(r.data.amount) / number(r.data.quantity), validUntil: r.data.validUntil!, certificate: r.data.certificate!, supplierId: r.data.supplierId! }, '有效')
        if (kind === 'reports' && actionId === 'release') r.data.releasedAt = now()
        if (kind === 'payments' && actionId === 'post') settleReceivables(state)
        syncUser(state, r); touch(r); audit(state, a, r, action.label, reason, before); return r
      })
    },
    async approvals() { const state = await repo.read(), a = actor(state); return state.approvals.filter(p => { const r = get(state, p.entityId); return inScope(a, r) && (a.id === p.applicantId || hasRole(a, p.approverRoles) || p.approverIds.includes(a.id)) }).map(p => ({ ...p, record: get(state, p.entityId) })) },
    async decide(id: string, approve: boolean, reason: string) {
      const apply = (state: LimsDatabase) => {
        const a = actor(state), p = state.approvals.find(p => p.id === id)
        if (!p || p.status !== 'pending') throw new AppError('BUSINESS_RULE', '审批已处理或不存在。')
        const r = get(state, p.entityId); assertScope(a, r)
        if (a.id === p.applicantId || (approve && a.id === r.ownerId)) throw new AppError('FORBIDDEN', '不能审批本人提交或创建的事项。')
        if (p.approverIds.length ? !p.approverIds.includes(a.id) : !hasRole(a, p.approverRoles)) throw new AppError('FORBIDDEN', '当前身份不是此流程的审批人。')
        if (!reason.trim()) throw problem('VALIDATION', '请填写审批意见。', 'reason')
        const before = structuredClone(r)
        p.status = approve ? 'approved' : 'rejected'; p.resolvedAt = now(); p.resolverId = a.id
        if (approve) { r.status = '已批准'; afterApproved(state, a, r, p) }
        else r.status = r.kind === 'qualityCases' ? '处理中' : r.kind === 'tasks' ? (p.action === 'change' ? '已完成' : '执行中') : ['change', 'cancel', 'exception'].includes(p.action) ? String(r.data.previousStatus) : p.action === 'sign' ? '已审核' : '已退回'
        touch(r); audit(state, a, r, approve ? '审批通过' : '审批退回', reason, before); return r
      }
      if (repo === repository && approve) {
        const staged = await repo.read(), request = staged.approvals.find(p => p.id === id)
        if (request?.kind === 'reports' && request.action === 'sign') {
          const signed = apply(staged), signer = actorId()
          const { renderSnapshotPdf } = await import('../reports/reportPdf')
          const blob = await renderSnapshotPdf(JSON.parse(String(signed.data.signedSnapshot)))
          staged.attachments.push({ id: `signed-pdf-${signed.id}`, entityId: signed.id, name: `${signed.code}.pdf`, type: 'application/pdf', size: blob.size, blob, actor: String(signed.data.signedBy), at: String(signed.data.signedAt) })
          return repo.write(current => {
            if (actorId() !== signer) throw new AppError('FORBIDDEN', '当前身份已变化，请重新操作。')
            const latest = apply(current)
            // Commit this report only; unrelated records may have changed while rendering.
            latest.data = structuredClone(signed.data)
            current.attachments.push(staged.attachments.at(-1)!)
            return latest
          })
        }
      }
      return repo.write(apply)
    },
    async attach(kind: string, id: string, file: File) {
      if (!file.size || file.size > 20 * 1024 * 1024) throw new AppError('BUSINESS_RULE', '请选择 20 MB 以内的非空附件。')
      const blob = new Blob([await file.arrayBuffer()], { type: file.type })
      return repo.write(state => { const { a, r } = access(state, kind, id); assertRole(a, moduleMap[kind]!.roles); if (['已签发', '已发放', '已归档', '已替代', '已完成', '已作废'].includes(r!.status)) throw new AppError('BUSINESS_RULE', '已冻结记录不能追加附件。'); const item = { id: crypto.randomUUID(), entityId: id, name: file.name, type: file.type, size: file.size, blob, actor: a.name, at: now() }; state.attachments.push(item); audit(state, a, r!, '添加附件', file.name); return item.id })
    },
    async attachment(id: string) { const state = await repo.read(); const item = state.attachments.find(a => a.id === id); if (!item) throw new AppError('NOT_FOUND', '附件不存在。'); const r = get(state, item.entityId); access(state, r.kind, r.id); return item },
    async audits(authorization = false) { const state = await repo.read(), a = actor(state); assertRole(a, ['system']); return state.audits.filter(x => !authorization || ['users', 'personnel', 'approvalConfigs'].includes(x.kind)).slice().reverse() },
    async statistics() {
      const state = await repo.read(), a = actor(state), records = state.records.filter(r => inScope(a, r) && canRead(a, r.kind))
      const orders = records.filter(r => r.kind === 'commissions'), tasks = records.filter(r => r.kind === 'tasks')
      const finance = hasRole(a, ['finance'])
      const rows = finance ? orders.filter(order => !!order.data.snapshot).map(order => { const due = dueCents(state, order.id), paid = paidCents(state, order.id); const snapshot = order.data.snapshot ? JSON.parse(String(order.data.snapshot)) : { lines: [] }; const labor = (snapshot.lines as { laborCents: number }[]).reduce((s, l) => s + l.laborCents, 0); const material = state.records.filter(r => r.kind === 'tasks' && r.data.commissionId === order.id).reduce((s, t) => s + number(t.data.materialCostCents), 0); const external = state.records.filter(r => r.kind === 'outsourcing' && r.status === '已验收' && r.data.commissionId === order.id).reduce((s, r) => s + cents(r.data.amount), 0); return { id: order.id, code: order.code, name: order.name, due, paid, balance: due - paid, cost: labor + material + external, profit: due - labor - material - external } }) : []
      const pending = state.approvals.filter(p => p.status === 'pending' && p.applicantId !== a.id && inScope(a, get(state, p.entityId)) && (p.approverIds.length ? p.approverIds.includes(a.id) : hasRole(a, p.approverRoles)))
      const sampleStats = hasRole(a, ['samples', 'commissions', 'testing', 'reviewer', 'approver']) ? state.samples.filter(s => inScope(a, state.sampleMeta[s.id] ?? { departmentId: 'lab' })).reduce((stats, sample) => { stats.total++; stats[sample.status]++; return stats }, { total: 0, pending: 0, received: 0, returned: 0 }) : null
      const qualityTrend = Array.from({length: 6}, (_, i) => { const date = new Date(); date.setMonth(date.getMonth() - 5 + i); const month = date.toISOString().slice(0,7); const cases = records.filter(r => r.kind === 'qualityCases' && r.createdAt.startsWith(month)); return {month,total:cases.length,closed:cases.filter(r => r.status === '已关闭').length} })
      const equipmentUsage = records.filter(r => r.kind === 'equipment').map(e => ({name:e.name,total:tasks.filter(t => t.data.equipmentId === e.id).length,active:tasks.filter(t => t.data.equipmentId === e.id && t.status === '执行中').length}))
      return { sampleStats, qualityTrend, equipmentUsage, counts: modules.filter(m => canRead(a, m.id)).map(m => ({ id: m.id, title: m.title, total: records.filter(r => r.kind === m.id).length })), orders: orders.length, tasks: tasks.length, reports: records.filter(r => r.kind === 'reports').length, pending, rows, overdue: records.filter(r => r.data.dueDate && String(r.data.dueDate) < today() && !['已完成', '已归档', '已关闭', '已作废', '已付款', '已结清', '已发放', '已替代', '已登记'].includes(r.status)), recent: records.filter(r => ['commissions','sampling','tasks','reports','payments','qualityCases'].includes(r.kind)).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 10), workload: state.actors.filter(x => a.scope === 'all' || x.departmentId === a.departmentId).map(person => ({ name: person.name, total: tasks.filter(t => t.data.assigneeId === person.id).length, completed: tasks.filter(t => t.data.assigneeId === person.id && t.status === '已完成').length })), averageHours: tasks.filter(t => t.status === '已完成').reduce((s, t) => s + (Date.parse(t.updatedAt) - Date.parse(t.createdAt)) / 3600000, 0) / Math.max(1, tasks.filter(t => t.status === '已完成').length) }
    },
  }
}
export const limsService = createLimsService(repository)
