import { request } from './http'
export interface TechnicalParameter { id: number; name: string; method: string; standard: string; site: string; restriction: string }
export interface TechnicalSubproject { id: number; revision: number; code: string; name: string; projectId: number; projectCode: string; projectName: string; department: string; location: string; templateId: number; templateCode: string; templateName: string; enabled: boolean; parameters: TechnicalParameter[] }
export interface TechnicalOptions { projects: { id: number; code: string; name: string; department: string }[]; templates: { id: number; code: string; name: string }[]; parameters: TechnicalParameter[] }
export const listTechnicalSubprojects = (all = false) => request<{ rows: TechnicalSubproject[] }>('/api/technical-subprojects' + (all ? '?all=1' : '')).then(v => v.rows)
export const technicalOptions = (keyword = '') => request<TechnicalOptions>('/api/technical-subprojects/options?keyword=' + encodeURIComponent(keyword))
export const saveTechnicalSubproject = (data: Partial<TechnicalSubproject> & { parameterIds: number[] }) => request<TechnicalSubproject>('/api/technical-subprojects' + (data.id ? '/' + data.id : ''), { method: data.id ? 'PUT' : 'POST', body: JSON.stringify(data) })
export function technicalSummary(rows: TechnicalSubproject[]): [string, string][] {
  return rows.flatMap(row => [[`${row.code} · ${row.name}`, `${row.projectName} / ${row.department} / ${row.location}`], ['参数 / 方法 / 标准', row.parameters.map(p => `${p.name}；${p.method}；${p.standard}`).join(' | ')], ['报告模板', row.templateName]] as [string, string][])
}
