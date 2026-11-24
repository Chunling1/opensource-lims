import { modules } from '@/data/modules'
import type { ReportRow } from '@/services/auth'

export const dashboardRoutes: Record<string, { view: string; path: string }> = {
  待合同评审: { view: 'contract_review', path: '/inspection/report/contract_review' },
  待样品入库: { view: 'sample_inbound', path: '/inspection/sample/inbound' },
  待样品领取: { view: 'sample_outbound', path: '/inspection/sample/outbound' },
  检测录入中: { view: 'data_entry', path: '/inspection/testing/data_entry' },
  退回待重传: { view: 'data_change', path: '/inspection/testing/data_change' },
  检测更改中: { view: 'data_change', path: '/inspection/testing/data_change' },
  待审核: { view: 'review', path: '/inspection/report/review' },
  待批准: { view: 'approval', path: '/inspection/report/approval' },
  待打印: { view: 'print', path: '/inspection/report/print' },
  待发放: { view: 'archive', path: '/inspection/report/archive' },
  已发放: { view: 'archive', path: '/inspection/report/archive' },
  委托更改中: { view: 'entrust_change', path: '/inspection/entrust/change' },
}

export function canOpenDashboardPath(path: string, can: (permission: string) => boolean): boolean {
  const page = modules.flatMap(module => module.pages).find(page => page.path === path)
  return Boolean(page && can(page.permission))
}

export function dashboardTarget(row: ReportRow, can: (permission: string) => boolean, readOnly = false): string | undefined {
  const target = row.todoView === 'release' ? {view: 'release', path: '/inspection/report/release'} : row.todoView === 'archive' ? {view: 'archive', path: '/inspection/report/archive'} : dashboardRoutes[row.status]
  // Fail closed for old/query/mock payloads that have no authorized projection.
  if (readOnly || row.voided || !target || row.todoView !== target.view) return undefined
  return canOpenDashboardPath(target.path, can) ? target.path : undefined
}
