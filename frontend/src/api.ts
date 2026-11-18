export interface User {
  name: string
  department: string
  permissions: string[]
}
export interface Person {
  id: number
  name: string
}
export interface Actions {
  [name: string]: string
}
export interface Document {
  id: number
  name: string
  kind: 'source' | 'draft'
  size: number
  created: string
  uploader: string
  sha256: string
}
export interface Report {
  version: number
  id: number
  number: string
  state: 'draft' | 'review' | 'cancelled'
  start: string | null
  end: string | null
  reviewerId: number | null
  reviewers: Person[]
  files: Document[]
  actions: Actions
}
export interface Sample {
  id: number
  number: string
  name: string
  commission: string
  owner: string | null
  version: number
  today: string
  template: string
  frozen: boolean
  designated: boolean
  physical: boolean
  receivedDate: string | null
  siteDate: string | null
  commissionDate: string
  projects: string[]
  actions: Actions
  targets: Person[]
  rules: { id: number; prefix: string }[]
  reports: Report[]
}
export interface Listing {
  total: number
  page: number
  pageSize: number
  rows: { id: number; number: string; name: string; commission: string; frozen: boolean }[]
}
export interface ReportRow {
  id: number
  number: string
  state: Report['state']
  sampleId: number
  sampleName: string
  sampleNumber: string
  commission: string
  owner: string | null
}
export const reportStates = { draft: '编制中', review: '审1 待办理', cancelled: '已取消' } as const
export const taskLabels = {
  claim: '待领取',
  author: '编制中',
  returned: '被退回',
  review1: '待审核',
} as const
export type TaskKind = keyof typeof taskLabels
export interface TaskList {
  counts: Record<TaskKind, number>
  total: number
  page: number
  pageSize: number
  rows: {
    kind: TaskKind
    sampleId: number
    reportId: number | null
    name: string
    number: string
    source: string
    arrived: string | null
  }[]
}
export type Fields = Record<string, string | number | File>
export type Command = (action: string, values?: Fields) => Promise<boolean>

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

export async function api<T>(path: string, body?: object | FormData): Promise<T> {
  const headers: Record<string, string> = {}
  if (body) headers['X-LIMS-Action'] = '1'
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const response = await fetch('/api/' + path, {
    method: body ? 'POST' : 'GET',
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json()
  if (!response.ok) throw new ApiError(data.error, response.status)
  return data
}
