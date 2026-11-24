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
  const deps = { actor: () => actor, read: () => state, write: (value: typeof state) => { state = value } }
  return { state, service: createReportLifecycleService(deps, createDemoSigningProvider('test')), registration: createRegistrationService(deps), restrict: () => { actor = { ...actor, scope: 'department', departmentId: 'lab2' } } }
}
describe('report signing list', () => {
  it('uses signing facts and actions while excluding paper and inactive reports', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-94')!
    const row = t.service.signingList({ signingStatus: '签章失败' }).items[0]!
    expect(row).toMatchObject({ id: source.id, form: '电子', dataStatus: '报告签章中', signingStatus: '签章失败', signingDate: '' })
    expect(row.actions.map(action => action.label)).toEqual(['预览', '查看签章进度', '重试签章', '下载报告', '查看附件'])
    expect(row.actions.find(action => action.id === 'retry')?.enabled).toBe(true)
    expect(row.actions.find(action => action.id === 'download')?.enabled).toBe(false)
    expect(t.service.signingList({}).items.every(row => row.form === '电子')).toBe(true)
    const release = source.reportRelease!
    release.signing!.status = '签章完成'; release.signing!.signature = '已完成'; release.signing!.seal = '已完成'
    release.signing!.updatedAt = '2026-10-01T17:00:00Z'; release.signed = structuredClone(release.original)
    const complete = t.service.signingList({ ids: [source.id], status: '报告签章完成', signingStatus: '签章完成' }).items[0]!
    expect(complete).toMatchObject({ signingDate: '2026-10-02', signatureStatus: '已完成', sealStatus: '已完成' })
    expect(complete.actions.find(action => action.id === 'download')?.enabled).toBe(true)
    expect(complete.actions.find(action => action.id === 'retry')?.enabled).toBe(false)
    for (const state of ['void_pending', 'voided'] as const) { source.status = state; expect(t.service.signingList({ ids: [source.id] }).total).toBe(0) }
    source.status = 'completed'; source.dataStatus = '检测更改中'
    expect(t.service.signingList({ ids: [source.id] }).total).toBe(0)
    source.dataStatus = '报告批准完成'; release.supersededAt = new Date().toISOString()
    expect(t.service.signingList({ ids: [source.id] }).total).toBe(0)
  })
  it('filters before pagination and export and scopes the plan tree to electronic reports', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-94')!
    source.reportRelease!.approvedAt = '2026-10-01T17:00:00Z'
    t.state.samples = Array.from({ length: 14 }, (_, i) => ({ ...structuredClone(source), id: `sign-${i}`, code: `SIGN${String(i).padStart(2, '0')}`, customer: i < 12 ? '查询单位' : '其他单位', assignmentInfo: { ...source.assignmentInfo, conclusion: '合格' } }))
    const query = { searchField: 'customer', contains: '查询单位', signingStatus: '签章失败', dateField: 'approvalDate', from: '2026-10-02', to: '2026-10-02', conclusion: '合格', sampleType: source.sampleType, plans: { groupIds: [], planIds: [source.details!.testPlanId], excludedPlanIds: [] }, page: 2, pageSize: 10 }
    expect(t.service.signingList(query)).toMatchObject({ total: 12, page: 2 })
    expect(t.service.signingList(query).items).toHaveLength(2)
    expect(t.service.signingList(query, true).items).toHaveLength(12)
    expect(t.service.signingList({ ...query, ids: ['sign-0'] }, true).items.map(row => row.id)).toEqual(['sign-0'])
    expect(t.service.signingList({ ...query, conclusion: '不合格' }).total).toBe(0)
    expect(t.service.signingList({ ...query, from: '2026-10-01', to: '2026-10-01' }).total).toBe(0)
    expect(t.service.signingList({ ...query, signingStatus: '待确认' }).total).toBe(0)
    expect((await t.registration.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'report-signing')).populated?.total).toBe(1)
    t.restrict(); expect(t.service.signingList({}, true).items).toHaveLength(0)
  })
  it('validates signing query choices', () => {
    for (const query of [{ signingStatus: '已打印' }, { status: '报告打印中' }, { searchField: 'dataEntryPerson' }, { dateField: 'requestedTestDate' }]) expect(() => parseReportPrintQuery(query, 'signing')).toThrow()
  })
})
