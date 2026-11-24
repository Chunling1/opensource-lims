import { request } from './http'

export interface ParameterRow {
  id: number; itemName: string; objectName: string; capabilityType: string
  site: string; address: string; methodClause: string; restriction: string
  departments: string[]; active: boolean; accreditation: string; internal: boolean
  sourceFile: string; sourcePage: number; sourceRow: number; certificateNo: string
  version: string; standardCode: string; superseded: boolean
}
export interface ParameterDraft {
  itemName: string; objectName: string; capabilityType: string; site: string; address: string
  methodClause: string; restriction: string; departments?: string[]; active: boolean
  reason: string; version?: string; copyFromId?: number
}
export interface ParameterPage { rows: ParameterRow[]; total: number; departments: string[]; sharedSource: boolean }
export interface ParameterStandard { id: number; code: string; name: string; controlledNo?: string }
export const loadStandardParameters = (id: number, keyword = '', page = 1) => request<ParameterPage>(
  `/api/quality/std-library/${id}/parameters?${new URLSearchParams({ keyword, page: String(page), size: '20' })}`)
export const searchParameterStandards = (keyword = '', page = 1) => request<{rows: ParameterStandard[]; total: number}>(
  `/api/quality/std-library/parameter-catalog?${new URLSearchParams({ keyword, page: String(page), size: '20' })}`)
export const saveStandardParameter = (id: number, value: ParameterDraft, entryId?: number) => request<ParameterRow>(
  `/api/quality/std-library/${id}/parameters${entryId ? `/${entryId}` : ''}`,
  { method: entryId ? 'PUT' : 'POST', body: JSON.stringify(value) })
