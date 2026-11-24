import { describe, expect, it } from 'vitest'
import { createTestEnvironments, seedTestEnvironments } from '../../server/testEnvironments'
import type { RegistrationState } from '../../src/types/commissions/registration'
import type { Actor } from '../../src/types/lims'
function setup() {
  let user: Actor = { id: 'admin', name: '管理员', roles: ['admin'], departmentId: 'lab', scope: 'all' }
  let state: RegistrationState = { commissions: [], samples: [] }
  const service = createTestEnvironments({ actor: () => user, read: () => state, write: next => { state = next } })
  return { service, state: () => state, actor: (next: Partial<Actor>) => { user = { ...user, ...next } } }
}
describe('test environments', () => {
  it('saves independent descriptions and plan associations with optimistic concurrency', () => {
    const t = setup(), first = t.service.save({ name: ' 恒温环境 ', planIds: ['thermal-1', 'general-1'], departmentId: 'lab2' })
    expect(first).toMatchObject({ name: '恒温环境', departmentId: 'lab', version: 1 })
    expect(first.plans.map(row => row.code)).toEqual(['RS', 'CG'])
    expect(() => t.service.save({ name: '恒温环境', planIds: [] })).toThrow('相同')
    expect(() => t.service.save({ name: ' ', planIds: [] })).toThrow('描述')
    const second = t.service.save({ ...first, name: '新的环境', planIds: ['general-1'] })
    expect(second.version).toBe(2)
    expect(t.service.save({ ...first, name: '后提交覆盖' })).toMatchObject({ name: '后提交覆盖', version: 3 })
    expect(t.service.detail(first.id).planIds).toEqual(first.planIds)
    t.service.remove({ id: first.id, version: 1 })
    expect(t.service.query({}).total).toBe(0)
    expect(t.service.options().some(plan => plan.id === 'general-1')).toBe(true)
  })
  it('rejects invalid plans atomically and permits an empty association list', () => {
    const t = setup(), row = t.service.save({ name: '没有关联的环境', planIds: [] })
    const before = structuredClone(t.state())
    expect(() => t.service.save({ ...row, planIds: ['thermal-1', 'missing'] })).toThrow('权限范围')
    expect(() => t.service.save({ ...row, planIds: ['thermal-1', 'thermal-1'] })).toThrow('选择有误')
    expect(t.state()).toEqual(before)
  })
  it('enforces department visibility and readonly roles including plan options', () => {
    const t = setup(), row = t.service.save({ name: '实验室环境', planIds: ['thermal-1'] })
    t.actor({ departmentId: 'lab2', scope: 'department' })
    expect(t.service.query({}).total).toBe(0)
    expect(t.service.export({})).not.toContain(row.name)
    expect(t.service.options().map(row => row.id)).toEqual(['branch-1'])
    expect(() => t.service.detail(row.id)).toThrow('无权')
    expect(() => t.service.save({ ...row })).toThrow('无权')
    expect(() => t.service.remove({ ...row })).toThrow('无权')
    expect(() => t.service.save({ name: '越权关联', planIds: ['thermal-1'] })).toThrow('权限范围')
    t.service.save({ name: '第二部门环境', planIds: ['branch-1'] })
    t.actor({ roles: ['quality', 'reviewer'] })
    expect(t.service.query({}).total).toBe(1)
    expect(() => t.service.save({ name: '只读新增', planIds: [] })).toThrow('无权')
    t.actor({ roles: ['testing'] })
    expect(() => t.service.options()).toThrow('无权')
  })
  it('retains but conceals associations outside a scoped editor’s department', () => {
    const t = setup(), row = t.service.save({ name: '跨科室方案环境', planIds: ['thermal-1', 'branch-1'] })
    t.actor({ scope: 'department', roles: ['quality'] })
    expect(t.service.detail(row.id).plans[1]).toMatchObject({ name: '无权访问的检测方案', code: '—' })
    expect(() => t.service.save({ ...row, planIds: ['thermal-1'] })).toThrow('权限范围')
    expect(t.service.save({ ...row, name: '改名', planIds: row.planIds }).planIds).toEqual(row.planIds)
  })
  it('filters, paginates, exports selected records and does not reseed deleted examples', () => {
    const t = setup()
    for (let i = 0; i < 12; i++) t.service.save({ name: `环境${i}`, planIds: [] })
    expect(t.service.query({ page: 2, pageSize: 10 }).items).toHaveLength(2)
    expect(t.service.query({ name: '环境1' }).total).toBe(3)
    const row = t.service.query({}).items[0]!
    expect(t.service.export({ ids: [row.id] })).toContain('"环境0"')
    expect(t.service.export({ ids: [row.id] })).not.toContain('"环境1"')
    expect(() => t.service.query({ pageSize: 7 })).toThrow('分页')
    const state: RegistrationState = { commissions: [], samples: [] }
    seedTestEnvironments(state); expect(state.testEnvironments).toHaveLength(3)
    state.testEnvironments = []; seedTestEnvironments(state); expect(state.testEnvironments).toHaveLength(0)
  })
})
