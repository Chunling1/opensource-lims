import { describe, expect, it } from 'vitest'
import { createCustomerProjects } from '../../server/customerProjects'
import { emptyProject, projectFields } from '../../src/types/customers/projects'
import { demoActors } from '../../src/services/storage/demoActors'
import { registrationCsv } from '../../server/registrationDomain'
import type { RegistrationState } from '../../src/types/commissions/registration'
function setup() {
  let state: RegistrationState = { commissions: [], samples: [] }, actor = demoActors[0]!
  const service = createCustomerProjects({ actor: () => actor, read: () => state, write: value => { state = value } })
  return { service, state: () => state, actor: (id: string) => { actor = demoActors.find(row => row.id === id)! } }
}
describe('customer projects', () => {
  it('generates immutable codes without reuse after deletion and copies fields into independent records', () => {
    const { service } = setup(), first = service.save({ ...emptyProject(), name: '原工程', customer: '自填单位', witness: '见证甲' })
    const copy = service.save({ ...emptyProject(), name: first.name, customer: first.customer, witness: first.witness })
    expect(copy.code).not.toBe(first.code)
    expect(service.save({ ...copy, name: '副本修改', code: '伪造' }).code).toBe(copy.code)
    expect(service.detail(first.id).name).toBe('原工程')
    service.remove({ id: copy.id })
    expect(service.save({ ...emptyProject(), name: '第三工程' }).code).not.toBe(copy.code)
    expect(service.options().organizations).toContain('自填单位')
  })
  it('updates only specified batch fields atomically, supports clearing and rejects identity changes', () => {
    const { service, state } = setup()
    const a = service.save({ ...emptyProject(), name: '工程甲', builder: '施工甲', manager: '经理甲' }), b = service.save({ ...emptyProject(), name: '工程乙', builder: '施工乙' })
    service.batch({ ids: [a.id, b.id], changes: { builder: '共同施工', manager: '' } })
    expect(service.detail(a.id)).toMatchObject({ name: '工程甲', builder: '共同施工', manager: '' })
    expect(service.detail(b.id)).toMatchObject({ name: '工程乙', builder: '共同施工' })
    const before = JSON.stringify(state())
    for (const input of [{ ids: [a.id, 'missing'], changes: { builder: '不应写入' } }, { ids: [a.id, b.id], changes: { name: '' } }, { ids: [a.id], changes: { code: '伪造' } }, { ids: [a.id, a.id], changes: { name: '重复' } }]) expect(() => service.batch(input)).toThrow()
    expect(JSON.stringify(state())).toBe(before)
  })
  it('imports all rows atomically, validates enums and numbers, exports scoped matching or selected rows', () => {
    const { service } = setup(), header = projectFields.map(field => field.label)
    const line = (name: string, area = '100.25') => { const draft = { ...emptyProject(), name, buildingArea: area, projectType: '建筑', structure: '剪力墙结构', samplingPlace: '地点,一' }; return projectFields.map(field => draft[field.key as keyof typeof draft] || '') }
    expect(() => service.importCsv(registrationCsv([header, line('甲'), line('乙', '-1')]))).toThrow(/第 3 行/)
    expect(service.query({}).total).toBe(0)
    expect(service.importCsv(registrationCsv([header, line('甲'), line('乙')])).count).toBe(2)
    expect(service.export({ name: '甲' })).not.toContain('乙')
    expect(service.export({ ids: [] })).not.toContain('地点,一')
    expect(service.export({})).toContain('"地点,一"')
    for (const invalid of [{ name: '' }, { name: '甲', floors: '1.5' }, { name: '甲', structure: '未知' }]) expect(() => service.save({ ...emptyProject(), ...invalid })).toThrow()
  })
  it('enforces department scope and mutation permissions across endpoints', () => {
    const ctx = setup(), row = ctx.service.save({ ...emptyProject(), name: '本部门' })
    ctx.state().customerProjects!.push({ ...row, id: 'foreign', code: 'GC999999', departmentId: 'lab2', name: '外部门', customer: '外部专属单位' })
    ctx.actor('business')
    expect(ctx.service.query({}).total).toBe(1)
    expect(ctx.service.export({ ids: [row.id, 'foreign'] })).not.toContain('外部门')
    expect(ctx.service.options().organizations).not.toContain('外部专属单位')
    expect(() => ctx.service.batch({ ids: [row.id, 'foreign'], changes: { manager: '越权' } })).toThrow()
    expect(ctx.service.detail(row.id).manager).toBe('')
    ctx.actor('analyst')
    expect(ctx.service.detail(row.id).name).toBe('本部门')
    expect(() => ctx.service.save({ ...row, name: '越权' })).toThrow()
    expect(() => ctx.service.remove({ id: row.id })).toThrow()
    expect(() => ctx.service.importCsv(ctx.service.template())).toThrow()
  })
})
