import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import { canWriteSuppliers, emptySupplier, supplierFields, supplierSearchFields, evaluationSearchFields, supplierColumns, evaluationColumns, type SupplierRecord, type EvaluationRecord, type SupplierListKind } from '../src/types/quality/equipmentSuppliers'
import { registrationCsv } from './registrationDomain'
const text = (value: unknown, key: string, label: string, max = 2000) => {
  if (typeof value !== 'string' || value.length > max) throw problem('VALIDATION', `${label}不能超过 ${max} 个字符。`, key)
  return value.trim()
}
function ids(value: unknown): string[] | undefined {
  if (value === undefined) return
  if (!Array.isArray(value) || value.length > 1000 || value.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(value).size !== value.length) throw new AppError('VALIDATION', '所选记录有误。')
  return value
}
export function seedEquipmentSuppliers(state: RegistrationState, now = new Date()) {
  if (state.equipmentSuppliers) return
  const timestamp = now.toISOString(), date = timestamp.slice(0, 10)
  state.equipmentSuppliers = Array.from({ length: 7 }, (_, index) => ({ ...emptySupplier(), id: `equipment-supplier-${index + 1}`, version: 1, departmentId: index === 6 ? 'lab2' : 'lab', code: `GYS-${String(index + 1).padStart(3, '0')}`, name: `示例${['仪器设备', '计量服务', '设备维护', '实验室耗材', '环境检测设备', '技术服务', '分部设备'][index]}供应商`, address: '示例产业园', phone: '010-12345678', postalCode: '100000', contact: '示例联系人', services: ['仪器销售及安装', '仪器检定校准', '维修及保养'][index % 3]!, notes: '演示数据', createdAt: timestamp, updatedAt: timestamp, updatedBy: '演示用户' }))
  state.equipmentSupplierEvaluations = state.equipmentSuppliers.slice(0, 4).flatMap((supplier, index) => Array.from({ length: index === 0 ? 2 : 1 }, (_, n) => ({ id: `equipment-evaluation-${index}-${n}`, supplierId: supplier.id, departmentId: supplier.departmentId, name: supplier.name, services: supplier.services, version: 1, quality: '符合要求', price: '价格合理', service: '响应及时', opinions: n ? '持续跟踪服务质量' : '', conclusion: '合格', reviewDate: date, createdAt: timestamp, updatedAt: timestamp, updatedBy: '演示用户' })))
}
export function createEquipmentSuppliers(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canWriteSuppliers(user) : !user.roles.some(role => ['admin', 'quality', 'inventory', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行供应商及评价操作。')
    return user
  }
  const visible = (row: { departmentId: string }) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function supplier(id: unknown): SupplierRecord {
    actor(); const row = read().equipmentSuppliers?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '供应商不存在或无权访问，请刷新列表。')
    return { ...row }
  }
  function evaluation(id: unknown): EvaluationRecord {
    actor(); const row = read().equipmentSupplierEvaluations?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '评价不存在或无权访问，请刷新列表。')
    supplier(row.supplierId); return { ...row }
  }
  function query(kind: SupplierListKind, input: Record<string, unknown>, all = false) {
    actor()
    const field = input.field ?? '', value = text(input.value ?? '', 'value', '查询内容', 200).toLocaleLowerCase()
    const fields = kind === 'suppliers' ? supplierSearchFields : evaluationSearchFields
    if (typeof field !== 'string' || field && !fields.some(item => item.key === field)) throw new AppError('VALIDATION', '查询字段有误。')
    const requested = input.page ?? 1, size = input.pageSize ?? (kind === 'suppliers' ? 5 : 10)
    if (!Number.isSafeInteger(requested) || Number(requested) < 1 || typeof size !== 'number' || ![5, 10, 20, 50].includes(size)) throw new AppError('VALIDATION', '分页参数有误。')
    const selected = ids(input.ids), supplierIds = ids(input.supplierIds)
    supplierIds?.forEach(id => supplier(id))
    const supplierMap = new Map((read().equipmentSuppliers || []).filter(visible).map(row => [row.id, row]))
    const rows = kind === 'suppliers' ? [...supplierMap.values()] : (read().equipmentSupplierEvaluations || []).filter(row => visible(row) && supplierMap.has(row.supplierId) && (!supplierIds || supplierIds.includes(row.supplierId)))
    const filtered = rows.filter(row => (!selected || selected.includes(row.id)) && (!field || String(row[field as keyof typeof row] ?? '').toLocaleLowerCase().includes(value)))
      .sort((a, b) => kind === 'suppliers' ? (a as SupplierRecord).code.localeCompare((b as SupplierRecord).code, 'zh-CN', { numeric: true }) || a.name.localeCompare(b.name) : (b as EvaluationRecord).reviewDate.localeCompare((a as EvaluationRecord).reviewDate) || b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(filtered.length / size)))
    return { items: (all ? filtered : filtered.slice((page - 1) * size, page * size)).map(row => ({ ...row })), total: filtered.length, page, pageSize: size }
  }
  function save(kind: SupplierListKind, input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : kind === 'suppliers' ? supplier(input.id) : evaluation(input.id)
    
    const state = structuredClone(read()), now = new Date().toISOString()
    const metadata = { id: previous?.id || randomUUID(), version: (previous?.version || 0) + 1, createdAt: previous?.createdAt || now, updatedAt: now, updatedBy: user.name }
    if (kind === 'suppliers') {
      const draft = emptySupplier()
      for (const field of supplierFields) draft[field.key] = text(input[field.key] ?? '', field.key, field.label, field.max)
      draft.services = text(input.services ?? '', 'services', '服务商提供项目'); draft.notes = text(input.notes ?? '', 'notes', '备注')
      if (!draft.name) throw problem('VALIDATION', '请填写单位名称。', 'name')
      const departmentId = previous?.departmentId || user.departmentId
      if ((state.equipmentSuppliers || []).some(row => row.id !== previous?.id && row.departmentId === departmentId && draft.code && row.code.toLocaleLowerCase() === draft.code.toLocaleLowerCase())) throw problem('VALIDATION', '单位编码已存在。', 'code')
      const saved: SupplierRecord = { ...metadata, ...draft, departmentId }, rows = state.equipmentSuppliers ||= []
      if (previous) rows[rows.findIndex(row => row.id === saved.id)] = saved; else rows.push(saved)
      deps.write!(state); return saved
    }
    if (typeof input.supplierId !== 'string' || !input.supplierId) throw problem('VALIDATION', '请选择供应商。', 'supplierId')
    const parent = supplier(input.supplierId), reviewDate = input.reviewDate
    if (typeof reviewDate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(reviewDate) || !Number.isFinite(Date.parse(reviewDate)) || new Date(reviewDate).toISOString().slice(0, 10) !== reviewDate) throw problem('VALIDATION', '请选择有效的评审日期。', 'reviewDate')
    const saved: EvaluationRecord = { ...metadata, supplierId: parent.id, departmentId: parent.departmentId, name: parent.name, reviewDate, services: text(input.services ?? '', 'services', '服务提供项目'), quality: text(input.quality ?? '', 'quality', '质量评价', 500), price: text(input.price ?? '', 'price', '价格评价', 500), service: text(input.service ?? '', 'service', '服务评价', 500), opinions: text(input.opinions ?? '', 'opinions', '其它意见'), conclusion: text(input.conclusion ?? '', 'conclusion', '评审结论') }
    const rows = state.equipmentSupplierEvaluations ||= []
    if (previous) rows[rows.findIndex(row => row.id === saved.id)] = saved; else rows.push(saved)
    deps.write!(state); return saved
  }
  function remove(kind: SupplierListKind, input: Record<string, unknown>) {
    actor(true); const row = kind === 'suppliers' ? supplier(input.id) : evaluation(input.id)
    
    if (kind === 'suppliers' && read().equipmentSupplierEvaluations?.some(item => item.supplierId === row.id)) throw new AppError('VALIDATION', '该供应商存在评价记录，请先处理关联评价后再删除。')
    const state = structuredClone(read())
    if (kind === 'suppliers') state.equipmentSuppliers = state.equipmentSuppliers!.filter(item => item.id !== row.id)
    else state.equipmentSupplierEvaluations = state.equipmentSupplierEvaluations!.filter(item => item.id !== row.id)
    deps.write!(state); return { id: row.id }
  }
  return { query, save, remove, detail: (kind: SupplierListKind, id: unknown) => kind === 'suppliers' ? supplier(id) : evaluation(id), options: () => { actor(); return (read().equipmentSuppliers || []).filter(visible).map(({ id, name, services }) => ({ id, name, services })) }, export: (kind: SupplierListKind, input: Record<string, unknown>) => {
    const columns = kind === 'suppliers' ? supplierColumns : evaluationColumns
    return registrationCsv([columns.map(column => column.label), ...query(kind, input, true).items.map(row => columns.map(column => String(row[column.key as keyof typeof row] ?? '')))])
  } }
}
