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
  return { get state() { return state }, service: createReportLifecycleService(deps, createDemoSigningProvider('test')), registration: createRegistrationService(deps), restrict: () => { actor = { ...actor, scope: 'department', departmentId: 'lab2' } } }
}
describe('report distribution list', () => {
  it('loads only the selected report fee with missing finance values left unknown and enforces readiness/version/scope', async () => {
    const t = await setup(), sample = t.state.samples.find(s => s.id === 'demo-yp-92')!
    sample.reportPricing = { amount: 125.5, rule: '测试收费规则', at: new Date().toISOString() }
    const detail = t.service.distributionDetail(sample.id, sample.version, sample.reportRelease!.id)
    expect(detail).toMatchObject({ id: sample.id, form: '纸质', totalAmount: 125.5, receivedAmount: null, contractBalance: null, availableCredit: null })
    expect(detail.fees).toEqual([{ id: sample.id, testPlan: sample.details!.testPlan, code: sample.code, quantity: sample.quantity, amount: 125.5, paymentStatus: sample.details!.paymentStatus || '' }])
    expect(() => t.service.distributionDetail(sample.id, sample.version - 1, sample.reportRelease!.id)).not.toThrow()
    const pending = t.state.samples.find(s => s.id === 'demo-yp-94')!
    expect(() => t.service.distributionDetail(pending.id, pending.version, pending.reportRelease!.id)).toThrow()
    t.restrict(); expect(() => t.service.distributionDetail(sample.id, sample.version, sample.reportRelease!.id)).toThrow()
  })
  it('searches the recorded recipient before pagination and export', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-92')!
    source.reportRelease!.receipt = { recipient: '张先生 Alice', method: '领取', date: '2026-10-02', at: '2026-10-02T00:00:00Z', actorId: 'admin', actorName: '管理员', notes: '' }
    const query = { searchField: 'recipient', contains: ' 张先生 ' }
    expect(t.service.distributionList(query).items.map(row => row.id)).toEqual([source.id])
    expect(t.service.distributionList({ ...query, contains: 'alice' }, true).items.map(row => row.id)).toEqual([source.id])
    expect(t.service.distributionList({ ...query, contains: source.customer }).total).toBe(0)
    expect(() => parseReportPrintQuery({ searchField: 'reportTitle' }, 'distribution')).toThrow()
    expect(() => parseReportPrintQuery(query, 'print')).toThrow()
  })
  it('filters actual print and receipt dates before pagination and export', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-92')!
    source.reportRelease!.history.push({ at: '2026-10-01T17:00:00Z', actorId: 'admin', actorName: '管理员', action: '打印完成', reason: '' })
    source.reportRelease!.distributionStatus = '已发放'
    source.reportRelease!.receipt = { recipient: '客户', method: '领取', date: '2026-10-03', at: '2026-10-03T00:00:00Z', actorId: 'admin', actorName: '管理员', notes: '' }
    const query = { ids: [source.id], dateField: 'printDate', from: '2026-10-02', to: '2026-10-02' }
    expect(t.service.distributionList(query).items.map(row => row.id)).toEqual([source.id])
    expect(t.service.distributionList({ ...query, dateField: 'distributionDate' }).total).toBe(0)
    expect(t.service.distributionList({ ...query, dateField: 'distributionDate', from: '2026-10-03', to: '2026-10-03', distributionStatus: '已发放' }, true).items.map(row => row.id)).toEqual([source.id])
    expect(t.service.distributionList({ ...query, distributionStatus: '未发放' }).total).toBe(0)
    expect(() => parseReportPrintQuery({ dateField: 'testStartDate' }, 'distribution')).toThrow()
    expect(() => parseReportPrintQuery({ dateField: 'printDate' }, 'signing')).toThrow()
  })
  it('filters collection methods consistently for lists and exports, including historical pickup records', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-92')!
    t.state.samples = ['领取', '自取', '邮寄', '文件交付', '链接交付', ''].map((method, index) => {
      const sample = structuredClone(source)
      sample.id = `method-${index}`
      if (method) sample.reportRelease!.receipt = { recipient: '客户', method, date: '2026-10-02', notes: '', at: '2026-10-02T00:00:00Z', actorId: 'admin', actorName: '管理员' }
      return sample
    })
    expect(t.service.distributionList({ collectionMethod: '自取' }).items.map(row => row.id)).toEqual(['method-0', 'method-1'])
    expect(t.service.distributionList({ collectionMethod: '邮寄' }, true).items.map(row => row.id)).toEqual(['method-2'])
    expect(t.service.distributionList({ collectionMethod: '其他' }, true).items.map(row => row.id)).toEqual(['method-3', 'method-4'])
    expect(t.service.distributionList({ collectionMethod: '' }).total).toBe(6)
    expect(() => parseReportPrintQuery({ collectionMethod: '无效方式' }, 'distribution')).toThrow()
  })
  it('retains form-specific menus and readiness rules', async () => {
    const t = await setup(), rows = t.service.distributionList({}).items
    const paper = rows.find(row => row.id === 'demo-yp-91')!, electronic = rows.find(row => row.id === 'demo-yp-94')!
    expect(paper.actions.map(action => action.label)).toEqual(['预览', '打印', '发放', '撤销发放', '重新计价'])
    expect(electronic.actions.map(action => action.label)).toEqual(['预览', '下载报告', '发放', '撤销发放', '重新计价'])
    for (const row of [paper, electronic]) expect(row.actions.find(action => action.id === 'distribute')?.enabled).toBe(false)
    expect(rows.find(row => row.id === 'demo-yp-92')!.actions.find(action => action.id === 'distribute')?.enabled).toBe(true)
    const source = t.state.samples.find(s => s.id === paper.id)!
    source.reportRelease!.supersededAt = new Date().toISOString()
    expect(t.service.distributionList({ ids: [paper.id] }).items).toHaveLength(0)
    for (const query of [{ form: '纸质及电子' }, { distributionStatus: '部分发放' }, { status: '无效状态' }]) expect(() => parseReportPrintQuery(query, 'distribution')).toThrow()
  })
  it('persists postal receipt fields and preserves them in reversal history', async () => {
    const t = await setup(), row = t.service.distributionList({ ids: ['demo-yp-92'] }).items[0]!
    const input = { action: 'distribute', releaseId: row.releaseId, version: row.version, recipient: '收件人', method: '邮寄', date: '2026-10-02', trackingNumber: 'SF123456', mailingAddress: '客户收件地址' }
    expect(() => t.service.action(row.id, { ...input, trackingNumber: 'x'.repeat(101) })).toThrow()
    t.service.action(row.id, input)
    const delivered = t.service.distributionList({ distributionStatus: '已发放' }).items[0]!
    expect(delivered).toMatchObject({ id: row.id, distributionStatus: '已发放', dataStatus: '报告发放完成', recipient: '收件人', distributionDate: '2026-10-02', deliveryMethod: '邮寄', trackingNumber: 'SF123456', mailingAddress: '客户收件地址' })
    t.service.action(row.id, { action: 'undo-distribute', releaseId: row.releaseId, version: delivered.version, reason: '修正登记' })
    expect(t.service.distributionList({ ids: [row.id] }).items[0]).toMatchObject({ distributionStatus: '未发放', recipient: '', distributionDate: '', deliveryMethod: '', trackingNumber: '' })
    expect(t.state.samples.find(s => s.id === row.id)!.reportRelease!.history.at(-1)!.reason).toContain('SF123456')
  })
  it('applies filters before pagination/export and supplies distribution plan counts', async () => {
    const t = await setup(), source = t.state.samples.find(s => s.id === 'demo-yp-92')!
    source.reportRelease!.approvedAt = '2026-10-01T17:00:00Z'
    t.state.samples = Array.from({ length: 14 }, (_, i) => ({ ...structuredClone(source), id: `delivery-${i}`, code: `DELIVERY${i}`, customer: i < 12 ? '查询单位' : '其他单位' }))
    const query = { form: '纸质', distributionStatus: '未发放', searchField: 'customer', contains: '查询单位', dateField: 'approvalDate', from: '2026-10-02', to: '2026-10-02', plans: { groupIds: [], planIds: [source.details!.testPlanId], excludedPlanIds: [] }, page: 2, pageSize: 10 }
    expect(t.service.distributionList(query)).toMatchObject({ total: 12, page: 2 })
    expect(t.service.distributionList(query).items).toHaveLength(2)
    expect(t.service.distributionList(query, true).items).toHaveLength(12)
    expect(t.service.distributionList({ ...query, ids: ['delivery-0'] }, true).items.map(row => row.id)).toEqual(['delivery-0'])
    expect(t.service.distributionList({ ...query, form: '电子' }).total).toBe(0)
    expect(t.service.distributionList({ ...query, distributionStatus: '已发放' }).total).toBe(0)
    expect(t.service.distributionList({ ...query, from: '2026-10-01', to: '2026-10-01' }).total).toBe(0)
    expect((await t.registration.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'report-distribution')).populated?.total).toBe(1)
    t.restrict(); expect(t.service.distributionList({}, true).items).toHaveLength(0)
  })
})
