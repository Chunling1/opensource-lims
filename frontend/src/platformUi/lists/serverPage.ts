import { reactive } from 'vue'
import { request } from '@/services/http'

export type ListQuery = Record<string, any>
export type ListPage<T = any> = { rows: T[]; total: number; page: number; pageSize: number }

export function fetchListPage<T = any>(path: string, query: ListQuery): Promise<ListPage<T>> {
  return request<ListPage<T>>(path, { method: 'POST', body: JSON.stringify({ ...query, serverPage: true }) })
}

/** Export is explicit, bounded page reads; opening a list never downloads all pages. */
export async function fetchListExport<T = any>(path: string, query: ListQuery): Promise<T[]> {
  const rows: T[] = []
  let expected: number | undefined
  const seen = new Set<unknown>()
  for (let page = 1; ; page++) {
    const result = await fetchListPage<T>(path, { ...query, page, pageSize: 200 })
    if (expected !== undefined && result.total !== expected) throw new Error('导出期间列表已变化，请重新导出')
    expected = result.total
    for(const row of result.rows){
      const r=row as any, key=r.reportNo??r.entrustNo??r.id??(r.contractNo||r.agreement?.id)
      if(key!==undefined&&seen.has(key))throw new Error('导出期间列表已变化，请重新导出')
      if(key!==undefined)seen.add(key)
    }
    rows.push(...result.rows)
    if (rows.length >= result.total) return rows
    if (!result.rows.length) throw new Error('导出期间列表已变化，请重新导出')
  }
}

/** Controllers retain one current page; presentation changes trigger a new request. */
export function createServerPage(initial: ListQuery = {}) {
  const state = reactive({ query: { page: 1, pageSize: 10, ...initial } as ListQuery, total: 0 })
  function setQuery(query: ListQuery) {
    const next = JSON.parse(JSON.stringify(query))
    if (JSON.stringify(state.query) === JSON.stringify(next)) return false
    state.query = next
    return true
  }
  return { state, setQuery }
}
