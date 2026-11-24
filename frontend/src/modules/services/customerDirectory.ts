import { request } from './http'
import type { Customer } from './pipeline'

export type CustomerPage = { rows: Customer[]; total: number; page: number; size: number }
export function fetchCustomerPage(keyword: string, page = 1, size = 20, refresh = false, signal?: AbortSignal): Promise<CustomerPage> {
  const params = new URLSearchParams({ keyword, page: String(page), size: String(size), refresh: refresh ? '1' : '0' })
  return request<CustomerPage>(`/api/customers/search?${params}`, { signal })
}

export function splitCustomerNames(value: string): string[] {
  return [...new Set(value.split(/[、；;\n]/).map(v => v.trim()).filter(Boolean))]
}

// A selection updates the name field only. Contact information is filled only
// for an explicit single-client choice, never by background list refresh.
export function customerContactFields(rows: Customer[]) {
  if (rows.length !== 1 || !rows[0]?.code) return null
  const c = rows[0]!
  return { clientAddr: c.addr || '', clientLegal: c.legal || '', clientPhone: c.phone || '', clientZip: c.zip || '' }
}
