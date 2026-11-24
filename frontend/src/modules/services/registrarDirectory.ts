import { request } from './http'
export interface RegistrarOption {
  id: number
  name: string
  account?: string
  enabled?: boolean
  code?: string
  departmentId?: number | null
  department?: string
}
export function fetchRegistrarOptions(kind: 'people' | 'departments', keyword: string, page: number, signal?: AbortSignal) {
  const query = new URLSearchParams({ kind, keyword, page: String(page) })
  return request<{ rows: RegistrarOption[]; total: number; page: number }>(`/api/admin-corrections/registrar-options?${query}`, { signal })
}
