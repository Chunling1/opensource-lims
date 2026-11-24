import { modules } from '@/data/modules'
export type Availability = { status: 'available' | 'removed' | 'pending'; reason: string }
const available: Availability = { status: 'available', reason: '' }
const pending: Availability = { status: 'pending', reason: '此入口尚未完成新平台接口适配，暂不可用。当前状态不代表后端已取消此功能。' }
export const removedReportCheck: Availability = {
  status: 'removed',
  reason: '现平台已取消独立“报告校核”节点，报告流程以现后端为准。请使用“报告审核”或“报告批准”；“中间报告”不是报告校核。',
}
const connectedLists = new Set([
  '/commissions/registration', '/commissions/review', '/commissions/query',
  '/samples/inbound', '/samples/outbound', '/samples/flow',
  '/testing/data-entry', '/testing/data-query', '/testing/data-changes',
  '/reports/review', '/reports/approval', '/reports/query',
])
const originalPages = new Set(modules.flatMap(module=>module.pages.map(page=>page.path)))
// These former placeholder screens have no verified read/write adapter. Never
// present their mock arrays or localStorage "save" as live platform behavior.
export const unconnectedPages = new Map<string,string>([
  ...['monthly_calibration_plan','supplier_evaluation','reference_material','consumables','test_environment','daily_affairs','daily_affairs_approval'].map(key=>[`/inspection/quality/${key}`,'现平台接口目录尚无此页面对应的业务维护接口，暂不可操作；不会显示演示记录。'] as [string,string]),
  ...['runtime_parameters','approval_settings','project_workflow','logs','sms_settings','integration_erp','report_template','auto_collection'].map(key=>[`/inspection/system/${key}`,'此设置页面尚未建立与现平台一致的读取、保存契约，暂不可操作；不会保存到浏览器或显示演示日志。'] as [string,string]),
  ...modules.filter(m=>m.key==='statistics').flatMap(m=>m.pages.map(p=>[p.path,'此统计页面尚未接入现平台统计口径和接口，暂不可查询；不会显示演示结果。'] as [string,string])),
  ...['finance_reports','finance_statistics'].map(key=>[`/inspection/finance/${key}`,'此财务报表尚未接入现平台统计接口，暂不可查询；不会显示演示金额。'] as [string,string]),
])
/** Availability is separate from permissions and never grants backend access. */
export function pageAvailability(path: string): Availability {
  if (unconnectedPages.has(path)) return { status:'pending',reason:unconnectedPages.get(path)! }
  if (path === '/inspection/quality/erp_content') return available
  if (['/profile','/profile/edit','/change-password'].includes(path) || /^\/dashboard\/(analyst|reviewer|approver|admin|general)$/.test(path)) return available
  if (originalPages.has(path)) return available
  if (path === '/reports/check' || path.startsWith('/reports/check/')) return removedReportCheck
  if (['/', '/dashboard', '/work', '/identity', '/platform-availability'].includes(path) || connectedLists.has(path)) return available
  if (/^\/commissions\/(registration|review|query)\/commissions\/(\d+|new)(\/edit)?$/.test(path)) return available
  return pending
}
export function navigationAvailability(item: {to: string; children?: {to: string; children?: any[]}[]}): Availability {
  if (item.children?.length && item.children.some(child => navigationAvailability(child).status === 'available')) return available
  return pageAvailability(item.to)
}
export function preventUnavailableNavigation(event: Event, path: string) {
  if (pageAvailability(path).status !== 'available') { event.preventDefault(); event.stopImmediatePropagation() }
}
