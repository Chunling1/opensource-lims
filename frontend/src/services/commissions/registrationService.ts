import { contractReviewStage } from '../../types/commissions/workflow'
import type { Actor } from '../../types/lims'
import type { RegistrationKind, RegistrationWorkspace, SampleReviewStatus } from '../../types/commissions/registration'

export const registrationRoot = '/commissions/registration'
export const reviewRoot = '/commissions/review'
export const queryRoot = '/commissions/query'
export const changesRoot = '/commissions/changes'
export function registrationContext(path: string) {
  const inbound = path === '/samples/inbound' || path.startsWith('/samples/inbound/')
  const outbound = path === '/samples/outbound' || path.startsWith('/samples/outbound/')
  const disposal = path === '/samples/disposal' || path.startsWith('/samples/disposal/')
  const changing = path === changesRoot || path.startsWith(`${changesRoot}/`)
  const inquiry = inbound || outbound || disposal || path === queryRoot || path.startsWith(`${queryRoot}/`)
  const review = path === reviewRoot || path.startsWith(`${reviewRoot}/`)
  return { root: disposal ? '/samples/disposal' : outbound ? '/samples/outbound' : inbound ? '/samples/inbound' : changing ? changesRoot : inquiry ? queryRoot : review ? reviewRoot : registrationRoot, title: disposal ? '样品处置' : outbound ? '样品出库' : inbound ? '样品入库' : changing ? '委托更改' : inquiry ? '委托查询' : review ? '合同评审' : '委托登记', workspace: (changing ? 'changes' : inquiry ? 'query' : review ? 'review' : 'registration') as RegistrationWorkspace, review, inquiry, changing }
}
export const demoCustomers = ['华清环境检测中心', '远景建设集团', '清源食品有限公司']
export const demoProjects = ['pH 值', '化学需氧量', '重金属', '微生物', '抗压强度']
export const demoCategories = ['委托', '委托（有见证送检）', '抽样', '校准']
export const sampleReadOnlyReason = (status: string) => status === 'void_pending' ? '作废申请中的样品仅可查看' : status === 'voided' ? '已作废样品仅可查看' : undefined
export const commissionStates = ['未完成', '已完成']
const has = (actor: Actor, roles: string[]) => actor.roles.includes('admin') || roles.some(r => actor.roles.includes(r))
export const registrationCanWrite = (actor: Actor, kind: RegistrationKind) => has(actor, kind === 'commissions' ? ['commissions'] : ['samples', 'commissions'])
export const registrationCanLink = (actor: Actor) => has(actor, ['samples']) && registrationCanWrite(actor, 'samples')
export const registrationCanReadSamples = (actor: Actor) => has(actor, ['samples', 'commissions', 'testing', 'reviewer', 'approver', 'reports'])
export const registrationCanEdit = (actor: Actor, kind: RegistrationKind, status: string) => registrationCanWrite(actor, kind) && (kind === 'commissions' ? status === '未完成' : status === 'pending')
export const registrationCanAddSample = (actor: Actor, status: string) => registrationCanLink(actor) && status === '未完成'
export function registrationActions(actor: Actor, kind: RegistrationKind, status: string) {
  if (!registrationCanWrite(actor, kind)) return []
  if (kind === 'commissions') return status === '未完成' ? [{ id: 'complete', label: '完成', reason: false }] : status === '已完成' ? [{ id: 'uncomplete', label: '取消完成', reason: false }] : []
  return status === 'pending' ? [{ id: 'complete', label: '完成', reason: false }, { id: 'void', label: '作废', reason: true }] : status === 'completed' ? [{ id: 'uncomplete', label: '取消完成', reason: false }, { id: 'void', label: '作废', reason: true }] : []
}
export function registrationReturn(value: unknown, fallback: string = registrationRoot) {
  if (typeof value !== 'string' || !/^\/(?:commissions\/(registration|review|query|changes)|samples\/(inbound|outbound|disposal))(?:\?|$)/.test(value) || /[\\\r\n#]/.test(value)) return fallback
  return value
}

export interface WorkflowRecord { status: string; dataStatus?: string; reviewStatus?: SampleReviewStatus }
export interface WorkflowAction { id: string; label: string; reason: boolean; disabled?: boolean; disabledReason?: string }
export function workspaceCanEdit(actor: Actor, kind: RegistrationKind, row: WorkflowRecord, workspace: RegistrationWorkspace = 'registration') {
  if (workspace === 'changes') return kind === 'samples' && row.dataStatus === '委托更改中' && !sampleReadOnlyReason(row.status) && registrationCanWrite(actor, kind)
  if (kind === 'samples' && row.dataStatus === '委托更改中') return false
  if (workspace === 'query') return false
  if (kind === 'commissions') return registrationCanEdit(actor, kind, row.status)
  if ((row.reviewStatus === 'reviewed' || row.reviewStatus === 'approved')) return false
  return workspace === 'review' ? registrationCanWrite(actor, kind) && ['pending', 'completed'].includes(row.status) : registrationCanEdit(actor, kind, row.status)
}
export function workspaceActions(actor: Actor, kind: RegistrationKind, row: WorkflowRecord, workspace: RegistrationWorkspace = 'registration'): WorkflowAction[] {
  if (workspace === 'changes') return workspaceCanEdit(actor, kind, row, workspace) ? [{ id: 'complete-change', label: '完成', reason: false }] : []
  if (kind === 'samples' && row.dataStatus === '委托更改中') return []
  if (workspace === 'query') return []
  if (workspace !== 'review' || kind === 'commissions') return registrationActions(actor, kind, row.status).map(action => ({ ...action, ...(kind === 'samples' && action.id === 'uncomplete' && (row.reviewStatus === 'reviewed' || row.reviewStatus === 'approved') ? { disabled: true, disabledReason: '请先撤销评审再取消完成' } : {}) }))
  if (!registrationCanWrite(actor, kind) || sampleReadOnlyReason(row.status)) return []
  const reviewed = (row.reviewStatus === 'reviewed' || row.reviewStatus === 'approved')
  const laterStage = !contractReviewStage(row.dataStatus)
  return [
    { id: 'review', label: '开始评审', reason: false, disabled: laterStage || row.reviewStatus === 'approved', disabledReason: laterStage ? '已进入后续环节，请通过更改流程处理' : row.reviewStatus === 'approved' ? '评审已完成' : undefined },
    { id: 'unreview', label: '撤销评审', reason: false, disabled: laterStage || !reviewed, disabledReason: laterStage ? '已进入后续环节，请通过更改流程处理' : !reviewed ? '尚未开始评审' : undefined },
    { id: 'void', label: '作废', reason: true },
  ]
}
