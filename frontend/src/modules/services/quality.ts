// 质量体系：检测标准基础信息库 + 设备台账（真实数据，后端分页/筛选）
import { authedFetch, request } from './http'
import { USE_BACKEND } from './auth'
import {
  demoControlledStandards,
  demoEquipment,
  demoPersonnel,
  demoStandardMasters,
} from '@/data/moduleDemo'

export interface StdItem {
  identityImpactCount?: number
  id: number
  controlledNo: string
  code: string
  name: string
  parameters?: string
  authKind: string
  outOfScope: boolean
  category: string
  location: string
  issueCount: string
  issuer: string
  useDepts: string[]
  implDate: string
  voidDate: string
  delayDays: string
  replaceNo: string
  isEnglish: boolean
  isOnsiteStandard?: boolean
  remark: string
  status: string
}

export interface EquipItem {
  editVersion?: number
  id: number
  archiveNo: string
  name: string
  spec: string
  dept: string
  status: string
  calibrationMode?: 'correction' | 'renewal'
  eligibility?: {level: string; code: string; message: string; selectable: boolean; evidence?: Record<string, unknown>}
  manualStatus?: string
  keeper: string
  lastCalDate: string
  planCalDate: string
  // 详情（full=true）
  factoryNo?: string
  maker?: string
  calUnit?: string
  place?: string
  period?: string
  actualCalDate?: string
  range?: string
  accuracy?: string
  buyDate?: string
  buyPrice?: string
  useRecord?: string
  manual?: string
  cert?: string
  certificateNo?: string
  acceptDoc?: string
  equipType?: string
  calPerson?: string
  validUntil?: string
  remark?: string
}

export interface Paged<T> {
  rows: T[]
  total: number
  page: number
  size: number
}

function qs(params: Record<string, string | number | boolean | undefined>) {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') q.set(k, String(v))
  })
  return q.toString()
}

export function fetchStdLibrary(p: { keyword?: string; dept?: string; authKind?: string; page?: number; size?: number; scope?: 'department' }) {
  if (!USE_BACKEND) {
    const keyword = (p.keyword || '').trim().toLowerCase()
    const rows = demoControlledStandards.filter((item) => {
      const text = `${item.controlledNo} ${item.code} ${item.name}`.toLowerCase()
      return (!keyword || text.includes(keyword))
        && (!p.dept || item.useDepts.includes(p.dept))
        && (!p.authKind || item.authKind === p.authKind)
    })
    return Promise.resolve(paginateDemo(rows, p.page, p.size) as Paged<StdItem>)
  }
  return request<Paged<StdItem>>(`/api/quality/std-library?${qs({ ...p })}`)
}
export async function fetchStdDetail(id: number) {
  if (!USE_BACKEND) return Promise.resolve(demoControlledStandards.find((item) => item.id === id) as StdItem)
  return request<StdItem>(`/api/quality/std-library/${id}`)
}
export function updateStd(id: number, payload: Partial<StdItem>) {
  return request<StdItem>(`/api/quality/std-library/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}
export function createStd(payload: Partial<StdItem>) {
  return request<StdItem>('/api/quality/std-library', { method: 'POST', body: JSON.stringify(payload) })
}
export function removeStd(id: number) {
  return request<void>(`/api/quality/std-library/${id}`, { method: 'DELETE' })
}
export function voidStd(id: number, payload: { voidDate: string; replaceNo?: string; reason: string }) {
  return request<StdItem>(`/api/quality/std-library/${id}/void`, { method: 'POST', body: JSON.stringify(payload) })
}
export function updateStdDepartments(id: number, departments: string[]) {
  return request<StdItem>(`/api/quality/std-library/${id}/departments`, {
    method: 'PUT',
    body: JSON.stringify({ departments }),
  })
}
export function importStdLibrary(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{ created: number; updated: number }>('/api/quality/std-library/import', {
    method: 'POST',
    body,
  })
}
export function downloadStdLibraryTemplate() {
  return downloadQualityFile('/api/quality/std-library/template', 'standard-library-import-template.xlsx')
}
export function exportStdLibrary(params: { keyword?: string; dept?: string; authKind?: string }) {
  return downloadQualityFile(
    `/api/quality/std-library/export?${qs(params)}`,
    'standard-library.xlsx',
  )
}

export interface StandardMasterItem {
  id: number
  code: string
  name: string
  parameters?: string
  category: string
  authKind: string
  department: string
  status: string
  expired: boolean
}

export function fetchStandards(p: { keyword?: string; category?: string; page?: number; size?: number }) {
  if (!USE_BACKEND) {
    const keyword = (p.keyword || '').trim().toLowerCase()
    const rows = demoStandardMasters.filter((item) => {
      const text = `${item.code} ${item.name} ${item.department}`.toLowerCase()
      return (!keyword || text.includes(keyword)) && (!p.category || item.category === p.category)
    })
    return Promise.resolve(paginateDemo(rows, p.page, p.size) as Paged<StandardMasterItem>)
  }
  return request<Paged<StandardMasterItem>>(`/api/quality/standards?${qs({ ...p })}`).then((data) => {
    const page = p.page ?? 1
    const size = p.size ?? 20
    if (data.page && data.size) return data
    const rows = data.rows ?? []
    const total = data.total ?? rows.length
    const serverReturnedFullSet = rows.length === total || rows.length > size
    return {
      rows: serverReturnedFullSet ? rows.slice((page - 1) * size, page * size) : rows,
      total,
      page,
      size,
    }
  })
}
export function createStandard(payload: Partial<StandardMasterItem>) {
  return request<StandardMasterItem>('/api/quality/standards', { method: 'POST', body: JSON.stringify(payload) })
}
export function updateStandard(id: number, payload: Partial<StandardMasterItem>) {
  return request<StandardMasterItem>(`/api/quality/standards/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}
export function removeStandard(id: number) {
  return request<void>(`/api/quality/standards/${id}`, { method: 'DELETE' })
}

export function fetchReportEquipment(reportNo: string, intervals: {start:string;end:string}[] = []) {
  return request<{ rows: EquipItem[]; total: number }>(`/api/reports/${encodeURIComponent(reportNo)}/equipment-options?${qs({intervals: JSON.stringify(intervals)})}`)
}

export function fetchEquipment(p: { keyword?: string; dept?: string; status?: string; page?: number; size?: number; full?: boolean; scope?: 'department' }) {
  if (!USE_BACKEND) {
    const keyword = (p.keyword || '').trim().toLowerCase()
    const rows = demoEquipment.filter((item) => {
      const text = `${item.archiveNo} ${item.name} ${item.keeper} ${item.spec}`.toLowerCase()
      return (!keyword || text.includes(keyword))
        && (!p.dept || item.dept === p.dept)
        && (!p.status || item.status === p.status)
    })
    return Promise.resolve(paginateDemo(rows, p.page, p.size) as Paged<EquipItem>)
  }
  return request<Paged<EquipItem>>(`/api/quality/equipment?${qs({ ...p })}`)
}
export async function fetchEquipmentDetail(id: number, scope?: 'department') {
  if (!USE_BACKEND) return Promise.resolve(demoEquipment.find((item) => item.id === id) as EquipItem)
  return request<EquipItem>(`/api/quality/equipment/${id}${scope ? `?${qs({ scope })}` : ''}`)
}
export function updateEquipment(id: number, payload: Partial<EquipItem>) {
  return request<EquipItem>(`/api/quality/equipment/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}
export function createEquipment(payload: Partial<EquipItem>) {
  return request<EquipItem>('/api/quality/equipment', { method: 'POST', body: JSON.stringify(payload) })
}
export function removeEquipment(id: number) {
  return request<void>(`/api/quality/equipment/${id}`, { method: 'DELETE' })
}
export function backfillEquipmentCalibration(id: number, payload: { start: string; end: string; certificateNo: string; calUnit: string; reason: string; confirmed: boolean }) {
  return request<{ validPeriods: NonNullable<EquipmentHistory['validPeriods']> }>(`/api/quality/equipment/${id}/calibration-history`, { method: 'POST', body: JSON.stringify(payload) })
}
export function batchUpdateEquipment(ids: number[], changes: Partial<EquipItem>, calibrationMode: 'correction' | 'renewal' = 'correction') {
  return request<{ updated: number }>('/api/quality/equipment/batch-update', {
    method: 'POST',
    body: JSON.stringify({ ids, changes, calibrationMode }),
  })
}
export function batchDeleteEquipment(ids: number[]) {
  return request<{ deleted: number }>('/api/quality/equipment/batch-delete', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  })
}
export function importEquipment(file: File, dryRun = false) {
  const body = new FormData()
  body.append('file', file)
  body.append('dryRun', String(dryRun))
  return request<{ created: number; updated: number; createdCount: number; updatedCount: number; unchangedCount: number; changes: {id: number | null; archiveNo: string; name: string; fields: Record<string, {before: string; after: string}>; clearingFields: string[]}[] }>('/api/quality/equipment/import', {
    method: 'POST',
    body,
  })
}
async function downloadQualityFile(path: string, fallbackName: string) {
  const response = await authedFetch(path)
  if (!response.ok) throw new Error('文件下载失败')
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  const name = match?.[1] || fallbackName
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}
export function downloadEquipmentTemplate() {
  return downloadQualityFile('/api/quality/equipment/template', 'equipment-import-template.xlsx')
}
export function exportEquipment(params: { keyword?: string; dept?: string; status?: string; ids?: string }) {
  return downloadQualityFile(
    `/api/quality/equipment/export?${qs(params)}`,
    'equipment-ledger.xlsx',
  )
}
export interface EquipmentUsageRecord {
  id: number
  reportNo: string
  sampleNo: string
  project: string
  usedFrom: string
  usedTo: string
  usedByAccount: string
  usedByName: string
  statusAtUse: string
  createdAt: string
}
export interface EquipmentCalibrationRecord {
  id: number
  source: string
  changedFields: string[]
  before: Record<string, string>
  after: Record<string, string>
  changedByAccount: string
  changedByName: string
  changedAt: string
}
export interface EquipmentHistory {
  validPeriods?: { start: string; end: string; certificateNo: string; calUnit: string }[]
  usage: EquipmentUsageRecord[]
  calibration: EquipmentCalibrationRecord[]
  reports: EquipmentUsageRecord[]
  projects: string[]
}
export function fetchEquipmentHistory(id: number, scope?: 'department') {
  if (!USE_BACKEND) {
    const equipment = demoEquipment.find((item) => item.id === id)
    return Promise.resolve({
      usage: equipment ? [{ id: id * 10, reportNo: 'DEMO-R-1001', sampleNo: 'DEMO-S-1001', project: equipment.name, usedFrom: '2026-08-18 09:10', usedTo: '2026-08-18 11:30', usedByAccount: 'demo_tester_a', usedByName: '演示人员甲', statusAtUse: equipment.status, createdAt: '2026-08-18 09:10' }] : [],
      calibration: [],
      reports: [],
      projects: equipment ? [equipment.name] : [],
    } as EquipmentHistory)
  }
  return request<EquipmentHistory>(`/api/quality/equipment/${id}/history${scope ? `?${qs({ scope })}` : ''}`)
}

export function fetchQualityDepts() {
  if (!USE_BACKEND) return Promise.resolve(['演示检测一部', '演示检测二部', '演示检测三部', '演示质量部', '演示样品室'])
  return request<{ departments: string[] }>(`/api/quality/dept-options`).then((d) => d.departments)
}

export interface InstrumentItem {
  code: string
  name: string
  parameters?: string
  department: string
  site: string
  controlled: boolean
}

export function fetchInstruments() {
  return request<{ rows: InstrumentItem[]; total: number }>('/api/quality/instruments')
}

// 人员登记
export interface PersonItem {
  id: number
  mobile?: string
  name: string
  code: string
  dept: string
  title: string
  position: string
  approvalPosition?: '' | 'department_director' | 'institute_leader'
  assignedDepts: string[]
  permissions: string[]
  linkedUserId?: number | null
  accountEnabled?: boolean
  accountStatus?: string
  roleName?: string
  departmentId?: number | null
  // 详情
  gender?: string
  education?: string
  major?: string
  gradTime?: string
  testScope?: string
  checkScope?: string
  remark?: string
  birthDate?: string
  idNo?: string
  ethnicity?: string
  nativePlace?: string
  political?: string
  school?: string
  workStartTime?: string
  joinTime?: string
}
export function fetchPersonnel(p: { keyword?: string; dept?: string; page?: number; size?: number }) {
  if (!USE_BACKEND) {
    const keyword = (p.keyword || '').trim().toLowerCase()
    const rows = demoPersonnel.filter((item) => {
      const text = `${item.name} ${item.code} ${item.dept} ${item.position}`.toLowerCase()
      return (!keyword || text.includes(keyword)) && (!p.dept || item.dept === p.dept)
    })
    return Promise.resolve(paginateDemo(rows, p.page, p.size) as Paged<PersonItem>)
  }
  return request<Paged<PersonItem>>(`/api/quality/personnel?${qs({ ...p })}`)
}
export async function fetchPersonnelDetail(id: number) {
  if (!USE_BACKEND) return Promise.resolve(demoPersonnel.find((item) => item.id === id) as PersonItem)
  return request<PersonItem>(`/api/quality/personnel/${id}`)
}
export function updatePersonnel(id: number, payload: Partial<PersonItem>) {
  return request<PersonItem>(`/api/quality/personnel/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}
export function createPersonnel(payload: Partial<PersonItem>) {
  return request<PersonItem>(`/api/quality/personnel`, { method: 'POST', body: JSON.stringify(payload) })
}
export function removePersonnel(id: number) {
  return request<void>(`/api/quality/personnel/${id}`, { method: 'DELETE' })
}
export interface PersonnelImportPreview {
  total: number
  createPersonnel: number
  updatePersonnel: number
  createAccounts: number
  departmentMoves: number
  valid: boolean
  previewToken: string
  errors: { row: number; code: string; message: string }[]
}
export function exportPersonnel(params: { keyword?: string; dept?: string } = {}) {
  return downloadQualityFile(`/api/quality/personnel/export?${qs(params)}`, 'personnel-register.xlsx')
}
export function downloadPersonnelTemplate() {
  return downloadQualityFile('/api/quality/personnel/template', 'personnel-register.xlsx')
}
export function previewPersonnelImport(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<PersonnelImportPreview>('/api/quality/personnel/import-preview', { method: 'POST', body })
}
export function importPersonnel(file: File, previewToken: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('previewToken', previewToken)
  return request<PersonnelImportPreview>('/api/quality/personnel/import', { method: 'POST', body })
}
export function fetchPermOptions() {
  if (!USE_BACKEND) return Promise.resolve(['样品入库', '样品出库', '检测数据录入', '电子原始记录', '报告审核', '报告批准'])
  return request<{ permissions: string[] }>(`/api/quality/perm-options`).then((d) => d.permissions)
}

function paginateDemo<T>(rows: T[], page = 1, size = 20): Paged<T> {
  const safePage = Math.max(1, page)
  const safeSize = Math.max(1, size)
  return {
    rows: rows.slice((safePage - 1) * safeSize, safePage * safeSize),
    total: rows.length,
    page: safePage,
    size: safeSize,
  }
}

// 检测依据/判定标准自动补全（标准库，含一单一库标记）
export interface StdLibHit {
  isOnsiteStandard?: boolean
  id?: number
  code: string
  name: string
  parameters?: string
  authKind: string
  singleList: boolean
  status: string
  cma: boolean
  cnas: boolean
  useDepts: string[]
  controlledNo: string
  capabilityTypes?: string[]
  sites?: string[]
  location?: string
}
export interface StdLibSearchOptions {
  ids?: number[]
  onsiteOnly?: boolean
  capabilityOnly?: boolean
  capabilityType?: string
  site?: string
  date?: string
  scopeFilter?: 'all' | 'cnas' | 'cma' | 'single'
  page?: number
  size?: number
}
export interface JudgmentStandardHit { id: number; code: string; name: string; status: string }
export function loadStandardDisplayNames(codes: string[]) {
  return request<Record<string,string>>('/api/quality/std-library/display-names', {method:'POST',body:JSON.stringify({codes})})
}
export function searchJudgmentStandards(keyword: string) {
  return request<Paged<JudgmentStandardHit>>(
    `/api/quality/std-library/judgment-search?${qs({ keyword, size: 50, page: 1 })}`,
  )
}
export function searchStdLibPage(
  keyword: string,
  department = '',
  options?: StdLibSearchOptions,
) {
  return request<Paged<StdLibHit>>(
    `/api/quality/std-library/search?${qs({
      keyword,
      ids: options?.ids?.join(','),
      dept: department,
      capabilityOnly: options?.capabilityOnly ? 1 : undefined,
      onsiteOnly: options?.onsiteOnly ? 1 : undefined,
      capabilityType: options?.capabilityType,
      site: options?.site,
      date: options?.date,
      scopeFilter: options?.scopeFilter,
      page: options?.page,
      size: options?.size,
    })}`,
  )
}
export function searchStdLib(
  keyword: string,
  department = '',
  options?: StdLibSearchOptions,
) {
  return searchStdLibPage(keyword, department, options).then((d) => d.rows)
}

export function standardIdentityImpact(id:number) {
 return request<{rows:{reportNo:string;department:string;status:string;revision:string;choices:{code:string;candidates:{id:number}[]}[]}[];total:number}>(`/api/quality/std-library/${id}/identity-impact`)
}
export function resolveStandardImpact(id:number, reports:{reportNo:string;revision:string;selections:Record<string,number>}[], reason:string){
 return request(`/api/quality/std-library/${id}/resolve-report-identities`,{method:'POST',body:JSON.stringify({reports,reason})})
}
export function qualityGuardNotices(){return request<{rows:{id:number;reportNo:string;message:string}[]}>('/api/quality/guard-notices')}
