/** Pure column metadata: safe to share with server-side exports. */
export interface TableColumn<Key extends string = string> {
  key: Key
  label: string
  group?: string
  default?: boolean
  required?: boolean
  sort?: string
  money?: boolean
  wrap?: boolean
  truncate?: number
  fullTitle?: boolean
}

export interface TablePaginationState {
  total: number
  page: number
  pageSize: number
  sizes: number[]
}
