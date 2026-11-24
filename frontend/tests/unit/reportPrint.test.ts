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
  return { state: () => state, service: createReportLifecycleService(deps, createDemoSigningProvider('test')), registration: createRegistrationService(deps), actor: (id: string) => { actor = id === 'scoped' ? { ...demoActors[3]!, departmentId: 'lab2', scope: 'department' } : demoActors.find(value => value.id === id)! } }
}
describe('report printing list', () => {
  it('returns the last available page when completing the final row removes the requested page', async () => {
    const t = await setup(), source = t.state().samples.find(s => s.id === 'demo-yp-91')!
    t.state().samples = Array.from({ length: 11 }, (_, index) => ({ ...structuredClone(source), id: `print-${index}`, code: `PRINT${index}` }))
    const query = { status: '报告打印中', page: 2, pageSize: 10 }
    const last = t.service.printList(query).items[0]!
    t.service.action(last.id, { action: 'complete-print', version: last.version, releaseId: last.releaseId, confirmed: true })
    const result = t.service.printList(query)
    expect(result).toMatchObject({ total: 10, page: 1, pageSize: 10 })
    expect(result.items).toHaveLength(10)
    expect(result.items.some(row => row.id === last.id)).toBe(false)
    expect(t.service.printList({ ...query, page: 999 })).toEqual(result)
    expect(t.service.printList({ ...query, contains: 'missing' })).toMatchObject({ items: [], total: 0, page: 1 })
  })
  it('uses independent printing facts and refreshes columns and filters after completing or undoing printing', async () => {
    const t = await setup(), sample = t.state().samples.find(s => s.id === 'demo-yp-91')!
    sample.details!.reportCopies = '3'; sample.details!.standardPrice = '125.50'
    sample.reportRelease!.approvedAt = '2026-10-01T17:00:00Z'
    const input = { contains: sample.reportCode, searchField: 'reportCode', dateField: 'approvalDate', from: '2026-10-02', to: '2026-10-02' }
    let row = t.service.printList(input).items[0]!
    expect(row).toMatchObject({ id: sample.id, reportCopies: '3', standardPrice: 125.5, discountPrice: null, actualPrice: null, approvalDate: '2026-10-02', dataStatus: '报告打印中', printDate: '', printPerson: '' })
    expect(row.actions.map(action => action.label)).toEqual(['预览', '打印', '查看附件', '打印完成', '撤销打印完成'])
    expect(t.service.printList({ ...input, status: '报告打印完成' }).total).toBe(0)
    expect(t.service.printList({ ...input, to: '2026-10-01', from: '2026-10-01' }).total).toBe(0)
    t.service.action(row.id, { action: 'complete-print', version: row.version, releaseId: row.releaseId, confirmed: true })
    row = t.service.printList({ ...input, status: '报告打印完成', printStatus: '已打印' }).items[0]!
    expect(row.printPerson).toBe(demoActors[0]!.name); expect(row.printDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(t.service.printList({ ...input, printStatus: '未打印' }).total).toBe(0)
    t.service.action(row.id, { action: 'undo-print', version: row.version, releaseId: row.releaseId })
    expect(t.service.printList(input).items[0]).toMatchObject({ printDate: '', printPerson: '', dataStatus: '报告打印中' })
  })
  it('filters content, dates, conclusion, sample type and plans before pagination and complete export', async () => {
    const t = await setup(), source = t.state().samples.find(s => s.id === 'demo-yp-91')!
    t.state().samples = Array.from({ length: 14 }, (_, index) => ({ ...structuredClone(source), id: `print-${index}`, code: `PRINT${index}`, customer: index < 12 ? '查询单位' : '其他单位', assignmentInfo: { ...source.assignmentInfo, conclusion: '合格' }, workflow: { ...source.workflow, testStartDate: '2026-10-01', testEndDate: '2026-10-02' } }))
    const query = { searchField: 'customer', contains: '查询单位', dateField: 'testEndDate', from: '2026-10-02', to: '2026-10-02', conclusion: '合格', sampleType: source.sampleType, plans: { groupIds: [], planIds: [source.details!.testPlanId], excludedPlanIds: [] }, page: 2, pageSize: 10 }
    expect(t.service.printList(query)).toMatchObject({ total: 12, page: 2, pageSize: 10 })
    expect(t.service.printList(query).items).toHaveLength(2)
    expect(t.service.printList(query, true).items).toHaveLength(12)
    expect(t.service.printList({ ...query, ids: ['print-0'], page: 1 }, true).items.map(row => row.id)).toEqual(['print-0'])
    expect(t.service.printList({ ...query, conclusion: '不合格' }).total).toBe(0)
    expect(t.service.printList({ ...query, from: '2026-10-03', to: '2026-10-03' }).total).toBe(0)
    expect((await t.registration.testPlanSelection({ groupIds: [], planIds: [], excludedPlanIds: [] }, undefined, 'report-print')).populated?.total).toBe(1)
    t.actor('scoped'); expect(t.service.printList({}, true).items).toHaveLength(0)
    t.actor('business'); expect(() => t.service.printList({})).toThrow()
  })
  it('excludes electronic, void and changing reports and validates all query choices', async () => {
    const t = await setup()
    expect(t.service.printList({}).items.every(row => row.form === '纸质')).toBe(true)
    const source = t.state().samples.find(s => s.id === 'demo-yp-91')!
    source.status = 'void_pending'
    expect(t.service.printList({ ids: [source.id] }).total).toBe(0)
    source.status = 'completed'; source.dataStatus = '检测更改中'
    expect(t.service.printList({ ids: [source.id] }).total).toBe(0)
    for (const query of [{ searchField: 'dataEntryPerson' }, { dateField: 'requestedTestDate' }, { dateField: 'approvalDate', from: '2026-02-30' }, { printStatus: '已审核' }, { status: '报告审核中' }]) expect(() => parseReportPrintQuery(query)).toThrow()
  })
})
