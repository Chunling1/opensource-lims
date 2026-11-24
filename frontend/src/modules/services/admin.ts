// 用户与权限管理服务（超级管理员）。仅后端模式可用。
import { authedFetch, request } from './http'
import { USE_BACKEND } from './auth'

export const ADMIN_AVAILABLE = USE_BACKEND

export interface AdminUserBrief {
  id: number
  account: string
  name: string
  roleKey: string
  roleName: string
  department: string
  departmentId: number | null
  dataScope: { department: string; scopeType: string; description: string }
  permissionCount: number
  actionCount: number
  enabled: boolean
}

export interface DataGrant {
  departmentId: number
  departmentName: string
  seeData: boolean
  seeMembers: boolean
  includeChildren: boolean
  grantedBy?: string
  grantedAt?: string
}

export interface AdminUserDetail extends AdminUserBrief {
  homePath: string
  eSignature: string
  permissions: string[]
  actionPermissions: string[]
  projectStepIds: number[]
  standardAuthorization: StandardAuthorization
  dataDepartmentIds: number[]
  dataGrants: DataGrant[]
  dataSites: string[]
}

export interface OrgNode {
  id: number
  code: string
  name: string
  parentId: number | null
  site: string
  memberCount: number
  children: OrgNode[]
}

export interface OrgMember extends AdminUserBrief {
  dataGrants: DataGrant[]
}

export interface OrgAuthorization {
  equipmentDepartmentIds?: number[]
  equipmentAuthorizationInherited?: boolean
  correctionApproval?: boolean
  correctionApprovalInherited?: boolean
  sealedReportDownload?: boolean
  reportDistribution?: boolean
  reportDeliveryInherited?: boolean
  sealConfirmation?: boolean
  erpAuthorization?: { roles: string[]; administrator: boolean; canManage: boolean }
  department: { id: number; name: string }
  user?: { id: number; account: string; name: string }
  permissions: { code: string; name: string; ptype: string }[]
  projects: {
    id: number
    code: string
    name: string
    department: string
    location?: string
    sourceDepartment?: string
    stepIds: (number | null)[]
  }[]
  stepColumns: {
    code: string
    name: string
    requiredPermissionCodes: string[]
  }[]
  allowedProjectStepIds: number[]
  selectedPermissionCodes: string[]
  selectedProjectIds: number[]
  selectedProjectStepIds: number[]
  selectedTemplateIds?: number[]
  orgWide: boolean
}

export interface PermissionTemplate {
  id: number
  code: string
  name: string
  description: string
  enabled: boolean
  permissionCodes: string[]
  projectStepIds: number[]
  assignedUserCount: number
  syncSummary?: {
    assignedUserCount: number
    updatedUserCount: number
    departmentLimitedUserCount: number
  }
  updatedAt: string
}

export interface PermissionTemplateCatalog {
  rows: PermissionTemplate[]
  permissions: OrgAuthorization['permissions']
  projects: OrgAuthorization['projects']
  stepColumns: OrgAuthorization['stepColumns']
  allowedProjectStepIds: number[]
}

export interface PermissionTemplatePayload {
  code: string
  name: string
  description: string
  enabled: boolean
  permissionCodes: string[]
  projectStepIds: number[]
}

export interface PermissionAppointmentPreview {
  sourceSha256: string
  previewToken: string
  sourceRows: number
  peopleCount: number
  matchedPeopleCount: number
  unmatchedPeopleCount: number
  matchedPeople: string[]
  unmatchedPeople: string[]
  projectCodeCount: number
  matchedProjectCodeCount: number
  newProjectCount: number
  newProjects: {
    projectCode: string
    name: string
    department: string
    sourceDepartment: string
    location: string
  }[]
  ignoredRowCount: number
  ignoredRole: string
  managedRowCount: number
  grantCount: number
  templateCount: number
  templateAssignments: number
  exceptions: { type: string; person?: string; projectCode?: string; detail: string }[]
  blockingErrors: { type: string; projectCode?: string; detail: string }[]
  batchId?: number
}

export interface AdminProject {
  id: number
  code: string
  name: string
  department: string
  departmentId: number | null
  numberCode: string
  location: string
  stepIds: (number | null)[] // 与 stepColumns 对齐
}

export interface AdminStandardItem {
  id: number
  code: string
  name: string
  authKind: string
  status: string
}

export interface StandardAuthorization {
  department: string
  items: AdminStandardItem[]
  authorizedItemIds: number[]
}

export interface AdminCatalog {
  permissions: { code: string; name: string; ptype: string }[]
  actions: { code: string; name: string }[]
  departments: { id: number; name: string }[]
  sites: string[]
  stepColumns: { code: string; name: string }[]
  projects: AdminProject[]
  scopeTypes: { value: string; label: string }[]
}

export interface UpdateUserPayload {
  name?: string
  permissions?: string[]
  actionPermissions?: string[]
  projectStepIds?: number[]
  standardItemIds?: number[]
  dataDepartmentIds?: number[]
  dataSites?: string[]
  dataScopeType?: string
  dataScopeDesc?: string
  departmentId?: number | null
  roleName?: string
  homePath?: string
  enabled?: boolean
  eSignature?: string
  personnel?: Record<string, unknown>
}

export function listUsers() {
  return request<{ rows: AdminUserBrief[] }>('/api/admin/users').then((d) => d.rows)
}
export function getUser(id: number) {
  return request<AdminUserDetail>(`/api/admin/users/${id}`)
}
export function getCatalog() {
  return request<AdminCatalog>('/api/admin/catalog')
}
export function getDepartmentStandardCatalog(departmentId: number, userId?: number) {
  const query = new URLSearchParams({ departmentId: String(departmentId) })
  if (userId) query.set('userId', String(userId))
  return request<StandardAuthorization>(
    `/api/admin/standard-catalog?${query.toString()}`,
  )
}
export function resetUserPassword(id: number, password?: string) {
  return request<{ tempPassword: string }>(`/api/admin/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify(password ? { password } : {}),
  })
}
export function updateUser(id: number, payload: UpdateUserPayload) {
  return request<AdminUserDetail>(`/api/admin/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function createUser(payload: {
  account: string
  name: string
  password?: string
  roleName?: string
  departmentId?: number | null
  dataScopeType?: string
  dataScopeDesc?: string
  personnel?: Record<string, unknown>
}) {
  return request<{ user: AdminUserDetail; tempPassword: string; personnelId: number }>('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ---------- 组织机构 ----------
export function fetchOrgTree() {
  return request<{ tree: OrgNode[] }>('/api/admin/departments/tree').then((d) => d.tree)
}
export function fetchOrgMembers(deptId: number) {
  return request<{ department: { id: number; name: string }; rows: OrgMember[] }>(
    `/api/admin/departments/${deptId}/members`,
  )
}
export function getDepartmentAuthorizations(deptId: number) {
  return request<OrgAuthorization>(`/api/admin/departments/${deptId}/authorizations`)
}
export function updateDepartmentAuthorizations(
  deptId: number,
  payload: { permissionCodes: string[]; projectIds: number[] },
) {
  return request<OrgAuthorization>(`/api/admin/departments/${deptId}/authorizations`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function getMemberAuthorizations(deptId: number, userId: number) {
  return request<OrgAuthorization>(
    `/api/admin/departments/${deptId}/members/${userId}/authorizations`,
  )
}
export function updateMemberAuthorizations(
  deptId: number,
  userId: number,
  payload: {
    permissionCodes: string[]
    projectStepIds: number[]
    templateIds?: number[]
    expandProjectScope?: boolean
    equipmentDepartmentIds?: number[]
    erpPermissions?: string[]
    correctionApproval?: boolean
    sealedReportDownload?: boolean
    reportDistribution?: boolean
    sealConfirmation?: boolean
  },
) {
  return request<OrgAuthorization>(
    `/api/admin/departments/${deptId}/members/${userId}/authorizations`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}
export function listPermissionTemplates() {
  return request<PermissionTemplateCatalog>('/api/admin/permission-templates')
}
export function createPermissionTemplate(payload: PermissionTemplatePayload) {
  return request<PermissionTemplate>('/api/admin/permission-templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function updatePermissionTemplate(id: number, payload: PermissionTemplatePayload) {
  return request<PermissionTemplate>(`/api/admin/permission-templates/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function deletePermissionTemplate(id: number) {
  return request<null>(`/api/admin/permission-templates/${id}`, { method: 'DELETE' })
}
export async function exportPermissionWorkbook() {
  const response = await authedFetch('/api/admin/permission-templates/export')
  if (!response.ok) throw new Error(`导出失败：HTTP ${response.status}`)
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const filename = encoded ? decodeURIComponent(encoded) : '人员权限模板与实际权限.xlsx'
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
export function importPermissionWorkbook(file: File) {
  const body = new FormData()
  body.append('file', file)
  body.append('replace', '1')
  return request<{ templateCount: number; userCount: number }>(
    '/api/admin/permission-templates/import',
    { method: 'POST', body },
  )
}
export function previewPermissionAppointmentWorkbook(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<PermissionAppointmentPreview>(
    '/api/admin/permission-templates/appointment-import/preview',
    { method: 'POST', body },
  )
}
export function applyPermissionAppointmentWorkbook(file: File, sourceSha256: string, previewToken: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('sourceSha256', sourceSha256)
  body.append('previewToken', previewToken)
  body.append('replaceScope', 'report-managed')
  return request<PermissionAppointmentPreview>(
    '/api/admin/permission-templates/appointment-import/apply',
    { method: 'POST', body },
  )
}
export function createDepartment(payload: { name: string; parentId?: number | null; site?: string }) {
  return request<{ id: number; name: string }>('/api/admin/departments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function updateDepartment(id: number, payload: { name?: string; parentId?: number | null; site?: string }) {
  return request<{ id: number; name: string }>(`/api/admin/departments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
export function deleteDepartment(id: number) {
  return request<null>(`/api/admin/departments/${id}`, { method: 'DELETE' })
}
export function setGrant(uid: number, payload: {
  departmentId: number
  seeData: boolean
  seeMembers: boolean
  includeChildren: boolean
}) {
  return request<DataGrant[]>(`/api/admin/users/${uid}/grants`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function revokeGrant(uid: number, deptId: number) {
  return request<null>(`/api/admin/users/${uid}/grants/${deptId}`, { method: 'DELETE' })
}

export interface CnasBatch {
  id: number
  sourceName: string
  sourceSha256: string
  status: 'review' | 'active' | 'retired'
  attachmentCount: number
  chinesePageCount: number
  entryCount: number
  pendingCount: number
  anomalyCount: number
  createdAt: string
  activatedAt: string
}

export interface CnasMappingEntry {
  id: number
  capabilityType: string
  site: string
  objectName: string
  itemName: string
  standardCode: string
  standardName: string
  restriction: string
  sourceFile: string
  sourcePage: number
  mappingStatus: string
  departments: string[]
}

interface AdminPaged<T> {
  rows: T[]
  total: number
  page: number
  size: number
}

export function listCnasBatches() {
  return request<{ rows: CnasBatch[] }>('/api/admin/cnas/batches').then((data) => data.rows)
}

export function listCnasEntries(
  batchId: number,
  params: { keyword?: string; mappingStatus?: string; page?: number; size?: number },
) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  return request<AdminPaged<CnasMappingEntry>>(
    `/api/admin/cnas/batches/${batchId}/entries?${query}`,
  )
}

export function updateCnasEntryDepartments(entryId: number, departmentIds: number[]) {
  return request<CnasMappingEntry>(`/api/admin/cnas/entries/${entryId}/departments`, {
    method: 'PUT',
    body: JSON.stringify({ departmentIds }),
  })
}

export function activateCnasBatch(batchId: number) {
  return request<{ id: number; status: string }>(
    `/api/admin/cnas/batches/${batchId}/activate`,
    { method: 'POST', body: '{}' },
  )
}
