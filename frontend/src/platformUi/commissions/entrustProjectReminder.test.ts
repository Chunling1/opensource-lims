import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises, type VueWrapper } from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
import { ElMessageBox } from 'element-plus'

const api = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), complete: vi.fn(), contracts: vi.fn() }))
vi.mock('@/services/pipeline', async original => ({
  ...await original<typeof import('@/services/pipeline')>(),
  createEntrust: api.create, updateEntrust: api.update, completeEntrust: api.complete,
  fetchContractSelectionPage: api.contracts, fetchNextEntrustNo: vi.fn().mockResolvedValue('WT-QA'),
  fetchHandleDepartments: vi.fn().mockResolvedValue({ rows: [], current: 'QA' }),
  fetchDepartments: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/services/businessCorrection', () => ({ rememberCorrection: vi.fn().mockResolvedValue(undefined) }))
vi.mock('@/stores/session', () => ({ useSessionStore: () => ({ dataScope: { department: 'QA' }, userName: 'QA', account: 'qa', can: () => true, canAction: () => true }) }))
vi.mock('element-plus', async original => ({ ...await original<typeof import('element-plus')>(), ElMessage: { error: vi.fn(), warning: vi.fn(), success: vi.fn() }, ElMessageBox: { confirm: vi.fn() } }))
let wrapper: VueWrapper
const contract = () => ({ agreementNo: 'KD-QA', projectName: '自动带入项目', client: '客户', erpType: '虚拟框架', info: { fromErp: '1' } })
async function start(editEntrust?: any) {
  wrapper = shallowMount(Form, { props: { modelValue: false, mode: 'entrust', pageView: true, editEntrust }, global: { directives: { loading: {} }, config: { warnHandler: () => undefined } } })
  await wrapper.setProps({ modelValue: true }); await flushPromises()
  const x = (wrapper.vm as any).$.setupState
  if (!editEntrust) x.onContractSelected(contract())
  Object.assign(x.f, { handleDept: 'QA', handler: 'QA', entrustDate: '2026-11-02' })
  return x
}
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear()
  api.contracts.mockResolvedValue({ rows: [contract()] })
  api.create.mockResolvedValue({ id: 1, entrustNo: 'WT-QA', status: '委托中' })
  api.update.mockResolvedValue({ id: 1, entrustNo: 'WT-QA', status: '委托中' })
  api.complete.mockResolvedValue({ id: 1, entrustNo: 'WT-QA', status: '委托完成' })
  vi.mocked(ElMessageBox.confirm).mockResolvedValue('confirm')
})
afterEach(() => wrapper?.unmount())

it.each(['saveEntrust', 'completeEntrustRegistration'])('%s waits for confirmation and cancellation makes no write', async method => {
  const x = await start()
  let reject!: (reason: string) => void
  vi.mocked(ElMessageBox.confirm).mockImplementationOnce(() => new Promise((_, r) => { reject = r }))
  const pending = x[method](); await flushPromises()
  expect(ElMessageBox.confirm).toHaveBeenCalledWith(expect.stringContaining('二维码核验页'), '请确认项目名称', expect.objectContaining({ confirmButtonText: '继续保存', cancelButtonText: '返回修改' }))
  expect(api.create).not.toHaveBeenCalled()
  await x[method](); expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
  reject('cancel'); await pending
  expect(api.create).not.toHaveBeenCalled(); expect(api.complete).not.toHaveBeenCalled()
  expect(x.submitting).toBe(false); expect(x.f.projectName).toBe('自动带入项目')
})

it.each(['saveEntrust', 'completeEntrustRegistration'])('%s allows keeping the original name after confirmation', async method => {
  const x = await start(); await x[method]()
  expect(api.create).toHaveBeenCalledTimes(1)
  expect(api.create.mock.calls[0][0].projectName).toBe('自动带入项目')
  expect(api.complete).toHaveBeenCalledTimes(method === 'completeEntrustRegistration' ? 1 : 0)
})

it.each(['实际工程名', '/', ''])('does not warn for an edited value %j', async name => {
  const x = await start(); x.f.projectName = name; await x.saveEntrust()
  expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  expect(api.create.mock.calls[0][0].projectName).toBe(name)
})

it('does not warn for a local contract or an empty source name', async () => {
  const x = await start(); x.onContractSelected({ ...contract(), info: {} }); await x.saveEntrust()
  x.onContractSelected({ ...contract(), projectName: '' }); await x.saveEntrust()
  expect(ElMessageBox.confirm).not.toHaveBeenCalled()
})

it('checks a reopened unmodified entrust against the loaded Erp contract', async () => {
  const x = await start({ id: 1, entrustNo: 'WT-QA', contractNo: 'KD-QA', projectName: '自动带入项目', client: '客户', info: {} })
  await x.saveEntrust()
  expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1); expect(api.update).toHaveBeenCalledTimes(1)
})

it('resolves a copied contract and compares the value rather than whether the user touched the field', async () => {
  const x = await start(); x.copyFromEntrust({ entrustNo: 'WT-COPY', projectName: '自动带入项目', info: { contractNo: 'OTHER' } })
  api.contracts.mockResolvedValue({ rows: [{ ...contract(), agreementNo: 'OTHER' }] })
  x.f.projectName = '修改'; x.f.projectName = ' 自动带入项目 '
  await x.saveEntrust()
  expect(api.contracts).toHaveBeenLastCalledWith('', 1, undefined, 'OTHER')
  expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
})

it('does not submit a closed form after a delayed confirmation', async () => {
  const x = await start(); let resolve!: (value: string) => void
  vi.mocked(ElMessageBox.confirm).mockImplementationOnce(() => new Promise(r => { resolve = r }))
  const pending = x.saveEntrust(); await flushPromises()
  await wrapper.setProps({ modelValue: false }); resolve('confirm'); await pending
  expect(api.create).not.toHaveBeenCalled()
})
