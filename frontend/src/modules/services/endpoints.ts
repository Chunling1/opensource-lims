import { request } from './http'

export interface QueryParams {
  keyword?: string
  status?: string
  dateRange?: [string, string]
  page?: number
  pageSize?: number
}

export interface PageResult<T> {
  rows: T[]
  total: number
}

export const inspectionApi = {
  entrusts: (params: QueryParams) => request<PageResult<unknown>>('/api/entrusts/query', asPost(params)),
  samples: (params: QueryParams) => request<PageResult<unknown>>('/api/samples/query', asPost(params)),
  testingTasks: (params: QueryParams) => request<PageResult<unknown>>('/api/testing/tasks/query', asPost(params)),
  reports: (params: QueryParams) => request<PageResult<unknown>>('/api/reports/query', asPost(params)),
  approvals: (params: QueryParams) => request<PageResult<unknown>>('/api/approvals/query', asPost(params)),
  // financeBills removed in open-source edition (D-150)
  qualityAssets: (params: QueryParams) => request<PageResult<unknown>>('/api/quality/assets/query', asPost(params)),
}

export const systemApi = {
  erpLogs: (params: QueryParams) => request<PageResult<unknown>>('/api/system/erp/logs', asPost(params)),
  notificationLogs: (params: QueryParams) => request<PageResult<unknown>>('/api/system/notifications/logs', asPost(params)),
  reportTemplates: (params: QueryParams) => request<PageResult<unknown>>('/api/system/report-templates/query', asPost(params)),
  collectionLogs: (params: QueryParams) => request<PageResult<unknown>>('/api/system/auto-collection/logs', asPost(params)),
  users: (params: QueryParams) => request<PageResult<unknown>>('/api/system/users/query', asPost(params)),
}

function asPost(body: unknown): RequestInit {
  return {
    method: 'POST',
    body: JSON.stringify(body),
  }
}
