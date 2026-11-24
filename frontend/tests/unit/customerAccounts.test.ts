import { describe, it, expect } from 'vitest'
import { scryptSync } from 'node:crypto'
import { createCustomerAccounts } from '../../server/customerAccounts'
import { emptyCustomerAccount } from '../../src/types/customers/accounts'
import { demoActors } from '../../src/services/storage/demoActors'
import type { RegistrationState } from '../../src/types/commissions/registration'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor = demoActors[0]!
  const service = createCustomerAccounts({ actor: () => actor, read: () => state, write: value => { state = value } })
  return { service, state: () => state, actor: (id: string) => { actor = demoActors.find(a => a.id === id)! } }
}
describe('customer accounts', () => {
  it('exports all matching pages or selected records within the current department scope', () => {
    const context = setup()
    const records = Array.from({ length: 12 }, (_, index) => context.service.save({ ...emptyCustomerAccount(), name: `导出客户${index}`, notes: '备注,带逗号' }))
    context.actor('other')
    const foreign = context.service.save.bind(context.service)
    expect(() => foreign({ ...emptyCustomerAccount(), name: '越权新增' })).toThrow()
    context.actor('admin')
    context.state().customerAccounts!.push({ ...records[0]!, id: 'other-account', code: 'KH999999', name: '外部门客户', departmentId: 'lab2' })
    context.actor('business')
    expect(context.service.query({ pageSize: 10 }).items).toHaveLength(10)
    const csv = context.service.export({ page: 2, pageSize: 10, name: '导出客户' })
    expect(csv).toContain('导出客户11')
    expect(csv).toContain('导出客户0')
    expect(csv).toContain('"备注,带逗号"')
    expect(csv).not.toContain('外部门客户')
    const selected = context.service.export({ ids: [records[0]!.id, 'other-account'] })
    expect(selected).toContain('导出客户0')
    expect(selected).not.toContain('导出客户1')
    expect(selected).not.toContain('外部门客户')
    expect(context.service.export({ ids: [] })).not.toContain('导出客户')
    expect(() => context.service.export({ ids: 'invalid' })).toThrow()
  })
  it('generates immutable account codes and atomically saves contract relationships', () => {
    const { service, state } = setup(), draft = { ...emptyCustomerAccount(), name: '测试客户', contractIds: ['contract-1'] }
    const first = service.save(draft), second = service.save({ ...draft, name: '第二客户', contractIds: [] })
    expect(first.code).not.toBe(second.code)
    expect(first.contracts[0]?.id).toBe('contract-1')
    expect(() => service.save({ ...draft, id: first.id, name: '不应写入', contractIds: ['missing'] })).toThrow()
    expect(service.detail(first.id).name).toBe('测试客户')
    expect(() => service.save({ ...draft, contractIds: ['contract-1', 'contract-1'] })).toThrow()
    const updated = service.save({ ...draft, id: first.id, code: 'forged', contractIds: [] })
    expect(updated.code).toBe(first.code)
    expect(updated.contracts).toEqual([])
    expect(state().customerAccounts).toHaveLength(2)
  })
  it('enforces scoped reads and write permission, including reset', () => {
    const context = setup(), row = context.service.save({ ...emptyCustomerAccount(), name: '受限客户' })
    context.actor('analyst')
    expect(context.service.detail(row.id).name).toBe('受限客户')
    expect(() => context.service.save({ ...row, name: '无权更改' })).toThrow()
    expect(() => context.service.resetPassword({ id: row.id })).toThrow()
    context.actor('other')
    expect(context.service.query({}).total).toBe(0)
    expect(() => context.service.detail(row.id)).toThrow()
    context.actor('business')
    expect(() => context.service.save({ ...row, contractIds: ['contract-10'] })).toThrow()
  })
  it('stores only salted credentials and invalidates the previous temporary password', () => {
    const { service, state } = setup(), row = service.save({ ...emptyCustomerAccount(), name: '密码测试' })
    const result = service.resetPassword({ id: row.id }), credential = state().customerCredentials![row.id]!
    expect(result.password.length).toBeGreaterThanOrEqual(16)
    expect(credential.hash).toBe(scryptSync(result.password, credential.salt, 64).toString('hex'))
    expect(credential.mustChangePassword).toBe(true)
    expect(JSON.stringify(state())).not.toContain(result.password)
    expect(JSON.stringify(service.detail(row.id))).not.toContain(credential.hash)
    expect(JSON.stringify(service.query({}))).not.toContain(credential.hash)
    const next = service.resetPassword({ id: row.id })
    expect(next.password).not.toBe(result.password)
    expect(state().customerCredentials![row.id]!.hash).not.toBe(credential.hash)
  })
  it('allows an administrator to associate other departments and preserves authorized existing links', () => {
    const context = setup(), row = context.service.save({ ...emptyCustomerAccount(), name: '跨部门客户', contractIds: ['contract-10'] })
    context.actor('business')
    expect(context.service.save({ ...row, notes: '更新联系信息' }).contractIds).toEqual(['contract-10'])
    expect(() => context.service.save({ ...row, contractIds: ['contract-20'] })).toThrow()
  })
  it('validates contact fields, name, pagination and filters', () => {
    const { service } = setup(), draft = { ...emptyCustomerAccount(), name: '单位' }
    expect(() => service.save({ ...draft, email: 'bad' })).toThrow()
    expect(() => service.save({ ...draft, postcode: '123' })).toThrow()
    expect(() => service.save({ ...draft, name: ' ' })).toThrow()
    service.save({ ...draft, email: 'user@example.com', postcode: '100000' })
    expect(service.query({ name: '单位' }).total).toBe(1)
    expect(service.query({ name: '无匹配' }).total).toBe(0)
    expect(() => service.query({ pageSize: 100 })).toThrow()
  })
})
