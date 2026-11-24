import { platformRequest } from '../../services/platform/http'
import type { EquipItem } from '@/services/quality'
export interface EquipmentScheme {
  id: number; name: string; departmentId: number; department: string; equipmentIds: number[]
  projectIds: number[]; enabled: boolean; version: number; recommended?: boolean
}
export interface SchemeCatalogue {
  departmentId: number; department: string; canManage: boolean; projectId: number | null
  departments: { id: number; name: string }[]
  schemes: EquipmentScheme[]; projects: { id: number; code: string; name: string }[]; equipment: EquipItem[]
}
export interface SchemeResolution {
  schemeId: number; version: number; rows: EquipItem[]
  skipped: { id: string; code: string; name: string; reason: string }[]
}
export const equipmentSchemes = {
  catalogue: (reportNo?: string, departmentId?: number) => platformRequest<SchemeCatalogue>('/api/equipment-schemes?' + new URLSearchParams(reportNo ? { reportNo } : departmentId ? { departmentId: String(departmentId) } : {})),
  save: (body: Partial<EquipmentScheme>) => platformRequest<EquipmentScheme>(`/api/equipment-schemes${body.id ? '/' + body.id : ''}`, { method: body.id ? 'PUT' : 'POST', body }),
  resolve: (id: number, reportNo: string, intervals: { start: string; end: string }[]) => platformRequest<SchemeResolution>(`/api/equipment-schemes/${id}/resolve?` + new URLSearchParams({ reportNo, intervals: JSON.stringify(intervals) })),
}
