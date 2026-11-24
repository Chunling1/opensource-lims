import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { seedReportLifecycleDemo } from '../../server/reportLifecycleDemo'
import { demoActors } from '../../src/services/storage/demoActors'
import { parseReportQuery } from '../../server/reportQuery'
import { reportQueryColumns, reportQueryStates, reportQueryDateFields } from '../../src/types/reports/reportQuery'
import { reportDistributionStates } from '../../src/types/reports/reportDistribution'

async function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  await seedReportLifecycleDemo(state)
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { state = next } })
  return { service, state: () => state, sample: (id = 'demo-yp-96') => state.samples.find(row => row.id === id)!, actor: (next: typeof actor) => { actor = next } }
}
describe('report query', () => {
  it('joins saved lifecycle facts and leaves unsupported business fields unknown', async () => {
    const t = await setup(), sample = t.sample()
    sample.commissionInfo.erpContract = 'KD-PROJECT'; sample.erpContractNumber = 'KD-CONTRACT'; sample.contractType = '检测合同'; sample.reportPrintCount = 2
    const rows = await t.service.reportQuerySamples({ ids: [sample.id, 'demo-yp-91', 'demo-yp-97'] })
    const row = rows.items.find(row => row.id === sample.id)!
    expect(row).toMatchObject({ dataStatus: '报告发放完成', pendingStatus: '报告归档中', recipient: '演示领取人', distributionPerson: '演示用户', erpProjectNumber: 'KD-PROJECT', erpContractNumber: 'KD-CONTRACT', contractType: '检测合同', printCount: 2 })
    expect(rows.items.find(row => row.id === 'demo-yp-97')).toMatchObject({ dataStatus: '报告归档完成', archiver: '演示用户', pendingStatus: '' })
    expect(rows.items.find(row => row.id === 'demo-yp-91')).toMatchObject({ erpContractNumber: '', contractType: '', printCount: null, dataStatus: '报告打印中' })
    expect(reportQueryColumns).toHaveLength(53)
    expect(new Set(reportQueryColumns.map(row => row.key)).size).toBe(53)
    expect(await t.service.reportQueryFile(sample.id, sample.reportRelease!.id)).toEqual(sample.reportRelease!.signed)
    await expect(t.service.reportQueryFile(sample.id, 'stale')).rejects.toThrow('版本')
  })
  it('filters before pagination/export, preserves inactive rows and scopes plan counts', async () => {
    const t = await setup(), source = structuredClone(t.sample())
    t.state().samples = Array.from({ length: 12 }, (_, i) => ({ ...structuredClone(source), id: `query-${i}`, code: `RQ${i}`, customer: '报告查询单位' }))
    t.state().samples[0]!.status = 'voided'
    const query = { searchField: 'customer' as const, contains: '报告查询', page: 2, pageSize: 10 }
    expect(await t.service.reportQuerySamples(query)).toMatchObject({ total: 12, page: 2 })
    expect((await t.service.reportQuerySamples(query)).items).toHaveLength(2)
    const csv = await t.service.exportReportQuerySamples(query)
    for (let i = 0; i < 12; i++) expect(csv).toContain(`"RQ${i}"`)
    expect((await t.service.reportQuerySamples({ status: '委托已作废' })).items[0]).toMatchObject({ code: 'RQ0', canVoid: false })
    expect((await t.service.reportQuerySamples({ ids: ['query-1'], dateField: 'approvalDate', from: '2000-01-01', to: '2000-01-02' })).total).toBe(0)
    const approvalDate = new Date(source.reportRelease!.approvedAt).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
    const dates = { ids: ['query-1'], dateField: 'approvalDate' as const, from: approvalDate, to: approvalDate }
    expect((await t.service.reportQuerySamples(dates)).total).toBe(1)
    const nodes = await t.service.testPlans({ keyword: source.details!.testPlan })
    expect(nodes.items.find(row => row.id === source.details!.testPlanId)?.reportQuerySampleCount).toBe(12)
    for (const input of [{ status: 'unknown' }, { dateField: 'issueDate' }, { dateField: 'distributionDate' }, { searchField: 'recipient' }]) expect(() => parseReportQuery(input)).toThrow()
  })
  it('shares distribution statuses and filters check and review dates inclusively for lists and exports', async () => {
    expect(reportQueryStates).toBe(reportDistributionStates)
    expect(reportQueryDateFields.map(field => field.label)).toEqual(['委托日期', '试验开始日期', '试验结束日期', '校核日期', '审核日期', '批准日期', '归档日期', '打印日期'])
    const t = await setup(), sample = t.sample()
    sample.reportCheckInfo = { actorId: 'reviewer', actorName: '校核人', date: '2026-09-20', at: '2026-09-21T00:00:00Z' }
    sample.reportReviewInfo = { actorId: 'reviewer', actorName: '审核人', date: '2026-09-22', at: '2026-09-23T00:00:00Z' }
    for (const [dateField, value] of [['checkDate', '2026-09-20'], ['auditDate', '2026-09-22']] as const) {
      const query = { ids: [sample.id], dateField, from: value, to: value }
      expect((await t.service.reportQuerySamples(query)).items.map(row => row.id)).toEqual([sample.id])
      expect(await t.service.exportReportQuerySamples(query)).toContain(sample.code)
      expect((await t.service.reportQuerySamples({ ...query, from: '2026-09-24', to: '2026-09-25' })).total).toBe(0)
      expect((await t.service.reportQuerySamples({ ...query, from: '2026-09-18', to: '2026-09-19' })).total).toBe(0)
    }
    delete sample.reportCheckInfo; delete sample.reportReviewInfo
    sample.workflow = {}
    expect((await t.service.reportQuerySamples({ ids: [sample.id], dateField: 'checkDate', from: '2026-09-01' })).total).toBe(0)
    expect((await t.service.reportQuerySamples({ ids: [sample.id], dateField: 'auditDate', to: '2026-10-01' })).total).toBe(0)
  })
  it('reuses void requests with actor, version and scope checks without losing files or receipt history', async () => {
    const t = await setup(), source = t.sample(), release = structuredClone(source.reportRelease!)
    await expect(t.service.reportQueryVoid(source.id, source.version, '')).rejects.toThrow()
    await t.service.reportQueryVoid(source.id, source.version, '客户申请作废')
    expect(t.sample()).toMatchObject({ status: 'void_pending', voidApplication: { reason: '客户申请作废', appliedBy: { id: 'admin' } } })
    expect(t.sample().reportRelease).toEqual(release)
    const row = (await t.service.reportQuerySamples({ ids: [source.id] })).items[0]!
    expect(row).toMatchObject({ dataStatus: '委托作废申请中', canVoid: false })
    await expect(t.service.reportQueryVoid(source.id, source.version, '重复申请')).rejects.toThrow()
    expect(await t.service.reportQueryFile(source.id, release.id)).toEqual(release.signed)
    t.actor(demoActors.find(actor => actor.id === 'finance')!)
    await expect(t.service.reportQuerySamples({})).rejects.toThrow()
    t.actor({ ...demoActors[3]!, scope: 'department', departmentId: 'lab2' })
    expect((await t.service.reportQuerySamples({ ids: [source.id] })).total).toBe(0)
    await expect(t.service.reportQueryFile(source.id, release.id)).rejects.toThrow()
  })
})
