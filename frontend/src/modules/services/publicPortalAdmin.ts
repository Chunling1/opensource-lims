import { request } from './http'

export type ExternalEntrustmentStatus = 'draft' | 'submitted' | 'accepted' | 'rejected' | 'cancelled' | string

export interface ExternalEntrustment {
  id: number
  applicationNo: string
  status: ExternalEntrustmentStatus
  customerName: string
  customerPhone: string
  companyName: string
  projectTitle: string
  projectCode: string
  estimatedAmount: number | null
  submittedAt: string
  formData: Record<string, unknown>
  internalEntrustNo: string
  note?: string
  reviewedAt?: string
  reviewerName?: string
}

export interface ExternalEntrustmentList {
  rows: ExternalEntrustment[]
  total: number
}

export interface ExternalEntrustmentQuery {
  keyword?: string
  status?: string
  page?: number
  size?: number
}

export interface ExternalCustomerDocumentAdmin {
  id: string
  kind: string
  kindLabel: string
  title: string
  documentNo: string
  reportNo: string
  fileName: string
  status: string
  publishedAt: string
}

export interface ExternalShipmentAdmin {
  id: number
  carrier: string
  trackingNo: string
  status: string
  statusLabel: string
  latestEvent: string
  events: Array<{ time: string; status: string; location: string; description: string }>
  shippedAt: string
  deliveredAt: string
  updatedAt: string
}

export interface ExternalNotificationAdmin {
  id: number
  category: string
  title: string
  content: string
  read: boolean
  publishedAt: string
}

export interface ExternalCustomerServices {
  documents: ExternalCustomerDocumentAdmin[]
  shipments: ExternalShipmentAdmin[]
  notifications: ExternalNotificationAdmin[]
}

function normalizeExternalEntrustment(raw: Record<string, unknown>): ExternalEntrustment {
  const formData = raw.formData ?? raw.form_data
  const amount = raw.estimatedAmount ?? raw.estimated_amount
  return {
    id: Number(raw.id ?? 0),
    applicationNo: String(raw.applicationNo ?? raw.application_no ?? ''),
    status: String(raw.status ?? 'pending'),
    customerName: String(raw.customerName ?? raw.customer_name ?? ''),
    customerPhone: String(raw.customerPhone ?? raw.customer_phone ?? ''),
    companyName: String(raw.companyName ?? raw.company_name ?? ''),
    projectTitle: String(raw.projectTitle ?? raw.project_title ?? ''),
    projectCode: String(raw.projectCode ?? raw.project_code ?? ''),
    estimatedAmount: amount == null || amount === '' ? null : Number(amount),
    submittedAt: String(raw.submittedAt ?? raw.submitted_at ?? ''),
    formData: formData && typeof formData === 'object' && !Array.isArray(formData)
      ? formData as Record<string, unknown>
      : {},
    internalEntrustNo: String(raw.internalEntrustNo ?? raw.internal_entrust_no ?? ''),
    note: String(raw.note ?? ''),
    reviewedAt: String(raw.reviewedAt ?? raw.reviewed_at ?? ''),
    reviewerName: String(raw.reviewerName ?? raw.reviewer_name ?? ''),
  }
}

export async function getExternalEntrustments(query: ExternalEntrustmentQuery = {}) {
  const params = new URLSearchParams()
  if (query.keyword) params.set('keyword', query.keyword)
  if (query.status) params.set('status', query.status)
  params.set('page', String(query.page ?? 1))
  params.set('size', String(query.size ?? 20))
  const data = await request<ExternalEntrustmentList | ExternalEntrustment[]>(
    `/api/admin/external-entrustments?${params}`,
  )
  const source = Array.isArray(data) ? data : data.rows ?? []
  return {
    rows: source.map((row) => normalizeExternalEntrustment(row as unknown as Record<string, unknown>)),
    total: Array.isArray(data) ? data.length : Number(data.total ?? source.length),
  }
}

export function acceptExternalEntrustment(id: number, note = '') {
  return request<ExternalEntrustment>(`/api/admin/external-entrustments/${id}/accept`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export function rejectExternalEntrustment(id: number, note: string) {
  return request<ExternalEntrustment>(`/api/admin/external-entrustments/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export function getExternalCustomerServices(id: number) {
  return request<ExternalCustomerServices>(`/api/admin/external-entrustments/${id}/customer-services`)
}

export function publishExternalCustomerDocument(id: number, payload: {
  kind: 'certificate' | 'invoice' | 'other'
  title: string
  documentNo?: string
  reportNo?: string
  issuedAt?: string
  file: File
}) {
  const body = new FormData()
  body.append('kind', payload.kind)
  body.append('title', payload.title)
  if (payload.documentNo) body.append('documentNo', payload.documentNo)
  if (payload.reportNo) body.append('reportNo', payload.reportNo)
  if (payload.issuedAt) body.append('issuedAt', payload.issuedAt)
  body.append('file', payload.file)
  return request<ExternalCustomerDocumentAdmin>(`/api/admin/external-entrustments/${id}/customer-documents`, {
    method: 'POST', body,
  })
}

export function withdrawExternalCustomerDocument(applicationId: number, documentId: string | number) {
  const id = String(documentId).replace(/^customer:/, '')
  return request<ExternalCustomerDocumentAdmin>(`/api/admin/external-entrustments/${applicationId}/customer-documents/${id}`, {
    method: 'DELETE',
  })
}

export function saveExternalCustomerShipment(applicationId: number, payload: {
  id?: number
  carrier: string
  trackingNo: string
  status: string
  latestEvent?: string
  shippedAt?: string
  deliveredAt?: string
  events?: Array<{ time: string; status: string; location: string; description: string }>
}) {
  return request<ExternalShipmentAdmin>(`/api/admin/external-entrustments/${applicationId}/customer-shipments`, {
    method: 'POST', body: JSON.stringify(payload),
  })
}

export function publishExternalCustomerNotification(applicationId: number, payload: {
  title: string
  content: string
  category?: string
}) {
  return request<ExternalNotificationAdmin>(`/api/admin/external-entrustments/${applicationId}/customer-notifications`, {
    method: 'POST', body: JSON.stringify(payload),
  })
}
