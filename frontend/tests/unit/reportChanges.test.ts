import { describe, expect, it } from 'vitest'
import { createReportChanges } from '../../server/reportChanges'
import { seedRegistration } from '../../server/registrationDomain'
import { seedReportLifecycleDemo } from '../../server/reportLifecycleDemo'
import { demoActors } from '../../src/services/storage/demoActors'
async function setup() {
  let state = seedRegistration(), actor = demoActors[0]!
  await seedReportLifecycleDemo(state)
  const service = createReportChanges({ actor: () => actor, read: () => state, write: next => { state = next } })
  const s = state.samples.find(s => s.id === 'demo-yp-92')!
  const draft = { sampleId: s.id, sampleVersion: s.version, releaseId: s.reportRelease!.id, changeType: '委托信息更改', reason: '纠正录入错误' }
  return { service, externalService: createReportChanges({ actor: () => actor, read: () => state, write: next => { state = next } }, 'external'), draft, state: () => state, actor: (id: string, departmentOnly = false) => { actor = { ...demoActors.find(a => a.id === id)!, ...(departmentOnly ? { scope: 'department' as const } : {}) } } }
}
describe('internal report change applications', () => {
  it('queries and validates handlers with shared picker paging and authorized personnel scope', async () => {
    const t = await setup(), service = t.externalService
    const department = service.queryHandlers({})
    expect(department.scope).toBe('department')
    expect(department.items.every(p => p.departmentId === 'lab')).toBe(true)
    const first = service.queryHandlers({ scope: 'all', pageSize: 10 }), second = service.queryHandlers({ scope: 'all', pageSize: 10, page: 2 })
    expect(first.total).toBe(11)
    expect(first.items).toHaveLength(10)
    expect(second.items).toHaveLength(1)
    expect(new Set([...first.items, ...second.items].map(p => p.id)).size).toBe(11)
    expect(service.queryHandlers({ scope: 'all', keyword: 'OTHER' }).items).toEqual([service.resolveHandler({ id: 'other' })])
    expect(service.queryHandlers({ keyword: '受理' }).items[0]).toMatchObject({ id: 'business', departmentName: '实验室', certificateNumber: '', phone: '' })
    expect(service.queryHandlers({ scope: 'all', page: 99 }).page).toBe(2)
    expect(service.queryHandlers({ keyword: '不存在' }).total).toBe(0)
    for (const input of [{ scope: 'preset' }, { page: 0 }, { pageSize: 15 }, { keyword: [] }]) expect(() => service.queryHandlers(input)).toThrow()
    t.actor('reviewer', true)
    expect(service.queryHandlers({ scope: 'all' }).items.every(p => p.departmentId === 'lab')).toBe(true)
    expect(() => service.resolveHandler({ id: 'other' })).toThrow('不可选')
    expect(() => service.resolveHandler({ id: 'missing' })).toThrow('不可选')
    t.actor('business')
    expect(() => service.queryHandlers({})).toThrow('无权')
    expect(() => service.resolveHandler({ id: 'admin' })).toThrow('无权')
  })
  it('stores external fields and evidence, isolates sources, and keeps shared workflow rules', async () => {
    const t = await setup(), original = structuredClone(t.state().samples)
    const external = { handlerId: 'admin', handlerName: '伪造姓名', isCommissionCustomer: true, evidence: [{ id: 'proof', name: '证据.txt', type: 'text/plain', size: 3, dataUrl: 'data:text/plain;base64,YWJj' }], allReturned: false }
    const input = { ...t.draft, responsibility: '委托单位', charge: true, amount: 125.5, before: '原内容', after: '新内容', external }
    const saved = t.externalService.save(input)
    expect(saved).toMatchObject({ source: 'external', responsibility: '委托单位', amount: 125.5, before: '原内容', after: '新内容', external: { handlerId: 'admin', handlerName: '演示用户', isCommissionCustomer: true } })
    expect(t.externalService.detail(saved.id).external!.evidence).toEqual(external.evidence)
    expect(t.service.query({}).total).toBe(0)
    expect(() => t.service.detail(saved.id)).toThrow('无权访问')
    expect(() => t.service.action(saved.id, { action: 'delete', version: saved.version })).toThrow('无权访问')
    expect(t.service.candidates({ keyword: t.draft.sampleId.replace('demo-yp-', 'SP20260900') })).toHaveLength(0)
    Object.assign(t.state().reportChangeRequests![0]!.external!, { issuedOriginals: 2, returnedOriginals: 1 })
    const submitted = t.externalService.save({ ...input, charge: false, external: { ...external, allReturned: true }, version: saved.version, intent: 'submit' }, saved.id)
    expect(submitted).toMatchObject({ amount: 0, status: '待审批', canEdit: false, external: { allReturned: true, issuedOriginals: 2, returnedOriginals: 1 } })
    const withdrawn = t.externalService.action(saved.id, { action: 'withdraw', version: submitted.version, reason: '调整' })
    expect(t.externalService.query({}).total).toBe(1)
    expect(t.externalService.export({})).toContain('委托单位')
    t.externalService.action(saved.id, { action: 'delete', version: withdrawn.version })
    expect(t.state().reportChangeRequests![0]!.events.at(-1)).toMatchObject({ action: '删除申请', reason: '' })
    expect(t.state().reportChangeRequests![0]!.events.find(event => event.action === '撤销申请')?.reason).toBe('调整')
    expect(t.externalService.query({}).total).toBe(0)
    expect(t.state().samples).toEqual(original)
  })
  it('validates external amounts, personnel, attachments and returned report choice', async () => {
    const t = await setup()
    const external = { handlerId: '', handlerName: '', isCommissionCustomer: false, evidence: [], allReturned: true }
    const input = { ...t.draft, charge: true, amount: 0, external }
    expect(() => t.externalService.save({ ...input, amount: -1 })).toThrow('收费金额')
    expect(() => t.externalService.save({ ...input, amount: 1.111 })).toThrow('收费金额')
    for (const change of [{ handlerId: 'missing' }, { allReturned: '是' }, { allReturned: undefined }, { evidence: [{ name: 'bad.txt', size: 100, type: 'text/plain', dataUrl: 'data:text/plain;base64,YWJj' }] }]) expect(() => t.externalService.save({ ...input, external: { ...external, ...change } })).toThrow()
    expect(t.externalService.query({}).total).toBe(0)
    const internal = t.service.save({ ...input, responsibility: '不可写', amount: 99 })
    expect(internal.external).toBeUndefined()
    expect(internal.amount).toBe(0)
    expect(t.externalService.query({}).total).toBe(0)
  })
  it('groups reports from one commission into one application and validates every report before saving', async () => {
    const t = await setup(), originalSample = t.state().samples.find(s => s.id === t.draft.sampleId)!
    const second = { ...structuredClone(originalSample), id: 'second-report', code: 'SP-SECOND', reportCode: 'BG-SECOND' }
    t.state().samples.push(second)
    const reports = [originalSample, second].map(s => ({ sampleId: s.id, sampleVersion: s.version, releaseId: s.reportRelease!.id }))
    const original = structuredClone(t.state())
    expect(() => t.service.save({ ...t.draft, reports: [reports[0], { ...reports[1], releaseId: 'stale' }] })).toThrow('更新')
    expect(t.state()).toEqual(original)
    second.commissionId = 'different-commission'
    expect(() => t.service.save({ ...t.draft, reports })).toThrow('同一委托单')
    second.commissionId = originalSample.commissionId
    expect(() => t.service.save({ ...t.draft, reports: [reports[0], reports[0]] })).toThrow('重复')
    const r = t.service.save({ ...t.draft, intent: 'submit', reports })
    expect(r.reports).toHaveLength(2)
    expect(r.sampleCode).toBe(`${originalSample.code}、${second.code}`)
    expect(t.state().reportChangeRequests).toHaveLength(1)
    expect(t.state().samples).toEqual(original.samples)
    expect(t.service.query({ sampleCode: second.code }).items[0]!.id).toBe(r.id)
    expect(t.service.export({})).toContain(second.reportCode)
    expect(t.service.candidates({ keyword: second.code })).toHaveLength(0)
    expect(() => t.service.save({ ...t.draft, reports })).toThrow('已有')
    const withdrawn = t.service.action(r.id, { action: 'withdraw', version: r.version, reason: '调整' })
    t.state().samples.find(s => s.id === second.id)!.version++
    const detail = t.service.detail(r.id)
    expect(detail.reports![1]!.sampleVersion).toBe(second.version + 1)
    expect(() => t.service.save({ ...t.draft, version: withdrawn.version, reports }, r.id)).not.toThrow()
    const changed = t.service.save({ ...detail, reason: '统一原因' }, r.id)
    expect(changed.reports).toHaveLength(2)
    expect(() => t.service.save({ ...changed, reports: changed.reports!.slice(0, 1) }, r.id)).toThrow('关联报告不能更换')
    t.state().samples.find(s => s.id === second.id)!.reportRelease!.supersededAt = new Date().toISOString()
    expect(t.service.detail(r.id).canEdit).toBe(false)
    expect(() => t.service.save({ ...changed, reason: '不能修改' }, r.id)).toThrow('不能修改')
    t.service.action(r.id, { action: 'delete', version: changed.version })
    expect(t.service.query({}).total).toBe(0)
  })
  it('filters candidate reports by commission and report codes and returns picker columns', async () => {
    const t = await setup(), sample = t.state().samples.find(s => s.id === t.draft.sampleId)!
    const commission = t.state().commissions.find(c => c.id === sample.commissionId)!
    const result = t.service.candidates({ commissionCode: commission.code.toLowerCase(), reportCode: sample.reportCode.toLowerCase() })
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ id: sample.id, code: sample.code, reportCode: sample.reportCode, commissionCode: commission.code, contractCode: sample.commissionInfo.contract || commission.contract })
    expect(t.service.candidates({ commissionCode: '不存在', reportCode: sample.reportCode })).toHaveLength(0)
    expect(() => t.service.candidates({ commissionCode: ['invalid'] })).toThrow()
  })
  it('saves, edits, withdraws and soft deletes applications without changing approved files', async () => {
    const t = await setup(), original = structuredClone(t.state().samples.find(s => s.id === t.draft.sampleId)!)
    const r = t.service.save(t.draft)
    expect(r).toMatchObject({ status: '申请中', applicant: '演示用户', department: '实验室', canDelete: true })
    expect(t.state().samples.find(s => s.id === t.draft.sampleId)).toEqual(original)
    expect(() => t.service.save(t.draft)).toThrow('已有')
    expect(() => t.service.action(r.id, { version: r.version, action: 'withdraw', reason: '取消' })).toThrow('不能撤销')
    const changed = t.service.save({ ...t.draft, version: r.version, reason: '修正内容' }, r.id)
    expect(changed.amount).toBe(0)
    const submitted = t.service.save({ ...t.draft, version: changed.version, intent: 'submit' }, r.id)
    expect(submitted).toMatchObject({ status: '待审批', canEdit: false, canDelete: false, canWithdraw: true })
    expect(() => t.service.action(r.id, { version: submitted.version, action: 'delete' })).toThrow('撤销')
    expect(() => t.service.save({ ...t.draft, version: submitted.version }, r.id)).toThrow('不能修改')
    expect(() => t.service.action(r.id, { version: submitted.version, action: 'withdraw', reason: ' ' })).toThrow('原因')
    const withdrawn = t.service.action(r.id, { version: r.version, action: 'withdraw', reason: '申请错误' })
    expect(withdrawn).toMatchObject({ status: '申请中', withdrawalReason: '申请错误', canDelete: true })
    t.service.action(r.id, { version: withdrawn.version, action: 'delete' })
    expect(t.service.query({}).total).toBe(0)
    expect(t.state().reportChangeRequests![0]!.events.map(e => e.action)).toEqual(['新增申请', '修改申请', '提交申请', '撤销申请', '删除申请'])
    expect(t.state().samples.find(s => s.id === t.draft.sampleId)).toEqual(original)
  })
  it('checks scope, ownership, file versions and input at the write boundary', async () => {
    const t = await setup()
    expect(() => t.service.save({ ...t.draft, changeType: '无效类型' })).toThrow('更改类型')
    expect(() => t.service.save({ ...t.draft, reason: '', intent: 'submit' })).toThrow('原因')
    expect(() => t.service.save({ ...t.draft, releaseId: 'stale' })).toThrow('更新')
    const r = t.service.save(t.draft)
    t.actor('reviewer'); expect(t.service.detail(r.id).canEdit).toBe(false)
    expect(() => t.service.save({ ...t.draft, version: r.version }, r.id)).toThrow('修改')
    t.actor('business'); expect(() => t.service.query({})).toThrow('无权')
    t.actor('admin'); t.state().samples.find(s => s.id === t.draft.sampleId)!.reportRelease!.supersededAt = new Date().toISOString()
    expect(t.service.detail(r.id).canEdit).toBe(false)
    expect(() => t.service.save({ ...t.draft, version: r.version }, r.id)).toThrow('不能修改')
  })
  it('applies filters, sorting, paging and export to application records', async () => {
    const t = await setup(), r = t.service.save(t.draft), date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date(r.appliedAt))
    expect(t.service.query({ from: date, to: date, code: r.code, departmentId: 'lab', applicant: '演示', sampleCode: '0092', status: '申请中', sort: 'code', direction: 'desc' }).total).toBe(1)
    expect(t.service.query({ applicant: '不存在' }).total).toBe(0)
    expect(t.service.export({ ids: [r.id] })).toContain('更改责任方')
    expect(t.service.export({ ids: [r.id] })).toContain('纠正录入错误')
    expect(() => t.service.query({ from: '2026-10-03', to: '2026-10-01' })).toThrow('开始日期')
    expect(() => t.service.query({ sort: 'other' })).toThrow('排序')
    expect(() => t.service.query({ from: '2026-99-99' })).toThrow('日期格式')
    expect(t.service.candidates({ keyword: 'SP2026090092' })).toHaveLength(0)
    expect(t.service.candidates({ keyword: 'SP2026090091' })).toHaveLength(1)
  })
  it('keeps an application bound to its original file and refreshes benign sample versions', async () => {
    const t = await setup(), r = t.service.save(t.draft), sample = t.state().samples.find(s => s.id === t.draft.sampleId)!
    sample.version++
    expect(t.service.detail(r.id).sampleVersion).toBe(sample.version)
    expect(() => t.service.save({ ...t.draft, version: r.version }, r.id)).not.toThrow()
    const latest = t.service.save({ ...t.draft, sampleVersion: sample.version, version: r.version }, r.id)
    const currentSample = t.state().samples.find(s => s.id === t.draft.sampleId)!
    currentSample.reportRelease!.id = 'new-release'
    expect(t.service.query({}).items[0]!.canEdit).toBe(false)
    expect(() => t.service.save({ ...t.draft, sampleVersion: currentSample.version, releaseId: 'new-release', version: latest.version }, r.id)).toThrow('不能修改')
  })
  it('saves incomplete drafts, submits all four change types and preserves historical detail fields', async () => {
    const t = await setup(), r = t.service.save({ ...t.draft, reason: '' })
    const stored = t.state().reportChangeRequests![0]!
    stored.before = '原内容'; stored.after = '更正内容'; stored.responsibility = '检测部门'; stored.charge = true; stored.amount = 12.5
    let current = r
    for (const changeType of ['委托信息更改', '检测数据更改', '委托信息更改和检测数据更改', '补充报告']) {
      current = t.service.save({ ...t.draft, changeType, intent: 'submit', version: current.version, amount: 999, before: '不能覆盖历史' }, r.id)
      expect(current).toMatchObject({ changeType, status: '待审批', before: '原内容', amount: 12.5 })
      current = t.service.action(r.id, { action: 'withdraw', version: current.version, reason: '调整类型' })
    }
  })
})
