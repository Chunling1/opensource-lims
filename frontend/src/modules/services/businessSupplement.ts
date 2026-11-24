import { request } from './http'
import type { EsignBinding } from './esign'
export interface SubprojectOption {
  id: number; code: string; name: string; dept: string; businessCategory: string
  enabled: boolean; revision: number; updatedAt?: string
}
export interface ErpSubprojectOption {
  source: 'erp'; contractNo: string; code: string; name: string
  dept: string; departmentCode: string; businessCategory: string; businessCategoryCode: string
  sourceKey: string; sourceEventId: string; sourceProof: string; sourceAmount: string
  sourceStatus: string; enabled: boolean; projectName: string
}
export const fetchErpSubprojects = (entrustNo: string, contractNo = '', reportNo = '') => request<{
  rows: ErpSubprojectOption[]; receivedAt: string; disabledCount: number
}>('/api/erp-subprojects/options?' + new URLSearchParams({ entrustNo, contractNo, reportNo }))
export const fetchSubprojects = (all = false) => request<{ rows: SubprojectOption[] }>(
  '/api/business-supplement/subprojects' + (all ? '?all=1' : ''),
).then(data => data.rows)
export const saveSubproject = (row: Partial<SubprojectOption>) => request<SubprojectOption>(
  '/api/business-supplement/subprojects' + (row.id ? '/' + row.id : ''),
  { method: row.id ? 'PUT' : 'POST', body: JSON.stringify(row) },
)
export interface RosterBindingPreview {
  canBind: boolean; userId?: number; legalName?: string; mobileMasked?: string
  reason?: string; binding?: EsignBinding; reconnectedSigners?: number
}
export const previewRosterBinding = (userId: number | 'me' = 'me') =>
  request<RosterBindingPreview>('/api/business-supplement/roster-binding/' + userId)
export const bindRosterPhone = (userId: number | 'me' = 'me') =>
  request<RosterBindingPreview>('/api/business-supplement/roster-binding/' + userId,
    { method: 'POST', body: JSON.stringify({ confirmed: true }) })
