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
}): Promise<FinancePageResult> {
  return Promise.resolve({
    rows: [],
    total: 0,
    page: payload.page || 1,
    size: payload.size || 20,
    nodeStatuses: [],
  })
}

export function fetchFinanceBill(_id: number, _node: string): Promise<{ bill: FinanceBill; events: FinanceEvent[] }> {
  return Promise.reject(new Error('开源版未启用财务管理模块'))
}

export function runFinanceCommand(_id: number, _command: string, _payload: Record<string, unknown>): Promise<FinanceBill> {
  return Promise.reject(new Error('开源版未启用财务管理模块'))
}
