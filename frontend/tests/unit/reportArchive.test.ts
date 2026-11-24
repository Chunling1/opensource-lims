import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createReportLifecycleService } from '../../server/reportLifecycle'
import { seedReportLifecycleDemo } from '../../server/reportLifecycleDemo'
import { createDemoSigningProvider } from '../../server/reportSigning'
import { demoActors } from '../../src/services/storage/demoActors'
import { parseReportPrintQuery } from '../../server/reportPrint'

async function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  await seedReportLifecycleDemo(state)
  const deps = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
  const service = createReportLifecycleService(deps, createDemoSigningProvider('test'))
  const sample = (id = 'demo-yp-95') => state.samples.find(row => row.id === id)!
  const act = (action: string, extra: Record<string, unknown> = {}, id = 'demo-yp-95') => service.action(id, { action, version: sample(id).version, releaseId: sample(id).reportRelease!.id, ...extra })
  return { service, sample, act, registration: createRegistrationService(deps), state: () => state, actor: (value: typeof actor) => { actor = value } }
}
describe('report archive', () => {
  it('lists issued paper and electronic reports with five archive actions and filters current archive facts', async () => {
    const t = await setup()
    expect(t.service.archiveList({ archiveStatus: '待归档' }).items.map(row => row.code)).toEqual(['SP2026090095', 'SP2026090096'])
    const archived = t.service.archiveList({ archiveStatus: '已归档' }).items[0]!
    expect(archived).toMatchObject({ code: 'SP2026090097', archivePerson: '演示用户' })
    expect(archived.archiveDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(archived.actions.map(action => action.label)).toEqual(['归档', '撤销归档', '打印报告', '打印任务单', '打印委托书'])
    expect(archived.actions.find(action => action.id === 'archive')?.enabled).toBe(false)
    for (const query of [{ archiveStatus: '报告打印中' }, { status: '报告打印中' }, { dateField: 'printDate' }, { dateField: 'testStartDate' }, { dateField: 'testEndDate' }]) expect(() => parseReportPrintQuery(query, 'archive')).toThrow()
    for (const dateField of ['approvalDate', 'archiveDate', 'commissionDate']) expect(parseReportPrintQuery({ dateField }, 'archive').dateField).toBe(dateField)
    const plan = t.sample().details!.testPlanId
    const nodes = await t.registration.testPlans({ keyword: t.sample().details!.testPlan })
    expect(nodes.items.find(row => row.id === plan)?.reportArchiveSampleCount).toBeGreaterThan(0)
    expect(t.service.archiveList({ plans: { groupIds: [], planIds: [plan], excludedPlanIds: [] } }).total).toBe(3)
  })
  it('records the server actor and chosen date, preserves report files and reversal history, and rejects stale writes', async () => {
    const t = await setup(), before = structuredClone(t.sample().reportRelease!), version = t.sample().version
    expect(() => t.act('archive', { date: '2026-02-30' })).toThrow()
    t.act('archive', { date: '2026-10-01', actorName: '伪造归档人' })
    expect(t.sample().reportRelease).toMatchObject({ archiveStatus: '已归档', distributionStatus: '已发放', archive: { actorId: 'admin', actorName: '演示用户', date: '2026-10-01' } })
    expect(t.sample().reportRelease!.original).toEqual(before.original)
    const archiveQuery = { ids: [t.sample().id, 'demo-yp-96'], dateField: 'archiveDate', from: '2026-10-01', to: '2026-10-01' }
    expect(t.service.archiveList(archiveQuery).items.map(row => row.id)).toEqual([t.sample().id])
    expect(t.service.archiveList(archiveQuery, true).total).toBe(1)
    expect(t.service.archiveList({ ...archiveQuery, from: '2026-10-02', to: '2026-10-03' }).total).toBe(0)
    expect(t.service.archiveList({ ...archiveQuery, from: '2026-09-29', to: '2026-09-30' }).total).toBe(0)
    expect(() => t.act('archive', { date: '2026-10-02', version })).toThrow('状态')
    expect(() => t.act('undo-distribute', { reason: '误发放' })).toThrow()
    t.act('undo-archive')
    expect(t.service.archiveList(archiveQuery).total).toBe(0)
    expect(t.service.archiveList({ ids: [t.sample().id] }).items[0]).toMatchObject({ archiveStatus: '待归档', archiveDate: '', archivePerson: '' })
    expect(t.sample().reportRelease!.history.at(-1)?.reason).toContain('2026-10-01')
    t.act('undo-distribute', { reason: '更正登记' })
    expect(t.service.archiveList({ ids: [t.sample().id] }).total).toBe(0)
    expect(() => t.act('archive', { date: '2026-10-02' })).toThrow()
  })
  it('uses the signed electronic file for archival printing without changing print or archive state', async () => {
    const t = await setup(), sample = t.sample('demo-yp-96'), before = structuredClone(sample.reportRelease!)
    expect(t.service.file(sample.id, before.id, 'print-report')).toEqual(before.signed)
    expect(sample.reportRelease).toEqual(before)
    expect(() => t.service.file(sample.id, before.id, 'print')).toThrow()
    t.act('archive', { date: '2026-10-02' }, sample.id)
    expect(t.sample(sample.id).reportRelease).toMatchObject({ printStatus: '不适用', archiveStatus: '已归档' })
    t.actor({ ...demoActors[3]!, roles: ['reports'] })
    expect((await t.registration.taskPrintSource(sample.id)).canPrint).toBe(true)
    expect((await t.registration.printSource('samples', sample.id)).canPrint).toBe(true)
    await expect(t.registration.taskPrintSource('demo-yp-91')).rejects.toThrow()
    t.actor(demoActors.find(actor => actor.id === 'finance')!)
    expect(() => t.act('archive', { date: '2026-10-02' })).toThrow()
    t.actor({ ...demoActors[0]!, scope: 'department', departmentId: 'lab2' })
    expect(t.service.archiveList({}).total).toBe(0)
    expect(() => t.act('archive', { date: '2026-10-02' })).toThrow()
  })
  it('filters before pagination and export and removes voided or superseded versions', async () => {
    const t = await setup(), source = t.sample()
    t.state().samples = Array.from({ length: 12 }, (_, index) => ({ ...structuredClone(source), id: `archive-${index}`, code: `AR${index}`, customer: '归档查询单位' }))
    const query = { searchField: 'customer', contains: '归档查询', archiveStatus: '待归档', page: 2, pageSize: 10 }
    expect(t.service.archiveList(query)).toMatchObject({ total: 12, page: 2 })
    expect(t.service.archiveList(query).items).toHaveLength(2)
    expect(t.service.archiveList(query, true).items).toHaveLength(12)
    t.state().samples[0]!.status = 'void_pending'
    t.state().samples[1]!.reportRelease!.supersededAt = new Date().toISOString()
    expect(t.service.archiveList(query)).toMatchObject({ total: 10, page: 1 })
  })
})
