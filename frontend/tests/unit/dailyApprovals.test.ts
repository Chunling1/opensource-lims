import { describe, it, expect } from 'vitest'
import { createDailyRequests } from '../../server/dailyRequests'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let actor: Actor = { id: 'business', name: '申请人', roles: ['commissions'], departmentId: 'lab', scope: 'department' }
  const deps = { actor: () => actor, read: () => state, write: (next: RegistrationState) => { state = next } }
  const requests = createDailyRequests(deps), approvals = createDailyRequests(deps, true)
  const draft = requests.save({ reason: '用印', items: ['加盖检测合同章'], copies: 1, files: [], intent: 'save' })
  const submitted = requests.save({ ...draft, intent: 'submit' })
  return { requests, approvals, submitted, state: () => state, actor: (value: Partial<Actor>) => { actor = { ...actor, ...value } } }
}
describe('daily approvals', () => {
  it('approves, revokes to pending and voids with immutable history and server identity', () => {
    const t = setup(); t.actor({ id: 'approver', name: '审批员', roles: ['approver'] })
    let row = t.approvals.approve({ ...t.submitted, result: '审批通过', opinion: '', actorId: 'fake' }, 'approve')
    expect(row).toMatchObject({ status: '审批通过', canApprove: false, canRevoke: true, approval: { actorId: 'approver', actor: '审批员', opinion: '' } })
    expect(row.approval!.at).toBeTruthy()
    expect(() => t.approvals.approve({ ...row, opinion: '' }, 'revoke')).toThrow('撤回原因')
    row = t.approvals.approve({ ...row, opinion: '复核资料' }, 'revoke')
    expect(row).toMatchObject({ status: '待审批', canApprove: true, withdrawalReason: '复核资料' })
    expect(row.approval).toBeUndefined()
    row = t.approvals.approve({ ...row, result: '审批通过', opinion: '核实通过' }, 'approve')
    expect(() => t.approvals.approve({ ...row, opinion: '' }, 'void')).toThrow('作废原因')
    row = t.approvals.approve({ ...row, opinion: '业务取消' }, 'void')
    expect(row).toMatchObject({ status: '已作废', voidReason: '业务取消', canApprove: false, canRevoke: false, canVoid: false, canEdit: false, canDelete: false })
    expect(row.events.slice(-4).map(e => e.action)).toEqual(['审批通过', '撤回审批', '审批通过', '作废申请'])
    expect(row.events.slice(-4).map(e => e.reason)).toEqual(['', '复核资料', '核实通过', '业务取消'])
    expect(() => t.approvals.approve({ ...row, opinion: '再次撤回' }, 'revoke')).toThrow('不允许')
    expect(t.approvals.export({})).toContain('已作废')
  })
  it('requires rejection opinion, allows applicant resubmission and rejects races atomically', () => {
    const t = setup(); t.actor({ id: 'admin', roles: ['admin'] })
    expect(() => t.approvals.approve({ ...t.submitted, result: '不通过', opinion: '' }, 'approve')).toThrow('审批意见')
    expect(() => t.approvals.approve({ ...t.submitted, result: '退回', opinion: '原因' }, 'approve')).toThrow('审批结果')
    expect(t.requests.detail(t.submitted.id).version).toBe(t.submitted.version)
    const rejected = t.approvals.approve({ ...t.submitted, result: '不通过', opinion: '补充资料' }, 'approve')
    t.actor({ id: 'business', roles: ['commissions'] })
    expect(t.requests.detail(rejected.id).canEdit).toBe(true)
    const resubmitted = t.requests.save({ ...rejected, reason: '补齐资料', intent: 'submit' })
    expect(resubmitted.approval).toBeUndefined()
    expect(resubmitted.events.some(e => e.action === '不通过' && e.reason === '补充资料')).toBe(true)
    t.actor({ id: 'admin', roles: ['admin'] })
    const snapshot = structuredClone(t.state())
    expect(() => t.approvals.approve({ ...rejected, opinion: '迟到撤回' }, 'revoke')).toThrow('当前状态')
    expect(t.state()).toEqual(snapshot)
    t.requests.action({ ...resubmitted, withdrawalReason: '申请人撤销' }, 'withdraw')
    expect(t.approvals.query({}).total).toBe(0)
    expect(() => t.approvals.detail(resubmitted.id)).toThrow('不存在')
  })
  it('enforces role, scope and original approver ownership for revocation', () => {
    const t = setup()
    expect(() => t.approvals.query({})).toThrow('无权')
    expect(() => t.requests.approve({ ...t.submitted, result: '审批通过' }, 'approve')).toThrow('无权')
    t.actor({ id: 'approver', roles: ['approver'], departmentId: 'lab2' })
    expect(t.approvals.query({}).total).toBe(0)
    expect(() => t.approvals.detail(t.submitted.id)).toThrow('无权')
    t.actor({ departmentId: 'lab' })
    const approved = t.approvals.approve({ ...t.submitted, result: '审批通过' }, 'approve')
    t.actor({ id: 'another-approver' })
    expect(t.approvals.detail(approved.id).canRevoke).toBe(false)
    expect(() => t.approvals.approve({ ...approved, opinion: '他人审批' }, 'revoke')).toThrow('不允许')
    t.actor({ active: false })
    expect(() => t.approvals.export({})).toThrow('无权')
  })
})
