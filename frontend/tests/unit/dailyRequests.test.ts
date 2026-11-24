import { describe, expect, it } from 'vitest'
import { randomUUID } from 'node:crypto'
import { createDailyRequests, seedDailyRequests } from '../../server/dailyRequests'
import { createAttachmentDrafts } from '../../server/attachmentDrafts'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
const draft = () => ({ reason: '业务用印', items: ['加盖检测合同章', '其他'], other: '证明文件', copies: 2, files: [] })
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  const service = createDailyRequests({ actor: () => user, read: () => state, write: next => { state = next } })
  return { service, state: () => state, actor: (next: Partial<Actor>) => { user = { ...user, ...next } } }
}
describe('daily applications', () => {
  it('saves drafts, submits, withdraws, resubmits and records the authenticated actor', () => {
    const t = setup(), saved = t.service.save({ ...draft(), applicantId: 'other', departmentId: 'lab2', appliedAt: '2000-01-01', status: '审批通过' })
    expect(saved).toMatchObject({ status: '申请中', applicantId: 'admin', departmentId: 'lab', canEdit: true, canWithdraw: false, canDelete: true })
    expect(saved.appliedAt).not.toContain('2000-01-01')
    const submitted = t.service.save({ ...saved, intent: 'submit' })
    expect(submitted).toMatchObject({ version: 2, status: '待审批', canEdit: false, canWithdraw: true, canDelete: false })
    expect(() => t.service.save({ ...submitted })).toThrow('不能直接修改')
    expect(() => t.service.action({ ...submitted }, 'delete')).toThrow('不能直接删除')
    expect(() => t.service.action({ ...submitted, withdrawalReason: '' }, 'withdraw')).toThrow('撤回原因')
    t.service.action({ ...submitted, withdrawalReason: '补充材料' }, 'withdraw')
    const withdrawn = t.service.detail(saved.id)
    expect(withdrawn).toMatchObject({ status: '申请中', withdrawalReason: '补充材料', version: 3, canEdit: true })
    const again = t.service.save({ ...withdrawn, intent: 'submit' })
    expect(again).toMatchObject({ status: '待审批', withdrawalReason: '' })
    expect(again.events.map(e => e.action)).toEqual(['新增申请', '提交申请', '撤销申请', '提交申请'])
    expect(again.events[2]!.reason).toBe('补充材料')
  })
  it('allows incomplete drafts and validates required fields only on submission', () => {
    const t = setup(), saved = t.service.save({ reason: '', items: [], other: '', copies: null })
    expect(saved.status).toBe('申请中')
    for (const [input, key] of [
      [{ ...saved, intent: 'submit' }, 'reason'],
      [{ ...saved, reason: '事由', intent: 'submit' }, 'items'],
      [{ ...saved, reason: '事由', items: ['其他'], intent: 'submit' }, 'other'],
      [{ ...saved, ...draft(), copies: 0 }, 'copies'],
      [{ ...saved, ...draft(), copies: 1.5 }, 'copies'],
      [{ ...saved, ...draft(), items: ['伪造事项'] }, 'items'],
    ] as const) expect(() => t.service.save(input)).toThrow()
    expect(t.service.detail(saved.id).version).toBe(1)
    const cleaned = t.service.save({ ...saved, ...draft(), items: ['领取中心资质'], other: '不保留隐藏内容' })
    expect(cleaned.other).toBe('')
  })
  it('rejects repeated and stale actions without modifying saved data', () => {
    const t = setup(), saved = t.service.save({ ...draft(), intent: 'submit' })
    expect(() => t.service.save({ ...saved, version: 0, intent: 'submit' })).toThrow('修改')
    t.service.action({ ...saved, withdrawalReason: '撤回' }, 'withdraw')
    const snapshot = structuredClone(t.state())
    expect(() => t.service.action({ ...saved, withdrawalReason: '重复撤回' }, 'withdraw')).toThrow('撤销')
    expect(t.state()).toEqual(snapshot)
    const current = t.service.detail(saved.id)
    t.service.action({ ...current }, 'delete')
    expect(t.service.query({}).total).toBe(0)
    expect(t.state().dailyRequests![0]!.events.at(-1)!.action).toBe('删除申请')
    expect(() => t.service.detail(saved.id)).toThrow('不存在')
    expect(t.service.save(draft()).code).not.toBe(saved.code)
  })
  it('scopes reads, exports, ownership and readonly status capabilities', () => {
    const t = setup(), saved = t.service.save(draft())
    t.actor({ id: 'quality', roles: ['quality'], scope: 'department', departmentId: 'lab' })
    expect(t.service.detail(saved.id)).toMatchObject({ canEdit: false, canDelete: false })
    expect(() => t.service.save({ ...saved })).toThrow('不能修改')
    expect(t.service.save(draft()).applicantId).toBe('quality')
    t.actor({ departmentId: 'lab2' })
    expect(t.service.query({}).total).toBe(0)
    expect(t.service.export({})).not.toContain(saved.reason)
    expect(() => t.service.detail(saved.id)).toThrow('无权')
    expect(() => t.service.query({ departmentId: 'lab' })).toThrow('无权')
    t.actor({ id: 'reviewer', roles: ['quality', 'reviewer'], scope: 'all' })
    expect(t.service.query({}).items.every(r => !r.canEdit)).toBe(true)
    expect(t.service.save(draft()).applicantId).toBe('reviewer')
    t.actor({ active: false })
    expect(() => t.service.save(draft())).toThrow('无权')
  })
  it('allows ordinary staff to apply, protects ownership and explains blocked states', () => {
    const t = setup()
    t.actor({ id: 'business', roles: ['commissions'], scope: 'department' })
    const saved = t.service.save({ ...draft(), intent: 'submit' })
    expect(saved).toMatchObject({ applicantId: 'business', canWithdraw: true })
    expect(() => t.service.save({ ...saved })).toThrow('请先撤销')
    expect(() => t.service.action({ ...saved }, 'delete')).toThrow('请先撤销')
    t.actor({ id: 'analyst', roles: ['testing'] })
    expect(() => t.service.action({ ...saved }, 'withdraw')).toThrow('不能撤销他人的申请')
    t.actor({ id: 'business' })
    for (const status of ['审批通过', '已作废'] as const) {
      t.state().dailyRequests![0]!.status = status
      expect(() => t.service.save({ ...saved })).toThrow(`当前申请为“${status}”，不能修改`)
      expect(() => t.service.action({ ...saved }, 'delete')).toThrow(`当前申请为“${status}”，不能删除`)
      expect(() => t.service.action({ ...saved }, 'withdraw')).toThrow(`当前申请为“${status}”，不能撤销`)
    }
  })
  it('filters by multi-selected matter, time, name, status and paginates full-column exports', () => {
    const t = setup()
    seedDailyRequests(t.state())
    for (let i = 0; i < 12; i++) t.service.save({ ...draft(), reason: `申请事由${i}` })
    expect(t.service.query({ item: '其他', page: 2, pageSize: 10 }).items).toHaveLength(2)
    expect(t.service.query({ reason: '事由1' }).total).toBe(3)
    expect(t.service.query({ status: '审批通过' }).items[0]).toMatchObject({ canEdit: false, canDelete: false, canWithdraw: false })
    const row = t.service.query({ reason: '事由0' }).items[0]!
    const csv = t.service.export({ ids: [row.id] })
    expect(csv).toContain('撤回原因'); expect(csv).toContain('其他：证明文件'); expect(csv).not.toContain('申请事由1')
    expect(t.service.query({ from: '2000-01-01', to: '2000-02-01' }).total).toBe(0)
    expect(() => t.service.query({ from: '2026-02-30' })).toThrow('日期')
    expect(() => t.service.query({ from: '2026-10-08', to: '2026-09-01' })).toThrow('开始日期')
  })
  it('resolves isolated temporary attachments, persists files, and rejects invalid content atomically', () => {
    const t = setup(), attachments = createAttachmentDrafts(), draftId = randomUUID()
    const file = { id: randomUUID(), name: '证明.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' }
    const ref = attachments.upload(draftId, 'admin', 'daily-request', '', file)
    const saved = t.service.save(attachments.resolve({ ...draft(), files: [ref] }, [], draftId, 'admin', 'daily-request', ''))
    expect(saved.files).toEqual([file])
    expect(() => attachments.file(draftId, 'other', 'daily-request', '', file.id)).toThrow('无权')
    expect(() => attachments.file(draftId, 'admin', 'personnel', '', file.id)).toThrow('无权')
    expect(() => t.service.save({ ...saved, files: [{ ...file, size: 4 }] })).toThrow('附件')
    expect(t.service.detail(saved.id).files).toEqual([file])
    attachments.discard(draftId, 'admin', 'daily-request', '')
    expect(() => attachments.file(draftId, 'admin', 'daily-request', '', file.id)).toThrow('失效')
    expect(t.service.detail(saved.id).files).toEqual([file])
  })
})
