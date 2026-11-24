import { describe, expect, it } from 'vitest'
import { createTaskProcessingService } from '../../server/taskProcessing'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { demoActors } from '../../src/services/storage/demoActors'
import type { Actor } from '../../src/types/lims'

const file = { name: '沟通记录.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }
const input = { requestId: 'request-1', account: 'analyst', name: '李检测', date: '2026-09-28', contactMethod: '电话', contactTarget: '客户甲', content: '确认检测要求', notes: '' }
function setup() {
  let state = seedRegistration(), actor: Actor = demoActors[0]!, locked = false
  const deps = { actor: () => actor, locked: () => locked, read: () => state, write: (next: typeof state) => { state = next } }
  return { service: createTaskProcessingService(deps), registration: createRegistrationService(deps), get state() { return state }, setActor(value: Actor) { actor = value }, lock() { locked = true } }
}
describe('task processing records', () => {
  it('keeps snapshots, idempotency and attachments separate from sample versions and files', async () => {
    const x = setup(), before = structuredClone(x.state), id = 'demo-yp-51'
    const record = x.service.create(id, input)
    expect(record).toMatchObject({ account: 'analyst', name: '李检测', version: 1, submittedBy: { id: 'admin', name: '演示用户' }, attachmentCount: 0 })
    expect(x.service.create(id, input).id).toBe(record.id)
    expect(x.state.taskProcessingRecords).toHaveLength(1)
    expect(() => x.service.create(id, { ...input, content: '不同内容' })).toThrow('已保存其他内容')
    const other = x.service.create(id, { ...input, requestId: 'second', content: '另一记录' })
    const attached = x.service.attachmentAction(id, record.id, { version: 1, file })
    expect(attached).toMatchObject({ version: 2, attachmentCount: 1 })
    expect(x.service.attachments(id, other.id).attachments).toEqual([])
    expect(x.service.query(id, {}).items.find(row => row.id === record.id)).not.toHaveProperty('attachments')
    expect(x.service.detail(id, record.id)).not.toHaveProperty('requestId')
    expect(x.state.samples).toEqual(before.samples); expect(x.state.commissions).toEqual(before.commissions)
    const saved = structuredClone(x.state)
    expect(() => x.service.attachmentAction(id, other.id, { version: 1 }, attached.attachments[0]!.id)).toThrow('附件不存在')
    expect(() => x.service.attachments('demo-yp-53', record.id)).toThrow('处理记录不存在')
    expect(x.state).toEqual(saved)
    const removed = x.service.attachmentAction(id, record.id, { version: 1 }, attached.attachments[0]!.id)
    expect(removed).toMatchObject({ version: 3, attachmentCount: 0 })
    expect(x.state.taskProcessingRecords![0]!.events.map(event => event.action)).toEqual(['新增处理记录', '添加附件', '删除附件'])
    await x.registration.assignmentAction(id, 1, { account: 'admin', name: '演示用户', dataEntryPerson: 'analyst', tester1: 'analyst', tester2: '', date: '2026-09-28' })
    await x.registration.assignmentAction(id, 2, {}, 'undo')
    expect(x.service.detail(id, record.id).content).toBe(input.content)
    x.state.samples.find(row => row.id === id)!.name = '后来修改名称'
    expect(x.service.detail(id, record.id).sampleName).toBe(record.sampleName)
  })
  it('validates fields and real dates without writes and bounds filters and paging', () => {
    const x = setup(), id = 'demo-yp-51', before = structuredClone(x.state)
    for (const invalid of [{ account: '' }, { name: '不匹配' }, { content: '  ' }, { date: '2026-02-30' }, { requestId: '' }, { content: '字'.repeat(501) }, { notes: '字'.repeat(501) }, { contactMethod: '字'.repeat(101) }, { contactTarget: '字'.repeat(101) }]) expect(() => x.service.create(id, { ...input, ...invalid })).toThrow()
    expect(x.state).toEqual(before)
    const first = x.service.create(id, input)
    for (const bad of [{ ...file, size: 21 * 1024 * 1024 }, { ...file, size: 2 }, { ...file, dataUrl: 'bad' }]) expect(() => x.service.attachmentAction(id, first.id, { version: 1, file: bad })).toThrow()
    expect(x.service.detail(id, first.id).version).toBe(1)
    for (let index = 0; index < 21; index++) x.service.create(id, { ...input, requestId: `page-${index}`, date: '2026-09-27' })
    expect(x.service.query(id, { handler: '检测', from: '2026-09-28', to: '2026-09-28' })).toMatchObject({ total: 1, items: [{ id: first.id }] })
    expect(x.service.query(id, { handler: 'ANALYST', pageSize: 20, page: 2 })).toMatchObject({ total: 22, page: 2, pageSize: 20 })
    expect(x.service.query(id, { pageSize: 50, page: 9 })).toMatchObject({ page: 1, total: 22 })
    for (const bad of [{ from: '2026-02-30' }, { from: '2026-09-28', to: '2026-09-27' }, { page: -1 }, { pageSize: 5 }]) expect(() => x.service.query(id, bad)).toThrow()
  })
  it('enforces read and write roles, state, department and lock on every operation', () => {
    const x = setup(), id = 'demo-yp-51', record = x.service.create(id, input)
    x.service.attachmentAction(id, record.id, { version: 1, file })
    x.setActor(demoActors.find(actor => actor.id === 'business')!)
    expect(x.service.query(id, {}).canCreate).toBe(false)
    expect(x.service.attachments(id, record.id)).toMatchObject({ canManageAttachments: false, attachmentCount: 1 })
    const before = structuredClone(x.state)
    expect(() => x.service.create(id, { ...input, requestId: 'forbidden' })).toThrow('无权')
    expect(() => x.service.attachmentAction(id, record.id, { version: 2, file })).toThrow('无权')
    expect(x.state).toEqual(before)
    x.setActor({ ...demoActors[0]!, roles: ['testing'], departmentId: 'lab2', scope: 'department' })
    expect(() => x.service.query(id, {})).toThrow('不可访问')
    expect(() => x.service.attachments(id, record.id)).toThrow('不可访问')
    x.setActor({ ...demoActors[0]!, roles: ['testing'], departmentId: 'lab', scope: 'department' })
    expect(x.service.query(id, {}).canCreate).toBe(true)
    const sample = x.state.samples.find(row => row.id === id)!
    for (const status of ['void_pending', 'voided'] as const) {
      sample.status = status
      expect(x.service.detail(id, record.id).canManageAttachments).toBe(false)
      expect(() => x.service.create(id, { ...input, requestId: status })).toThrow('状态已变化')
      expect(() => x.service.attachmentAction(id, record.id, { version: 2 }, 'any')).toThrow('状态已变化')
    }
    sample.status = 'completed'; sample.dataStatus = '检测数据录入中'
    expect(x.service.query(id, {}).canCreate).toBe(false)
    x.lock(); expect(() => x.service.detail(id, record.id)).toThrow('锁定')
  })
})
