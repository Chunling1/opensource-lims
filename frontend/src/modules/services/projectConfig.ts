import { request } from './http'

export interface ProjectWorkflowStep {
  code: string
  name: string
  skipped?: boolean
}

export interface ApprovalStageConfig {
  name: string
  roleKey: string
  userAccounts: string[]
}

export interface ProjectMaster {
  id: number
  code: string
  name: string
  departmentId: number
  department: string
  location: string
  reportTitle: string
  centerPrefix: string
  testCategory: string
  reportType: string
  testDept: string
  detectionParameters: string
  sampleAmount: string
  sampleStatus: string
  testLocation: string
  active: boolean
  skippedSteps: string[]
  workflowSteps: ProjectWorkflowStep[]
  reviewStages?: ApprovalStageConfig[]
  approvalStages?: ApprovalStageConfig[]
  externalPublished?: boolean
  title?: string
  /** Transitional compatibility with early portal drafts. */
  externalTitle?: string
  summary?: string
  category?: string
  tags?: string[]
  priceType?: ExternalPriceType
  priceMin?: number | null
  priceMax?: number | null
  priceUnit?: string
  originalPrice?: number | null
  turnaroundDays?: number | null
  promotion?: string
  featured?: boolean
  sort?: number
  detail?: string
  sampleRequirements?: string
  contactPhone?: string
}

export type ExternalPriceType = 'fixed' | 'range' | 'negotiable'

export interface ProjectMasterCatalog {
  rows: ProjectMaster[]
  workflowSteps: ProjectWorkflowStep[]
  departments: { id: number; name: string }[]
}

export interface ProjectMasterPayload {
  code: string
  name: string
  departmentId: number | null
  location: string
  reportTitle: string
  centerPrefix: string
  testCategory: string
  reportType: string
  detectionParameters: string
  sampleAmount: string
  sampleStatus: string
  testLocation: string
  skippedSteps: string[]
  reviewStages?: ApprovalStageConfig[]
  approvalStages?: ApprovalStageConfig[]
  active?: boolean
  externalPublished: boolean
  title: string
  summary: string
  category: string
  tags: string[]
  priceType: ExternalPriceType
  priceMin: number | null
  priceMax: number | null
  priceUnit: string
  originalPrice: number | null
  turnaroundDays: number | null
  promotion: string
  featured: boolean
  sort: number
  detail: string
  sampleRequirements: string
  contactPhone: string
}

export interface PortalCatalogCandidate {
  projectId: number
  projectName: string
  department: string
  objectName: string
  matchType: 'exact' | 'alias'
  score: number
  eligible: boolean
  selected: boolean
  reason: string
}

export interface PortalCatalogDiagnostics {
  departments: Record<string, number>
  candidates: PortalCatalogCandidate[]
  rejected: Array<{ projectId: number; project: string; department: string; reason: string }>
}

export interface PortalCatalogSyncResult {
  dryRun: boolean
  selected: number
  created: number
  updated: number
  unchanged: number
  rejected: number
  departments: Record<string, number>
  changes: Array<{ action: 'create' | 'update'; projectId: number; objectName: string; department: string; score: number }>
}

export function getProjectMasters(keyword = '', includeInactive = false) {
  const query = new URLSearchParams({
    keyword,
    includeInactive: includeInactive ? '1' : '0',
  })
  return request<ProjectMasterCatalog>(`/api/admin/project-masters?${query}`)
}

export function createProjectMaster(payload: ProjectMasterPayload) {
  return request<ProjectMaster>('/api/admin/project-masters', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProjectMaster(id: number, payload: ProjectMasterPayload) {
  return request<ProjectMaster>(`/api/admin/project-masters/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteProjectMaster(id: number) {
  return request<ProjectMaster>(`/api/admin/project-masters/${id}`, {
    method: 'DELETE',
  })
}

export function getPortalCatalogDiagnostics() {
  return request<PortalCatalogDiagnostics>('/api/admin/portal-service-catalog/diagnostics')
}

export function syncPortalCatalog(apply = false) {
  return request<PortalCatalogSyncResult>('/api/admin/portal-service-catalog/sync', {
    method: 'POST',
    body: JSON.stringify({ apply }),
  })
}
