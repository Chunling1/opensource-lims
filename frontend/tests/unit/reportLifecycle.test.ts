import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration } from '../../server/registrationDomain'
import { createReviewChecks } from '../../server/reviewChecks'
import { createDataEntryService, seedCompletedReport } from '../../server/dataEntryDetail'
import { createReportLifecycleService, demoLifecycleConfig, prepareReportRelease, commitReportRelease, reportForm } from '../../server/reportLifecycle'
import { createDemoSigningProvider, type SigningProvider, type SigningResult } from '../../server/reportSigning'
import { parseSampleDetails, sampleFormOptions } from '../../server/sampleForm'
import { demoActors } from '../../src/services/storage/demoActors'
import type { ReportLifecycleConfig } from '../../server/reportLifecycle'
import type { ReportRelease } from '../../src/types/reports/reportLifecycle'

async function setup(form: '纸质' | '电子' = '纸质', config: ReportLifecycleConfig = demoLifecycleConfig) {
  let state = seedRegistration(), actor = demoActors[0]!, mode: SigningResult['status'] = 'complete', failSubmit = false, submissions = 0, queries = 0
  const id = 'demo-yp-88', sample = state.samples.find(s => s.id === id)!
  sample.details!.reportForm = form; seedCompletedReport(state, sample)
  const deps = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
  const stages = createRegistrationService(deps, createReviewChecks(0), undefined, config)
  const proof = await stages.reportComplianceCheck(id, sample.version, 'approval')
  await stages.reportCheckAction(id, 'check', sample.version, { nextAction: 'next', readConfirmed: true, reviewCheckId: proof.id }, undefined, 'approval')
  const output = (release: ReportRelease): SigningResult => ({ externalId: `vendor-${release.signing!.key}`, status: mode, signature: mode === 'complete', seal: mode === 'complete', ...(mode === 'complete' ? { file: { ...release.original, id: 'signed' } } : {}), ...(mode === 'failed' ? { error: '明确失败' } : {}) })
  const provider: SigningProvider = { name: 'demo', verifyCallback: token => token === 'trusted', async submit(release) { submissions++; if (failSubmit) throw new Error('timeout'); return output(release) }, async query(release) { queries++; return output(release) } }
  const service = createReportLifecycleService(deps, provider, config)
  const current = () => state.samples.find(s => s.id === id)!
  const act = (action: string, extra: Record<string, unknown> = {}) => service.action(id, { action, version: current().version, releaseId: current().reportRelease!.id, ...extra })
  return { id, current, service, stages, state: () => state, act, actor: (id: string) => { actor = demoActors.find(a => a.id === id)! }, mode: (value: SigningResult['status']) => { mode = value }, timeout: () => { failSubmit = true }, counts: () => ({ submissions, queries }) }
}
describe('approved paper and electronic reports', () => {
  it('limits report forms at the write boundary, defaults absent legacy values and blocks mixed legacy approval', () => {
    expect(sampleFormOptions([]).choices.reportForm).toEqual(['纸质', '电子'])
    expect(() => parseSampleDetails({ reportForm: '纸质及电子' })).toThrow('纸质或电子')
    const sample = seedRegistration().samples[0]!
    expect(reportForm(sample)).toBe('纸质')
    sample.details = { ...parseSampleDetails({}), reportForm: '纸质及电子' }
    expect(() => reportForm(sample)).toThrow('报告更改')
  })
  it('freezes the approved file and gates paper printing, delivery, reversal and archive queues independently', async () => {
    const t = await setup(), r = t.current().reportRelease!, original = structuredClone(r.original)
    expect(r).toMatchObject({ form: '纸质', printStatus: '待打印', distributionStatus: '未发放' }); expect(r.signing).toBeUndefined()
    expect(t.service.query({ queue: 'signing' }).items.some(row => row.id === t.id)).toBe(false)
    expect(() => t.act('distribute', { recipient: '客户', method: '领取', date: '2026-10-02' })).toThrow()
    const version = t.current().version
    expect(t.service.file(t.id, r.id, 'preview')).toEqual(original)
    expect(t.service.file(t.id, r.id, 'print')).toEqual(original)
    expect(t.current().version).toBe(version)
    expect(() => t.act('complete-print')).toThrow('请确认')
    t.act('complete-print', { confirmed: true }); t.act('undo-print'); t.act('complete-print', { confirmed: true })
    expect(() => t.act('distribute', { recipient: '客户', method: '文件交付', date: '2026-10-02' })).toThrow('不匹配')
    t.act('distribute', { recipient: '张工', method: '邮寄', date: '2026-10-02', notes: '快递' })
    expect(t.service.query({ queue: 'archive' }).items.map(r => r.id)).toContain(t.id)
    expect(() => t.act('undo-print')).toThrow()
    expect(() => t.act('undo-distribute', { reason: ' ' })).toThrow()
    t.act('undo-distribute', { reason: '登记有误' })
    expect(t.current().reportRelease!.history.at(-1)?.reason).toContain('张工')
    expect(t.service.query({ queue: 'archive' }).items.map(r => r.id)).not.toContain(t.id)
    expect(t.current().reportRelease!.original).toEqual(original)
    await expect(t.stages.reportCheckAction(t.id, 'undo', t.current().version, undefined, undefined, 'approval')).rejects.toMatchObject({ code: 'BUSINESS_RULE' })
  })
  it('enqueues electronic signing on approval, queries uncertain submissions and delivers without printing', async () => {
    const t = await setup('电子'), releaseId = t.current().reportRelease!.id
    expect(t.current().reportRelease).toMatchObject({ printStatus: '不适用', signing: { status: '待签章' } })
    expect(t.service.query({ queue: 'print' }).items.map(r => r.id)).not.toContain(t.id)
    expect(() => t.service.file(t.id, releaseId, 'print')).toThrow()
    expect(() => t.service.file(t.id, releaseId, 'download')).toThrow()
    expect(() => t.act('distribute')).toThrow()
    t.timeout(); await t.service.tick()
    expect(t.current().reportRelease!.signing!.status).toBe('待确认')
    expect(() => t.act('retry')).toThrow()
    await t.service.tick()
    expect(t.current().reportRelease!.signing!.status).toBe('签章完成')
    expect(t.counts()).toEqual({ submissions: 1, queries: 1 })
    expect(t.service.file(t.id, releaseId, 'download').id).toBe('signed')
    expect(t.current().reportRelease!.distributionStatus).toBe('未发放')
    for (const method of ['自取', '邮寄', '文件交付', '链接交付']) {
      expect(() => t.act('distribute', { recipient: '李工', method, date: '2026-10-02' })).toThrow('不匹配')
    }
    t.act('distribute', { recipient: '李工', method: '其他', date: '2026-10-02', notes: '链接交付', trackingNumber: '不应保存', mailingAddress: '不应保存' })
    expect(t.current().reportRelease!.receipt).toMatchObject({ method: '其他', notes: '链接交付' })
    expect(t.current().reportRelease!.receipt).not.toHaveProperty('trackingNumber')
    expect(t.current().reportRelease!.receipt).not.toHaveProperty('mailingAddress')
    expect(t.current().reportRelease!.printStatus).toBe('不适用')
    expect(() => t.act('retry')).toThrow()
  })
  it('retries definite failures, rejects stale callbacks, validates callback authentication and ignores successful duplicates', async () => {
    const t = await setup('电子')
    t.mode('failed'); await t.service.tick()
    const r = t.current().reportRelease!, callback = { sampleId: t.id, releaseId: r.id, revision: r.revision, taskKey: r.signing!.key, externalId: r.signing!.externalId! }
    expect(r.signing!.status).toBe('签章失败')
    await expect(t.service.callback('wrong', callback)).rejects.toMatchObject({ code: 'FORBIDDEN' })
    t.act('retry'); expect(t.current().reportRelease!.signing!.attempt).toBe(2)
    expect(t.current().reportRelease!.signing!.attempts![0]!.externalId).toBe(callback.externalId)
    expect(await t.service.callback('trusted', callback)).toEqual({ accepted: false })
    t.mode('complete'); await Promise.all([t.service.tick(), t.service.tick()])
    const done = structuredClone(t.current().reportRelease!), task = done.signing!
    await t.service.callback('trusted', { ...callback, taskKey: task.key, externalId: task.externalId! })
    expect(t.current().reportRelease).toEqual(done)
    expect(t.counts().submissions).toBe(2)
  })
  it('requires both signing steps and a valid final file', async () => {
    const t = await setup('电子'), deps = { actor: () => demoActors[0]!, read: t.state, write: (s: ReturnType<typeof t.state>) => { Object.assign(t.state(), s) } }
    const partial: SigningProvider = { name: 'demo', verifyCallback: () => true, async submit() { return { externalId: 'partial', status: 'complete', signature: true, seal: false } }, async query() { return { externalId: 'partial', status: 'complete', signature: true, seal: true, file: { id: 'bad', name: 'bad.pdf', sha256: 'bad', base64: 'aGVsbG8=' } } } }
    const service = createReportLifecycleService(deps, partial)
    await service.tick(); expect(t.current().reportRelease!.signing!.status).toBe('待确认')
    await service.tick(); expect(t.current().reportRelease!.signed).toBeUndefined()
    expect(t.current().reportRelease!.signing!.status).toBe('待确认')
  })
  it('preserves files and delivery history on change, blocks old callbacks and requires fresh approval', async () => {
    const t = await setup('电子'); t.mode('unknown'); await t.service.tick()
    const release = structuredClone(t.current().reportRelease!), task = release.signing!
    t.service.requestChange(t.id, { version: t.current().version, source: 'internal', destination: 'testing', reason: '更正报告正文' })
    expect(t.current().reportRelease).toBeUndefined()
    expect(t.current().reportReleaseHistory![0]!.original).toEqual(release.original)
    t.mode('complete')
    expect(await t.service.callback('trusted', { sampleId: t.id, releaseId: release.id, revision: release.revision, taskKey: task.key, externalId: task.externalId! })).toEqual({ accepted: false })
    expect(() => t.service.file(t.id, release.id, 'preview')).toThrow()
    expect(t.service.query({ queue: 'distribution' }).items.map(r => r.id)).not.toContain(t.id)
  })
  it('blocks revoked reports, stale versions and unauthorized or out-of-scope actions', async () => {
    const t = await setup(), version = t.current().version, releaseId = t.current().reportRelease!.id
    t.act('complete-print', { confirmed: true })
    expect(() => t.service.action(t.id, { action: 'undo-print', version, releaseId })).not.toThrow()
    t.actor('finance'); expect(() => t.act('undo-print')).toThrow()
    t.actor('other'); expect(() => t.service.query({ queue: 'print' })).toThrow()
    t.actor('admin'); t.current().status = 'void_pending'
    expect(() => t.service.file(t.id, releaseId, 'preview')).toThrow()
    expect(() => t.act('distribute')).toThrow()
  })
  it('supports manual pricing without configured rules and preserves report files', async () => {
    const noRule = await setup()
    expect(noRule.service.query({ queue: 'distribution' }).items.find(r => r.id === noRule.id)!.actions.find(a => a.id === 'reprice')).toMatchObject({ enabled: true })
    const sample = noRule.current(), release = structuredClone(sample.reportRelease), version = sample.version
    const detail = noRule.service.pricingDetail(noRule.id, version, release!.id)
    expect(detail).toMatchObject({ discountPrice: null, actualPrice: null, otherItems: [], pricingMethod: '手工计价' })
    expect(detail.parameterItems.map(item => item.name)).toEqual(sample.projects)
    for (const actualPrice of [null, '', -1, 1.234, Infinity, 1e12]) {
      expect(() => noRule.act('reprice', { prices: { standardPrice: 100, discountPrice: 80, actualPrice } })).toThrow()
      expect(noRule.current().version).toBe(version)
    }
    noRule.act('reprice', { prices: { standardPrice: 100, discountPrice: 80, actualPrice: 75.5 } })
    expect(noRule.current().reportPricing).toMatchObject({ standardPrice: 100, discountPrice: 80, amount: 75.5 })
    expect(noRule.current().reportRelease!.original).toEqual(release!.original)
    expect(noRule.current().reportRelease!.history.at(-1)?.reason).toContain('75.5')
    expect(noRule.service.distributionList({ ids: [noRule.id] }).items[0]).toMatchObject({ standardPrice: 100, discountPrice: 80, actualPrice: 75.5 })
    expect(() => noRule.service.pricingDetail(noRule.id, version, release!.id)).not.toThrow()
    noRule.actor('reviewer')
    expect(() => noRule.service.pricingDetail(noRule.id, noRule.current().version, release!.id)).toThrow()
    expect(() => noRule.act('reprice', { prices: { standardPrice: 1, discountPrice: 1, actualPrice: 1 } })).toThrow()
    const t = await setup('纸质', { ...demoLifecycleConfig, price: () => ({ amount: 100, rule: '测试收费规则1' }) }), file = structuredClone(t.current().reportRelease!.original)
    t.act('reprice'); expect(t.current().reportPricing?.amount).toBe(100); expect(t.current().reportRelease!.original).toEqual(file)
  })
  it('fails approval atomically when signing configuration or the final report is missing', async () => {
    const state = seedRegistration(), sample = state.samples.find(s => s.id === 'demo-yp-88')!
    sample.details!.reportForm = '电子'; seedCompletedReport(state, sample)
    await expect(prepareReportRelease(state, sample, demoActors[0]!, { signing: () => undefined })).rejects.toThrow('配置不完整')
    delete state.dataEntries![sample.id]
    await expect(prepareReportRelease(state, sample, demoActors[0]!)).rejects.toThrow('尚未生成')
    expect(sample.reportRelease).toBeUndefined(); expect(sample.reportApprovalInfo).toBeUndefined()
  })
  it('authenticates demo callbacks with a server-side secret', () => {
    const provider = createDemoSigningProvider('0123456789abcdef0123456789abcdef')
    expect(provider.verifyCallback('')).toBe(false)
    expect(provider.verifyCallback('0123456789abcdef0123456789abcdef')).toBe(true)
  })
  it('rejects stale final sources and rolls back a batch if any final report is missing', async () => {
    let state = seedRegistration()
    const sample = state.samples.find(s => s.id === 'demo-yp-88')!, prepared = await prepareReportRelease(state, sample, demoActors[0]!)
    state.dataEntries![sample.id]!.reportRevision++
    expect(() => commitReportRelease(state, sample, prepared)).toThrow('报告资料在批准期间发生变化')
    const service = createRegistrationService({ actor: () => demoActors[0]!, read: () => state, write: s => { state = s } }, createReviewChecks(0))
    const targets = ['demo-yp-88', 'demo-yp-90'].map(id => ({ id, version: state.samples.find(s => s.id === id)!.version }))
    const checks = await service.reportBatchCheck(targets, 'approval'), before = structuredClone(state)
    await expect(service.reportBatchSubmit(targets, 'check', { nextAction: 'next', readConfirmed: true }, checks.items.map(c => ({ sampleId: c.sampleId, checkId: c.id })), undefined, 'approval')).rejects.toThrow('尚未生成')
    expect(state).toEqual(before)
  })
  it('keeps signed files and receipts in the previous version when requesting changes', async () => {
    const t = await setup('电子'); await t.service.tick()
    t.act('distribute', { recipient: '已接收客户', method: '其他', date: '2026-10-02' })
    const signed = t.current().reportRelease!.signed
    t.service.requestChange(t.id, { version: t.current().version, source: 'external', destination: 'commission', reason: '更改形式' })
    const history = t.current().reportReleaseHistory![0]!
    expect(history.signed).toEqual(signed); expect(history.receipt!.recipient).toBe('已接收客户')
    expect(history.distributionStatus).toBe('已发放'); expect(t.current().dataStatus).toBe('委托更改中')
  })
  it('preserves the sample report form through transfer and approval and invalidates old checks', async () => {
    let state = seedRegistration()
    const actor = demoActors[0]!, deps = { actor: () => actor, read: () => state, write: (next: typeof state) => { state = next } }
    const stages = createRegistrationService(deps, createReviewChecks(0)), entry = createDataEntryService(deps), id = 'demo-yp-88'
    const proof = await stages.reportComplianceCheck(id, 1, 'approval')
    const transfer = await stages.reportCheckAction(id, 'check', 1, { reviewCheckId: proof.id, readConfirmed: true, nextAction: 'transfer', recipientId: 'approver' }, undefined, 'approval')
    const lifecycle = createReportLifecycleService(deps, createDemoSigningProvider('0123456789abcdef0123456789abcdef'))
    expect(lifecycle.query({ queue: 'print' }).items.map(row => row.id)).not.toContain(id)
    const prior = entry.detail(id), updated = transfer
    const expectedForm = prior.sample.details?.reportForm || '纸质'
    expect(entry.detail(id).reportStatus).toBe('ready'); expect(entry.detail(id).job!.id).toBe(prior.job!.id)
    const fresh = await stages.reportComplianceCheck(id, updated.version, 'approval')
    const approved = await stages.reportCheckAction(id, 'check', updated.version, { reviewCheckId: fresh.id, readConfirmed: true, nextAction: 'next' }, undefined, 'approval')
    expect(approved.reportRelease!.form).toBe(expectedForm)
    expect(approved.details?.reportForm || '纸质').toBe(expectedForm)
    await expect(stages.act('samples', id, 'unreview', approved.version)).rejects.toThrow('不能撤销')
  })
})
