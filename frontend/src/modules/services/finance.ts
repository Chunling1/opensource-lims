import { request } from './http'
import { USE_BACKEND } from './auth'
import { demoFinanceBills } from '@/data/moduleDemo'

export interface FinanceBill {
  id: number
  billNo: string
  entrustNo: string
  contractNo: string
  client: string
  projectName: string
  department: string
  amountDue: string
  pendingPayment: string
  amountReceived: string
  amountInvoiced: string
  amountRefunded: string
  netReceived: string
  outstanding: string
  status: string
  paymentMethod: string
  paymentReference: string
  paymentDate: string
  invoiceNo: string
  invoiceType: string
  invoiceDate: string
  settlementNo: string
  settlementDate: string
  refundDate: string
  note: string
  version: number
  createdBy: string
  updatedBy: string
  createdAt: string
  updatedAt: string
  paymentPreviousAt?: string
  priceAt?: string
  paymentConfirmedAt?: string
  invoiceAt?: string
  settlementAt?: string
  refundAt?: string
  workflowDates?: {
    paymentPreviousAt?: string
    priceAt?: string
    paymentConfirmedAt?: string
    invoiceAt?: string
    settlementAt?: string
    refundAt?: string
  }
}

export interface FinanceEvent {
  id: number
  action: string
  userName: string
  createdAt: string
  message: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}

export interface FinancePageResult {
  rows: FinanceBill[]
  total: number
  page: number
  size: number
  nodeStatuses: string[]
}

export function fetchFinanceBills(payload: {
  node: string
  keyword?: string
  status?: string
  page?: number
  size?: number
  all?: boolean
}) {
  if (!USE_BACKEND) {
    const nodeStatuses: Record<string, string[]> = {
      pricing: ['待计价'], payment_registration: ['待收款'], payment_confirmation: ['待收款确认'],
      invoice: ['待开票'], settlement: ['待结算'], account_refund: ['已结算', '部分退款'],
    }
    const keyword = String(payload.keyword || '').trim().toLowerCase()
    const matched = (demoFinanceBills as FinanceBill[]).filter((row) =>
      (nodeStatuses[payload.node] || []).includes(row.status)
      && (!keyword || `${row.billNo} ${row.entrustNo} ${row.contractNo} ${row.client} ${row.projectName}`.toLowerCase().includes(keyword)),
    )
    const page = payload.page || 1
    const size = payload.size || 20
    return Promise.resolve({
      rows: matched.slice((page - 1) * size, page * size), total: matched.length, page, size,
      nodeStatuses: nodeStatuses[payload.node] || [],
    })
  }
  return request<FinancePageResult>('/api/finance/bills/query', {
    method: 'POST', body: JSON.stringify(payload),
  })
}

export function fetchFinanceBill(id: number, node: string) {
  if (!USE_BACKEND) {
    const bill = (demoFinanceBills as FinanceBill[]).find((item) => item.id === id)
    if (!bill) return Promise.reject(new Error('演示费用单不存在'))
    return Promise.resolve({
      bill,
      events: [{ id: id * 10, action: '演示节点', userName: '演示财务员', createdAt: bill.updatedAt, message: `当前节点：${node}`, before: null, after: { status: bill.status } }],
    })
  }
  return request<{ bill: FinanceBill; events: FinanceEvent[] }>(
    `/api/finance/bills/${id}?node=${encodeURIComponent(node)}`,
  )
}

export function runFinanceCommand(id: number, command: string, payload: Record<string, unknown>) {
  if (!USE_BACKEND) return Promise.reject(new Error('本地演示模式不会保存财务操作'))
  return request<FinanceBill>(`/api/finance/bills/${id}/${command}`, {
    method: 'POST', body: JSON.stringify(payload),
  })
}
