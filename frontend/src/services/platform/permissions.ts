// Explicit platform permission names; no inference from display labels or demo roles.
import { modules } from '@/data/modules'
export const pagePermissions: Record<string, string> = {
  '/commissions/registration': 'entrust.registration.view', '/commissions/review': 'entrust.contract_review.view',
  '/commissions/query': 'entrust.query.view', '/commissions/changes': 'entrust.change.view',
  '/commissions/cancellation-approval': 'entrust.void_approval.view',
  '/samples/inbound': 'sample.inbound.view', '/samples/outbound': 'sample.outbound.view',
  '/samples/disposal': 'sample.disposal.view', '/samples/flow': 'sample.flow_query.view',
  '/testing/assignment': 'testing.assignment.view', '/testing/sample-pickup': 'testing.sample_pickup.view',
  '/testing/task-query': 'testing.task_query.view', '/testing/data-entry': 'testing.data_entry.view',
  '/testing/data-check': 'testing.data_check.view', '/testing/data-changes': 'testing.data_change.view',
  '/testing/sample-completion': 'testing.completed_sample_handling.view',
  '/testing/data-query': 'report.query.view',
  '/reports/review': 'report.review.view',
  '/reports/approval': 'report.approval.view', '/reports/print': 'report.print.view',
  '/reports/signing': 'report.print.view', '/reports/distribution': 'report.release.view',
  '/reports/archive': 'report.archive.view', '/reports/query': 'report.query.view',
}
for (const module of modules) for (const page of module.pages) pagePermissions[page.path] = page.permission
export function requiredPermission(path: string) {
  return Object.entries(pagePermissions).sort((a,b) => b[0].length-a[0].length).find(([prefix]) => path === prefix || path.startsWith(prefix + '/'))?.[1]
}
