import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import { equipmentStates, equipmentDateFields } from '../src/types/quality/equipmentLedger'
import { emptyEquipment, equipmentAttachmentKinds, equipmentHistoryFields, equipmentRecordFields, equipmentBatchFields, type EquipmentBatchChanges, type EquipmentBatchKey, type EquipmentHistoryKind, type EquipmentRecord, type EquipmentProfile, type EquipmentProject } from '../src/types/quality/equipmentForm'
import { testPlans, testPlanGroups, publicTestPlan } from './samplePlans'
import { resolvePlanSelection } from './testPlanSelection'
import type { TestPlanQuery } from '../src/types/commissions/sampleForm'
import { equipmentImportFields } from '../src/types/quality/equipmentImport'
import { parsePersonnelCsv as parseCsv } from './personnel'
import { registrationCsv } from './registrationDomain'

const invalid = (message: string, key?: string): never => { throw new AppError('VALIDATION', message, { fieldErrors: key ? { [key]: message } : undefined }) }
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : invalid('设备资料格式有误。')
function text(value: unknown, label: string, required = false, key?: string) {
  if (value === undefined) return required ? invalid(`请填写${label}。`, key) : ''
  if (typeof value !== 'string' || value.length > 1000 || required && !value.trim()) return invalid(`请正确填写${label}。`, key)
  return value.trim()
}
function date(value: unknown, label: string, key?: string) {
  const result = text(value, label, false, key)
  if (result && (!/^\d{4}-\d{2}-\d{2}$/.test(result) || !Number.isFinite(Date.parse(result)) || new Date(result).toISOString().slice(0, 10) !== result)) return invalid(`${label}须为有效日期。`, key)
  return result
}
export function createEquipmentForms(deps: RegistrationDependencies) {
  function actor(write = false) {
    const a = deps.actor()
    if (deps.locked?.() || !a.roles.some(r => (write ? ['admin', 'quality'] : ['admin', 'quality', 'reviewer', 'approver']).includes(r))) throw new AppError('FORBIDDEN', '无权访问此设备操作。')
    return a
  }
  function options() {
    const a = actor()
    return { departments: registrationDepartments.filter(d => a.scope === 'all' || d.id === a.departmentId), equipmentTypes: (deps.read!()!.equipmentTypes || []).map(type => type.name), projects: testPlans.filter(p => a.scope === 'all' || p.departmentId === a.departmentId).map(({ id, code, name, parentId }) => ({ id, code, name, parentId })) }
  }
  function plans(query: TestPlanQuery = {}) {
    const a = actor(), allowed = (row: { departmentId: string }) => a.scope === 'all' || row.departmentId === a.departmentId
    const keyword = text(query.keyword, '方案名称或代码').toLocaleLowerCase(), parentId = text(query.parentId, '方案分组')
    const groups = testPlanGroups.filter(allowed), available = testPlans.filter(allowed)
    if (parentId && !groups.some(group => group.id === parentId)) return invalid('检测方案分组不存在或已不可访问。')
    const rows = keyword ? available.filter(p => `${p.name} ${p.code}`.toLocaleLowerCase().includes(keyword)) : parentId ? available.filter(p => p.parentId === parentId) : groups
    const pageSize = 10, page = Math.min(Math.max(1, Math.floor(Number(query.page) || 1)), Math.max(1, Math.ceil(rows.length / pageSize)))
    return { items: rows.slice((page - 1) * pageSize, page * pageSize).map(publicTestPlan), total: rows.length, page, pageSize }
  }
  function planSelection(selection: unknown, toggle?: unknown) {
    const result = resolvePlanSelection(actor(), selection, toggle)
    return { ...result.state, catalogue: result.catalogue }
  }
  function detail(id: string): EquipmentRecord {
    const a = actor(), state = deps.read!()!, row = state.equipmentLedger?.find(r => r.id === id)
    if (!row || a.scope !== 'all' && row.departmentId !== a.departmentId) throw new AppError('NOT_FOUND', '设备不存在或无权访问。')
    return structuredClone({ ...row, version: row.version || 1, profile: state.equipmentProfiles?.[id] || emptyEquipment().profile })
  }
  function parse(input: unknown, previous?: EquipmentRecord) {
    const a = actor(true), raw = object(input), draft = emptyEquipment()
    for (const key of ['code', 'name', 'model', 'serial', 'manufacturer', 'testOrganization', 'location', 'cycle', 'notes', 'range', 'accuracy', 'keeper', 'departmentId'] as const) draft[key] = text(raw[key], key === 'code' ? '档案号' : key === 'name' ? '仪器设备名称' : '设备信息', key === 'code' || key === 'name', key)
    for (const field of equipmentDateFields) draft[field.key] = date(raw[field.key], field.label, field.key)
    if (!equipmentStates.includes(raw.status as typeof equipmentStates[number])) return invalid('请选择有效的设备状态。', 'status')
    draft.status = raw.status as typeof draft.status
    if (raw.price !== null && raw.price !== undefined && (typeof raw.price !== 'number' || !Number.isFinite(raw.price) || raw.price < 0 || raw.price > 1e12)) return invalid('购入价格须为有效的非负金额。', 'price')
    draft.price = raw.price == null ? null : raw.price as number
    const department = registrationDepartments.find(d => d.id === draft.departmentId)
    if (draft.departmentId && !department || a.scope !== 'all' && draft.departmentId !== a.departmentId) return invalid('请选择可访问的所属部门。', 'departmentId')
    draft.department = department?.name || ''
    const p = object(raw.profile), profile = draft.profile
    for (const key of ['equipmentType', 'tester', 'validity'] as const) profile[key] = text(p[key], '设备信息', false, key)
    if (!Array.isArray(p.projects) || p.projects.length > 200) return invalid('请选择有效的检测方案。')
    const projects = options().projects
    profile.projects = [...new Set(p.projects.map(row => text(object(row).id, '方案编号', true)))].map(id => projects.find(row => row.id === id) || invalid('所选检测方案不存在或已不可访问，请重新选择。'))
    for (const kind of Object.keys(equipmentHistoryFields) as EquipmentHistoryKind[]) {
      if (!Array.isArray(p[kind]) || p[kind].length > 200) return invalid('每类设备记录最多 200 条。')
      const retained = new Set<string>()
      profile[kind] = p[kind].map(raw => {
        const row = object(raw), existing = previous?.profile[kind].find(item => item.id === row.id && !retained.has(item.id))
        const result: Record<string, string> & { id: string } = { ...(kind === 'calibrations' && existing ? existing : {}), id: existing?.id || randomUUID() }
        retained.add(result.id)
        for (const f of equipmentRecordFields(kind)) result[f.key] = f.date ? date(row[f.key], f.label) : text(row[f.key], f.label)
        if (!equipmentRecordFields(kind).some(f => result[f.key])) return invalid('设备记录不能全部为空。')
        return result
      })
    }
    const attachments = object(p.attachments); let size = 0, count = 0
    for (const { key } of equipmentAttachmentKinds) {
      const values = attachments[key]
      if (!Array.isArray(values)) return invalid('附件格式有误。')
      profile.attachments[key] = values.map(value => {
        const file = object(value), name = text(file.name, '附件名称', true), type = text(file.type, '附件类型'), dataUrl = file.dataUrl
        const encoded = typeof dataUrl === 'string' && dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
        if (name.length > 255 || typeof file.size !== 'number' || !Number.isSafeInteger(file.size) || file.size <= 0 || encoded === false || encoded === undefined || encoded.length % 4 || Buffer.from(encoded, 'base64').length !== file.size) return invalid('附件内容或大小不正确。')
        size += file.size; count++
        if (size > 20 * 1024 * 1024 || count > 100) return invalid('设备附件总计不能超过 20 MB、100 个。')
        return { id: previous?.profile.attachments[key].find(item => item.id === file.id)?.id || randomUUID(), name, type, size: file.size, dataUrl: dataUrl as string }
      })
    }
    return draft
  }
  function save(input: unknown, recordId?: string): EquipmentRecord {
    actor(true)
    const raw = object(input), previous = recordId ? detail(recordId) : undefined
    
    const draft = parse(raw, previous), profile = draft.profile, state = structuredClone(deps.read!()!)
    if (state.equipmentLedger?.some(row => row.id !== recordId && row.code.toLocaleLowerCase() === draft.code.toLocaleLowerCase())) return invalid('档案号已存在，请使用其他档案号。', 'code')
    const id = recordId || randomUUID(), version = previous ? previous.version + 1 : 1, { profile: savedProfile, ...row } = draft
    Object.assign(row, { usageRecordCount: profile.attachments.usage.length, manualCount: profile.attachments.manual.length, certificateCount: profile.attachments.certificate.length, acceptanceCount: profile.attachments.acceptance.length })
    if (recordId) state.equipmentLedger![state.equipmentLedger!.findIndex(item => item.id === recordId)] = { ...row, id, version }
    else (state.equipmentLedger ||= []).push({ ...row, id, version })
    ;(state.equipmentProfiles ||= {})[id] = savedProfile
    deps.write!(state)
    return detail(id)
  }
  function remove(id: string, input: unknown) {
    actor(true)
    const row = detail(id), raw = object(input)
    
    const state = structuredClone(deps.read!()!)
    if (state.equipmentLoans?.some(record => record.equipmentId === id)) throw new AppError('BUSINESS_RULE', '该设备存在领用历史，不能直接删除。')
    if (state.equipmentInterimPlans?.some(plan => plan.equipmentId === id)) throw new AppError('BUSINESS_RULE', '该设备已被期间核查计划引用，请先处理相关计划。')
    if (Object.values(state.dataEntries || {}).some(entry => entry.form.equipmentIds.includes(id))
      || Object.values(state.equipmentPlans || {}).some(plan => plan.associatedIds.includes(id) || plan.defaultIds.includes(id))) {
      throw new AppError('BUSINESS_RULE', '该设备已被检测数据或检测方案引用，暂不能删除。')
    }
    state.equipmentLedger = state.equipmentLedger!.filter(item => item.id !== id)
    if (state.equipmentProfiles) delete state.equipmentProfiles[id]
    if (state.equipmentGroupLinks) delete state.equipmentGroupLinks[id]
    if (state.equipmentOverallPlans) delete state.equipmentOverallPlans[id]
    if (state.equipmentCalibrationPlans) delete state.equipmentCalibrationPlans[id]
    deps.write!(state)
    return { id }
  }
  function batchUpdate(input: unknown) {
    const a = actor(true), raw = object(input), changes = object(raw.changes)
    if (!Array.isArray(raw.records) || !raw.records.length || raw.records.length > 200) return invalid('请选择 1 至 200 条设备记录。')
    const keys = Object.keys(changes)
    if (!keys.length || keys.some(key => !equipmentBatchFields.some(field => field.key === key))) return invalid('请勾选有效的修改字段。')
    const patch: EquipmentBatchChanges = {}
    for (const key of keys as EquipmentBatchKey[]) {
      const field = equipmentBatchFields.find(field => field.key === key)!
      if (key === 'price') {
        const price = changes.price
        if (price !== null && (typeof price !== 'number' || !Number.isFinite(price) || price < 0 || price > 1e12)) return invalid('购入价格须为有效的非负金额。', 'price')
        patch.price = price as number | null
      } else {
        const value = field.kind === 'date' ? date(changes[key], field.label, key) : text(changes[key], field.label, false, key)
        if (key === 'status' && !equipmentStates.includes(value as typeof equipmentStates[number])) return invalid('请选择有效的设备状态。', 'status')
        if (key === 'departmentId' && (value && !registrationDepartments.some(d => d.id === value) || a.scope !== 'all' && value !== a.departmentId)) return invalid('请选择可访问的所属部门。', 'departmentId')
        Object.assign(patch, { [key]: value })
      }
    }
    const ids = new Set<string>()
    const targets = raw.records.map(value => {
      const target = object(value), id = text(target.id, '设备编号', true)
      if (ids.has(id)) return invalid('所选设备不能重复。')
      ids.add(id)
      const row = detail(id)
      
      return row
    })
    // Validate every target first, then write the partial update atomically.
    const state = structuredClone(deps.read!()!)
    for (const target of targets) {
      const row = state.equipmentLedger!.find(row => row.id === target.id)!
      const { equipmentType, ...basic } = patch
      Object.assign(row, basic, { version: target.version + 1 })
      if ('departmentId' in patch) row.department = registrationDepartments.find(d => d.id === patch.departmentId)?.name || ''
      if (equipmentType !== undefined) {
        const profiles = state.equipmentProfiles ||= {}
        const profile = profiles[target.id] ||= emptyEquipment().profile
        profile.equipmentType = equipmentType
      }
    }
    deps.write!(state)
    return { count: targets.length }
  }
  function importCsv(value: unknown) {
    actor(true)
    const [header, ...lines] = parseCsv(value)
    if (!header || header.length !== equipmentImportFields.length || header.some((cell, i) => cell.trim() !== equipmentImportFields[i]!.label)) return invalid('模板列不匹配，请使用下载的导入模板。')
    if (!lines.length || lines.length > 1000) return invalid('每次请导入 1 至 1000 条设备记录。')
    const state = structuredClone(deps.read!()!), codes = new Set((state.equipmentLedger || []).map(row => row.code.toLocaleLowerCase()))
    const records = lines.map((values, index) => {
      try {
        if (values.length !== header.length) return invalid('列数与模板不一致。')
        const cells = Object.fromEntries(equipmentImportFields.map((field, i) => [field.key, values[i]!.trim()]))
        const draft = emptyEquipment()
        for (const field of equipmentImportFields) {
          const value = cells[field.key]!
          if (field.key === 'department') {
            const department = registrationDepartments.find(item => item.name === value)
            if (value && value !== '无' && !department) return invalid('所属部门不存在，请填写部门名称或“无”。')
            draft.departmentId = department?.id || ''
          } else if (field.key === 'price') {
            if (value && !/^\d+(\.\d+)?$/.test(value)) return invalid('购入价格须为有效的非负金额。', 'price')
            draft.price = value ? Number(value) : null
          } else if (field.key === 'equipmentType' || field.key === 'tester' || field.key === 'validity') draft.profile[field.key] = value
          else if (field.key === 'status') draft.status = (value || '可用') as typeof draft.status
          else draft[field.key] = value
        }
        const parsed = parse(draft), code = parsed.code.toLocaleLowerCase()
        if (codes.has(code)) return invalid('档案号重复，请检查文件及已有设备。')
        codes.add(code)
        return { ...parsed, id: randomUUID(), version: 1 }
      } catch (error) { if (error instanceof AppError) throw new AppError(error.code, `第 ${index + 2} 行：${error.message}`); throw error }
    })
    // Commit only after every row has passed the same validation as the equipment form.
    for (const { profile, ...row } of records) {
      (state.equipmentLedger ||= []).push(row)
      ;(state.equipmentProfiles ||= {})[row.id] = profile
    }
    deps.write!(state)
    return { count: records.length }
  }
  return { options, detail, save, remove, batchUpdate, plans, planSelection, importCsv,
    template: () => { actor(); return registrationCsv([equipmentImportFields.map(field => field.label)]) },
  }
}
