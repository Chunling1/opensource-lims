import { randomUUID } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import { demoActors } from '../src/services/storage/demoActors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationDependencies, RegistrationState } from '../src/types/commissions/registration'
import type { EntryPersonCandidate, EntryPeoplePage } from '../src/types/testing/dataEntryDetail'
import { canWriteMaterials, emptyMaterial, emptyAcceptance, materialTextFields, acceptanceTextFields, acceptanceStatuses, materialColumns, acceptanceColumns, type MaterialKind, type MaterialRecord, type AcceptanceRecord } from '../src/types/quality/referenceMaterials'
import { registrationCsv } from './registrationDomain'
const text = (value: unknown, key: string, label: string, max = 200) => {
  if (typeof value !== 'string' || value.length > max) throw problem('VALIDATION', `${label}不能超过 ${max} 个字符。`, key)
  return value.trim()
}
function date(value: unknown, key: string, label: string, required = false) {
  const result = text(value ?? '', key, label, 10)
  if ((!result && required) || result && (!/^\d{4}-\d{2}-\d{2}$/.test(result) || !Number.isFinite(Date.parse(result)) || new Date(result).toISOString().slice(0, 10) !== result)) throw problem('VALIDATION', `请填写有效的${label}。`, key)
  return result
}
function ids(value: unknown): string[] | undefined {
  if (value === undefined) return
  if (!Array.isArray(value) || value.length > 1000 || value.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(value).size !== value.length) throw new AppError('VALIDATION', '所选记录有误。')
  return value
}
export function seedReferenceMaterials(state: RegistrationState, now = new Date()) {
  if (state.referenceMaterials) return
  const timestamp = now.toISOString(), today = timestamp.slice(0, 10)
  state.referenceMaterials = ['铅标准溶液', '镉标准溶液', '汞标准溶液', '砷标准溶液', '电导率标准溶液', 'pH 标准缓冲液', '分部标准溶液'].map((name, index) => ({ ...emptyMaterial(), id: `reference-material-${index + 1}`, name, specification: '50 mL/瓶', supplier: '示例标准物质供应商', manufacturer: '示例标准物质研究所', purchasedAt: today, purchasedQuantity: 10, purchaseStatus: '已购置', validity: `${now.getUTCFullYear() + 1}-12-31`, version: 1, departmentId: index === 6 ? 'lab2' : 'lab', accepted: index === 1 || index === 2, acceptanceStatus: index === 1 || index === 2 ? '已验收' : '未验收', createdAt: timestamp, updatedAt: timestamp, updatedBy: '演示用户' }))
  state.materialAcceptances = state.referenceMaterials.slice(1, 3).map((row, index) => ({ ...emptyAcceptance(), id: `material-acceptance-${index + 1}`, materialId: row.id, materialVersion: row.version, version: 1, name: row.name, specification: row.specification, supplier: row.supplier, manufacturer: row.manufacturer, departmentId: row.departmentId, useDepartmentId: 'lab', useDepartment: '实验室', location: '标准物质柜', status: index ? '不合格' : '合格', acceptedAt: today, acceptorId: 'quality', acceptor: '刘质量', keeperId: 'inventory', keeper: '吴物资', createdAt: timestamp, updatedAt: timestamp, updatedBy: '演示用户' }))
}
export function createReferenceMaterials(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || (write ? !canWriteMaterials(user) : !user.roles.some(role => ['admin', 'quality', 'inventory', 'reviewer', 'approver'].includes(role)))) throw new AppError('FORBIDDEN', '无权执行标准物质操作。')
    return user
  }
  const visible = (row: { departmentId: string }) => deps.actor().scope === 'all' || row.departmentId === deps.actor().departmentId
  function material(id: unknown): MaterialRecord {
    actor(); const row = read().referenceMaterials?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '登记记录不存在或无权访问，请刷新列表。')
    const accepted = !!read().materialAcceptances?.some(item => item.materialId === row.id)
    return { ...row, accepted, acceptanceStatus: accepted ? '已验收' : '未验收' }
  }
  function acceptance(id: unknown): AcceptanceRecord {
    actor(); const row = read().materialAcceptances?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '验收记录不存在或无权访问，请刷新列表。')
    const parent = material(row.materialId)
    return { ...row, materialVersion: parent.version }
  }
  function users(): EntryPersonCandidate[] {
    actor()
    return demoActors.filter(user => user.active !== false && visible(user)).map(user => ({ ...user, departmentName: registrationDepartments.find(dept => dept.id === user.departmentId)?.name || '', certificateNumber: user.certificateNumber || '', phone: user.phone || '' }))
  }
  function person(id: unknown, key = 'acceptorId') {
    const user = users().find(user => user.id === id)
    if (!user) throw problem('VALIDATION', '请选择权限范围内的有效人员。', key)
    return user
  }
  function queryUsers(input: Record<string, unknown>): EntryPeoplePage {
    const user = actor(), fields = ['account', 'name', 'certificateNumber'] as const
    const filters = Object.fromEntries(fields.map(key => [key, text(input[key] ?? '', key, '查询条件').toLowerCase()]))
    const result = paginate(users().filter(row => fields.every(key => String(key === 'account' ? row.id : row[key]).toLowerCase().includes(filters[key]!))), input)
    return { ...result, scope: 'all', presetConfigured: false, departmentName: registrationDepartments.find(dept => dept.id === user.departmentId)?.name || '' }
  }
  function paginate<Row>(rows: Row[], input: Record<string, unknown>, all = false) {
    const requested = input.page ?? 1, size = input.pageSize ?? 10
    if (!Number.isSafeInteger(requested) || Number(requested) < 1 || typeof size !== 'number' || ![5, 10, 20, 50].includes(size)) throw new AppError('VALIDATION', '分页参数有误。')
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(rows.length / size)))
    return { items: all ? rows : rows.slice((page - 1) * size, page * size), total: rows.length, page, pageSize: size }
  }
  function query(kind: MaterialKind, input: Record<string, unknown>, all = false) {
    actor()
    const name = text(input.name ?? '', 'name', '名称').toLowerCase(), manufacturer = text(input.manufacturer ?? '', 'manufacturer', '生产厂家').toLowerCase(), department = text(input.useDepartment ?? '', 'useDepartment', '使用部门').toLowerCase()
    const selected = ids(input.ids), parents = ids(input.materialIds); parents?.forEach(id => material(id))
    const rows = kind === 'materials' ? (read().referenceMaterials || []).filter(visible).map(row => material(row.id)) : (read().materialAcceptances || []).filter(row => visible(row) && (read().referenceMaterials || []).some(parent => parent.id === row.materialId && visible(parent)) && (!parents || parents.includes(row.materialId))).map(row => acceptance(row.id))
    const filtered = rows.filter(row => (!selected || selected.includes(row.id)) && row.name.toLowerCase().includes(name) && (kind === 'materials' ? row.manufacturer.toLowerCase().includes(manufacturer) : (row as AcceptanceRecord).useDepartment.toLowerCase().includes(department)))
      .sort((a, b) => kind === 'materials' ? b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id) : (b as AcceptanceRecord).acceptedAt.localeCompare((a as AcceptanceRecord).acceptedAt) || b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id))
    return paginate(filtered, { ...input, pageSize: input.pageSize ?? (kind === 'materials' ? 5 : 10) }, all)
  }
  
  function save(kind: MaterialKind, input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : kind === 'materials' ? material(input.id) : acceptance(input.id)
    
    const state = structuredClone(read()), now = new Date().toISOString(), meta = { id: previous?.id || randomUUID(), version: (previous?.version || 0) + 1, createdAt: previous?.createdAt || now, updatedAt: now, updatedBy: user.name }
    if (kind === 'materials') {
      const draft = emptyMaterial()
      for (const field of materialTextFields) draft[field.key] = text(input[field.key] ?? '', field.key, field.label)
      if (!draft.name) throw problem('VALIDATION', '请填写品名。', 'name')
      for (const [key, label] of [['purchasedAt', '购置日期'], ['receivedAt', '领用日期']] as const) draft[key] = date(input[key], key, label)
      for (const [key, label] of [['purchasedQuantity', '购置数量'], ['receivedQuantity', '领用数量']] as const) {
        const value = input[key]
        if (value !== null && value !== undefined && value !== '' && (typeof value !== 'number' || !Number.isFinite(value) || value < 0)) throw problem('VALIDATION', `${label}须为不小于零的数字。`, key)
        draft[key] = value === null || value === undefined || value === '' ? null : value as number
      }
      if (draft.purchasedQuantity !== null && draft.receivedQuantity !== null && draft.receivedQuantity > draft.purchasedQuantity) throw problem('VALIDATION', '领用数量不能大于购置数量。', 'receivedQuantity')
      if (draft.purchasedAt && draft.receivedAt && draft.receivedAt < draft.purchasedAt) throw problem('VALIDATION', '领用日期不能早于购置日期。', 'receivedAt')
      draft.notes = text(input.notes ?? '', 'notes', '备注', 2000)
      const accepted = !!state.materialAcceptances?.some(row => row.materialId === previous?.id)
      const saved: MaterialRecord = { ...meta, ...draft, departmentId: previous?.departmentId || user.departmentId, accepted, acceptanceStatus: accepted ? '已验收' : '未验收' }
      const rows = state.referenceMaterials ||= []; if (previous) rows[rows.findIndex(row => row.id === saved.id)] = saved; else rows.push(saved)
      deps.write!(state); return saved
    }
    if (previous && (previous as AcceptanceRecord).materialId !== input.materialId) throw problem('VALIDATION', '验收记录不能更换关联登记。', 'materialId')
    const parent = material(input.materialId)
    if (!previous && parent.accepted) throw new AppError('BUSINESS_RULE', `“${parent.name}”已验收，请刷新登记列表。`)
    
    const draft = emptyAcceptance()
    for (const field of acceptanceTextFields) draft[field.key] = text(input[field.key] ?? '', field.key, field.label)
    draft.materialId = parent.id; draft.materialVersion = parent.version + 1
    const dept = registrationDepartments.find(dept => dept.id === input.useDepartmentId)
    if (!dept || user.scope !== 'all' && dept.id !== user.departmentId) throw problem('VALIDATION', '请选择可访问的使用部门。', 'useDepartmentId')
    draft.useDepartmentId = dept.id
    if (!acceptanceStatuses.includes(input.status as never)) throw problem('VALIDATION', '请选择验收状态。', 'status')
    draft.status = input.status as string; draft.acceptedAt = date(input.acceptedAt, 'acceptedAt', '验收日期', true)
    const acceptor = person(input.acceptorId), keeper = input.keeperId ? person(input.keeperId, 'keeperId') : undefined
    draft.acceptorId = acceptor.id; draft.keeperId = keeper?.id || ''; draft.notes = text(input.notes ?? '', 'notes', '备注', 2000)
    const saved: AcceptanceRecord = { ...meta, ...draft, departmentId: parent.departmentId, name: parent.name, specification: parent.specification, useDepartment: dept.name, acceptor: acceptor.name, keeper: keeper?.name || '' }
    const rows = state.materialAcceptances ||= []; if (previous) rows[rows.findIndex(row => row.id === saved.id)] = saved; else rows.push(saved)
    const stored = state.referenceMaterials!.find(row => row.id === parent.id)!; Object.assign(stored, { accepted: true, acceptanceStatus: '已验收', version: parent.version + 1, updatedAt: now, updatedBy: user.name })
    deps.write!(state); return saved
  }
  function remove(kind: MaterialKind, input: Record<string, unknown>) {
    const user = actor(true), row = kind === 'materials' ? material(input.id) : acceptance(input.id); 
    const state = structuredClone(read())
    if (kind === 'materials') {
      if ((row as MaterialRecord).accepted) throw new AppError('VALIDATION', '该登记存在验收记录，请先删除关联验收记录。')
      state.referenceMaterials = state.referenceMaterials!.filter(item => item.id !== row.id)
    } else {
      const parent = material((row as AcceptanceRecord).materialId); 
      state.materialAcceptances = state.materialAcceptances!.filter(item => item.id !== row.id)
      Object.assign(state.referenceMaterials!.find(item => item.id === parent.id)!, { version: parent.version + 1, accepted: false, acceptanceStatus: '未验收', updatedAt: new Date().toISOString(), updatedBy: user.name })
    }
    deps.write!(state); return { id: row.id }
  }
  return { query, save, remove, person, queryUsers, detail: (kind: MaterialKind, id: unknown) => kind === 'materials' ? material(id) : acceptance(id), export: (kind: MaterialKind, input: Record<string, unknown>) => {
    const columns = kind === 'materials' ? materialColumns : acceptanceColumns
    return registrationCsv([columns.map(column => column.label), ...query(kind, input, true).items.map(row => columns.map(column => String(row[column.key as keyof typeof row] ?? '')))])
  } }
}
