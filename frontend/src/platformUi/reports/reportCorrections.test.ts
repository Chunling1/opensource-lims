import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import Panel from './ReportCorrections.vue'
import * as api from '@/services/reportCorrections'
vi.mock('@/services/reportCorrections', async original => ({ ...await original<any>(), fetchCorrections: vi.fn(), submitCorrection: vi.fn(), decideCorrection: vi.fn(), fetchCorrectionHistory: vi.fn(), downloadCorrectionHistory: vi.fn() }))
vi.mock('@/services/attachments', () => ({ attachmentObjectUrl: vi.fn() }))
const row = (reportNo = 'TEST-01') => ({ reportNo, mainReportNo: reportNo, reportKind: 'main', client: '虚拟委托单位', project: '建筑光学', status: '已发放' } as any)
const record = (overrides = {}) => ({ id: 12, mainReportNo: 'TEST-01', correctionType: 'external', status: 'pending_approval', reason: '虚拟更正', applicantName: '申请人', createdAt: '2026-10-24T02:00:00', returnMode: 'data_only', canApprove: false,
  applicationAttachment: { id: 1, name: '内部签字.pdf' }, receiptAttachment: { id: 2, name: '甲方回执.pdf' }, ...overrides } as any)
let wrapper: VueWrapper
async function render(records: any[] = [], canRequest = true) {
  vi.mocked(api.fetchCorrections).mockResolvedValue({ rows: records })
  wrapper = mount(Panel, { props: { rows: [row(), row('TEST-02')], loading: false, error: '', canRequest }, attachTo: document.body,
    global: { stubs: { BootstrapModal: { props: ['title'], template: '<section role="dialog"><h2>{{title}}</h2><slot/><slot name="footer"/></section>' }, FeedbackNotice: { props: ['message'], template: '<p role="alert">{{message}}</p>' } } } })
  await flushPromises(); return wrapper
}
async function menu(no = 'TEST-01') { await wrapper.get(`[aria-label="${no} 更多操作"]`).trigger('click'); await flushPromises() }
async function action(text: string) { const button = [...document.querySelectorAll<HTMLButtonElement>('[role=menuitem]')].find(b => b.textContent?.trim() === text)!; button.click(); await flushPromises() }
async function button(text: string) { await wrapper.findAll('button').find(b => b.text() === text)!.trigger('click'); await flushPromises() }
async function file(selector: string, name: string) {
  const input = wrapper.get(selector); Object.defineProperty(input.element, 'files', { value: [new File(['test'], name)], configurable: true }); await input.trigger('change')
}
beforeEach(() => vi.clearAllMocks())
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = '' })
it('uses the server total and sends search, status and page changes to the report list', async () => {
  await render()
  await wrapper.setProps({ total: 31 })
  expect(wrapper.text()).toContain('共 31 条')
  await button('下一页')
  expect(wrapper.emitted('query')?.at(-1)?.[0]).toEqual({ page: 2, pageSize: 12, keyword: '', correctionStatus: '' })
  await wrapper.get('#correction-search').setValue(' 2026V-0150 ')
  await wrapper.get('form').trigger('submit')
  await wrapper.get('#correction-status').setValue('none')
  expect(wrapper.emitted('query')?.at(-1)?.[0]).toEqual({ page: 1, pageSize: 12, keyword: '2026V-0150', correctionStatus: 'none' })
  await wrapper.setProps({ rows: [row('QA-2026V-0150')], total: 1 })
  expect(wrapper.text()).toContain('QA-2026V-0150')
})

it('opens the real three-dot row menu with exactly three requested actions', async () => {
  await render(); await menu()
  expect([...document.querySelectorAll('[role=menuitem]')].map(b => b.textContent?.trim())).toEqual(['查看', '外部更正', '内部更正'])
  await action('查看'); expect(wrapper.text()).toContain('尚未提交更正申请'); await button('查看报告详情与预览')
  expect(wrapper.emitted('view')?.[0]?.[0]).toMatchObject({ reportNo: 'TEST-01' })
})
it('requires two separate documents for external correction and sends the selected report', async () => {
  await render(); await menu('TEST-02'); await action('外部更正')
  await wrapper.get('#correction-reason').setValue('更正日期')
  await file('#correction-receipt', 'receipt.docx')
  expect(wrapper.findAll('button').find(b => b.text() === '提交审批')!.attributes('disabled')).toBeDefined()
  await file('#correction-internal', 'signed.pdf')
  vi.mocked(api.submitCorrection).mockResolvedValue(record())
  await wrapper.get('#correction-form').trigger('submit'); await flushPromises()
  expect(api.submitCorrection).toHaveBeenCalledExactlyOnceWith('TEST-02', 'external', '更正日期', 'data_only', expect.objectContaining({ name: 'signed.pdf' }), expect.objectContaining({ name: 'receipt.docx' }))
})
it('internal correction requires only the internal signed document', async () => {
  await render(); await menu(); await action('内部更正')
  expect(wrapper.find('#correction-receipt').exists()).toBe(false)
  await wrapper.get('#correction-reason').setValue('更正值'); await file('#correction-internal', 'internal.pdf')
  vi.mocked(api.submitCorrection).mockResolvedValue(record())
  await wrapper.get('#correction-form').trigger('submit'); await flushPromises()
  expect(api.submitCorrection).toHaveBeenCalledWith('TEST-01', 'internal', '更正值', 'data_only', expect.any(File), undefined)
})
it('prevents duplicate submit and keeps the selected report bound during save', async () => {
  await render(); await menu(); await action('内部更正')
  await wrapper.get('#correction-reason').setValue('更正值'); await file('#correction-internal', 'internal.pdf')
  let resolve!: (v: any) => void; vi.mocked(api.submitCorrection).mockReturnValue(new Promise(r => { resolve = r }))
  await wrapper.get('#correction-form').trigger('submit'); await wrapper.get('#correction-form').trigger('submit')
  expect(api.submitCorrection).toHaveBeenCalledTimes(1)
  expect(wrapper.findAll('button').find(b => b.text() === '关闭')!.attributes('disabled')).toBeDefined()
  resolve(record()); await flushPromises()
})
it('displays both attachments but no decision buttons without approval authority', async () => {
  await render([record()]); await menu(); await action('查看')
  expect(wrapper.text()).toContain('内部签字.pdf'); expect(wrapper.text()).toContain('甲方回执.pdf')
  expect(wrapper.findAll('button').map(b => b.text())).not.toContain('审批通过')
})
it('approves only after explicit confirmation and refreshes history', async () => {
  await render([record({ canApprove: true })]); await menu(); await action('查看'); await button('审批通过')
  expect(api.decideCorrection).not.toHaveBeenCalled()
  vi.mocked(api.decideCorrection).mockResolvedValue(record({ status: 'approved', correctionReportNo: 'TEST-01GZ' }))
  await button('确认')
  expect(api.decideCorrection).toHaveBeenCalledExactlyOnceWith(12, 'approve', '')
  expect(wrapper.text()).toContain('TEST-01GZ')
})
it('requires a rejection reason and retains input after failed approval', async () => {
  await render([record({ canApprove: true })]); await menu(); await action('查看'); await button('驳回'); await button('确认')
  expect(api.decideCorrection).not.toHaveBeenCalled(); expect(wrapper.text()).toContain('请填写驳回原因')
  await wrapper.get('#correction-note-12').setValue('签字不完整')
  vi.mocked(api.decideCorrection).mockRejectedValue(new Error('权限已收回'))
  await button('确认'); expect(wrapper.text()).toContain('权限已收回'); expect((wrapper.get('#correction-note-12').element as HTMLTextAreaElement).value).toBe('签字不完整')
})
it('blocks additional applications when an active or approved request exists', async () => {
  await render([record()]); await menu()
  expect([...document.querySelectorAll<HTMLButtonElement>('[role=menuitem]')].filter(b => b.disabled).map(b => b.textContent?.trim())).toEqual(['外部更正', '内部更正'])
})
it('disables new applications without request permission', async () => {
  await render([], false); await menu(); expect(document.querySelectorAll('[role=menuitem]:disabled')).toHaveLength(2)
})
it('does not offer another main-report application on a derived GZ row', async () => {
  await render(); await wrapper.setProps({ rows: [{ ...row('TEST-01GZ'), mainReportNo: 'TEST-01', reportKind: 'correction' }] })
  await menu('TEST-01GZ'); expect(document.querySelectorAll('[role=menuitem]:disabled')).toHaveLength(2)
})
it('resets documents, reason and decision state when switching to another report', async () => {
  await render(); await menu(); await action('外部更正'); await wrapper.get('#correction-reason').setValue('旧报告原因'); await file('#correction-internal', 'old.pdf')
  await button('关闭'); await menu('TEST-02'); await action('内部更正')
  expect((wrapper.get('#correction-reason').element as HTMLTextAreaElement).value).toBe('')
  expect(wrapper.findAll('button').find(b => b.text() === '提交审批')!.attributes('disabled')).toBeDefined()
})

it('keeps the original number after internal approval and exposes immutable history', async () => {
  const old = record({ correctionType: 'internal', status: 'approved', correctionReportNo: 'TEST-01', hasHistory: true, blocksNewRequest: false })
  await render([old]); await menu(); expect(document.querySelectorAll('[role=menuitem]:disabled')).toHaveLength(0)
  await action('查看')
  vi.mocked(api.fetchCorrectionHistory).mockResolvedValue({ report: { reportNo: 'TEST-01', client: '更正前客户', status: '已发放', version: 'V1' }, versions: [{ id: 7, versionLabel: 'V1', hasPdf: true, createdAt: '' }], flows: [{ id: 8, hasSignedFile: true, status: 'completed', documentVersionId: 7 }] })
  await button('查看更正前历史')
  expect(api.fetchCorrectionHistory).toHaveBeenCalledExactlyOnceWith(12)
  expect(wrapper.text()).toContain('更正前客户')
  await button('下载历史 V1 PDF')
  expect(api.downloadCorrectionHistory).toHaveBeenCalledExactlyOnceWith(12, 'version', 7)
})
it('reports same-number approval without claiming a new GZ report was created', async () => {
  await render([record({ correctionType: 'internal', canApprove: true })]); await menu(); await action('查看'); await button('审批通过')
  vi.mocked(api.decideCorrection).mockResolvedValue(record({ correctionType: 'internal', status: 'approved', correctionReportNo: 'TEST-01', hasHistory: true }))
  await button('确认')
  expect(wrapper.text()).toContain('TEST-01 沿用原编号进入更改，旧版已留存历史')
})
