import type { Actor } from './lims'
import { profile } from '../services/platform/auth'

export const workbenches = [
  { id: 'analyst', title: '主检工作台', icon: 'ti ti-microscope', roles: ['testing'] },
  { id: 'reviewer', title: '审核工作台', icon: 'ti ti-file-search', roles: ['testing', 'reviewer', 'reports'] },
  { id: 'approver', title: '批准工作台', icon: 'ti ti-circle-check', roles: ['approver'] },
  { id: 'admin', title: '管理工作台', icon: 'ti ti-dashboard', roles: ['admin'] },
] as const
export type Workbench = typeof workbenches[number]['id'] | 'general'
export function allowedWorkbench(actor: Actor, id: string): boolean {
  if (id === 'general') return !!profile.value
  const item = workbenches.find(item => item.id === id)
  const permission: Record<string,string> = { analyst: 'testing.data_entry.view', reviewer: 'report.review.view', approver: 'report.approval.view' }
  return !!item && (profile.value?.features?.fullPlatformAuthority === true || !!profile.value?.permissions.includes(permission[id] || '__none__'))
}
export function defaultWorkbench(actor: Actor, remembered?: string | null) {
  if (remembered && allowedWorkbench(actor, remembered)) return `/dashboard/${remembered}`
  const order: Workbench[] = ['admin', 'approver', 'reviewer', 'analyst']
  // A tester's primary responsibility is data entry, even though data checking is also permitted.
  if (!profile.value?.features?.fullPlatformAuthority && !actor.roles.some(role => ['admin', 'approver', 'reviewer', 'reports'].includes(role))) order.reverse()
  return `/dashboard/${order.find(id => allowedWorkbench(actor, id)) || 'general'}`
}
export type DashboardFilter = 'all' | 'overdue' | 'returned'
export interface DashboardQuery { workbench: Workbench; queue?: string; filter?: DashboardFilter; page?: number; pageSize?: number }
export interface DashboardTask {
  id: string; code: string; reportCode: string; name: string; plan: string; inspector: string
  due: string; status: string; returned: boolean; overdue: boolean; to: string; action: string
}
export interface DashboardActivity { id: string; code: string; name: string; actor: string; action: string; at: string; to: string }
export interface DashboardData {
  pending: number; overdue: number; returned: number; completedToday: number
  queues: { id: string; title: string; total: number; to: string }[]
  queue: string; items: DashboardTask[]; total: number; page: number; pageSize: number
  urgent: DashboardTask[]; recent: DashboardActivity[]
  trend: { date: string; count: number }[]; workload: { name: string; count: number }[]; updatedAt: string
}
