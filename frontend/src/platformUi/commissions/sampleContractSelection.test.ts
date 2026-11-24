import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises, type VueWrapper } from '@vue/test-utils'
import Form from '@/components/PipelineWizard.vue'
import { ElMessage } from 'element-plus'

vi.mock('@/services/pipeline', async original => ({
  ...await original<typeof import('@/services/pipeline')>(),
  fetchEntrustOptions: vi.fn().mockResolvedValue([]),
  fetchContractSelectionPage: vi.fn().mockResolvedValue({ rows: [] }),
  fetchHandleDepartments: vi.fn().mockResolvedValue({ rows: [], current: 'QA' }),
  fetchDepartments: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/stores/session', () => ({ useSessionStore: () => ({ dataScope: { department: 'QA' }, userName: 'QA', account: 'qa', can: () => true, canAction: () => true }) }))
vi.mock('element-plus', async original => ({ ...await original<typeof import('element-plus')>(), ElMessage: { error: vi.fn(), warning: vi.fn(), success: vi.fn() } }))
let wrapper: VueWrapper
const source = () => ({ id: 1, entrustNo: 'WT-ORIGINAL', contractNo: 'VIRTUAL', projectName: '占号项目', projectType: '虚拟框架', info: { entrustDate: '2026-01-01' } })
const target = () => ({ agreementNo: 'ACTUAL', projectName: '实际项目', erpType: '标准合同', projectCode: 'P-ACTUAL', client: '实际甲方' })
async function start(props = {}) {
  wrapper = shallowMount(Form, { props: { modelValue: false, mode: 'samples', pageView: true, ...props }, global: { directives: { loading: {} }, config: { warnHandler: () => undefined } } })
  const x = (wrapper.vm as any).$.setupState
  x.entrustOptions = [source()]; x.sampleEntrustNo = 'WT-ORIGINAL'; x.applySampleEntrustOption(source())
  await flushPromises()
  return x
}
beforeEach(() => vi.clearAllMocks())
afterEach(() => wrapper?.unmount())

it('ordinary new sample can select a different contract without mutating the source entrust', async () => {
  const x = await start()
  expect(x.administratorEditing).toBe(false)
  x.onSampleContractSelected(target())
  expect(x.sampleEntrust.contractNo).toBe('ACTUAL')
  expect(x.sampleEntrust.projectType).toBe('标准合同')
  expect(x.sampleEntrust.contractPartyA).toBe('实际甲方')
  expect(x.sampleEntrust.entrustDate).toBe('2026-01-01')
  expect(x.sampleEntrust.entrustNo).toBe('WT-ORIGINAL')
  expect(x.entrustOptions[0].contractNo).toBe('VIRTUAL')
  expect(x.sampleEntrustPayload().contractNo).toBe('ACTUAL')
  expect(x.sampleEntrustPayload().sourceEntrustNo).toBe('WT-ORIGINAL')
})

it('preserves old subprojects and warns instead of silently dropping amounts', async () => {
  const x = await start()
  x.s.subItems = [{ source: 'erp', contractNo: 'VIRTUAL', code: 'OLD', amount: '500' }]
  x.onSampleContractSelected(target())
  expect(x.s.subItems[0].amount).toBe('500')
  expect(ElMessage.warning).toHaveBeenCalledWith(expect.stringContaining('已保留'))
})

it('same selection does not overwrite an edited project name and clear does not break the association', async () => {
  const x = await start()
  x.onSampleContractSelected(target()); x.sampleEntrust.projectName = '用户工程名称'
  x.onSampleContractSelected(target())
  expect(x.sampleEntrust.projectName).toBe('用户工程名称')
  x.onSampleContractSelected(undefined)
  expect(x.sampleEntrust.contractNo).toBe('ACTUAL')
})

it('read only, submitting and completed registration cannot switch', async () => {
  const x = await start()
  x.submitting = true; x.onSampleContractSelected(target()); expect(x.sampleEntrust.contractNo).toBe('VIRTUAL')
  x.submitting = false; x.activeSampleRegState = '登记完成'
  x.onSampleContractSelected(target()); expect(x.sampleEntrust.contractNo).toBe('VIRTUAL')
  x.activeSampleRegState = '登记中'; await wrapper.setProps({ readOnly: true })
  x.onSampleContractSelected(target()); expect(x.sampleEntrust.contractNo).toBe('VIRTUAL')
})

it('return-to-entrust change can switch and choosing a different entrust clears the stale picker', async () => {
  const x = await start({ changeReportNo: 'REPORT-UNCHANGED' })
  x.activeSampleRegState = '登记完成'; x.onSampleContractSelected(target())
  expect(x.sampleEntrust.contractNo).toBe('ACTUAL')
  expect(x.effectiveReportNo).toBe('REPORT-UNCHANGED')
  x.applySampleEntrustOption(source())
  expect(x.sampleSelectedContract).toBeUndefined()
  expect(x.sampleEntrust.contractNo).toBe('VIRTUAL')
})
