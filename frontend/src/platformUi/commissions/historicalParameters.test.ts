import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
vi.mock('@/services/pipeline', async original => ({
  ...await original<any>(), fetchCapabilityItems: vi.fn(async () => []),
}))
import { fetchCapabilityItems } from '@/services/pipeline'
import Form from '@/components/PipelineWizard.vue'
import Picker from '@/components/CapabilityPicker.vue'

const history = { id: 91, itemName: '历史参数', standardCode: 'GB/TEST', address: '虚拟地址', objectName: '虚拟对象' }
const wrappers: ReturnType<typeof shallowMount>[] = []
function setup(readOnly = false) {
  const wrapper = shallowMount(Form, { props: { modelValue: false, mode: 'samples', readOnly },
    global: { plugins: [createPinia()], config: { warnHandler: () => undefined } } })
  wrappers.push(wrapper)
  const state = (wrapper.vm as any).$.setupState
  state.stdOptions = [{ id: 1, code: 'GB/TEST', name: '标准', singleList: true, sites: ['北京'] }]
  Object.assign(state.s, { testBases: ['GB/TEST'], testBasis: 'GB/TEST', locationWorkflowVersion: 1,
    testDept: '虚拟部门', capabilityEntryIds: [91], capabilitySnapshots: [{ ...history }],
    testItemOrder: [{ kind: 'library', id: 91 }], projectList: ['历史参数'], project: '历史参数',
    testLocation: '虚拟地址', actualTestLocations: ['虚拟地址'] })
  return state
}
beforeEach(() => vi.mocked(fetchCapabilityItems).mockReset().mockResolvedValue([]))
afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))

it.each([false, true])('preserves missing historical choices, output text and addresses (readonly=%s)', async readOnly => {
  const state = setup(readOnly)
  await state.loadCapabilityItems()
  const saved = state.currentSampleItem()
  expect(saved.capabilityEntryIds).toEqual([91])
  expect(saved.capabilitySnapshots).toEqual([history])
  expect(saved.testItemOrder).toEqual([{ kind: 'library', id: 91 }])
  expect(saved.commissionText.items).toBe('历史参数')
  expect(saved.actualTestLocations).toEqual(['虚拟地址'])
  expect(state.unavailableCapabilityLabels).toEqual(['历史参数（GB/TEST）'])
  await state.validateCurrentSample()
  expect(state.sampleConfigErrors.join('；')).toContain('当前不可用的历史参数')
})

it('keeps choices when no standards are available, and when a query fails', async () => {
  const state = setup()
  state.s.testBases = []; state.s.testBasis = ''
  await state.loadCapabilityItems()
  expect(state.s.capabilityEntryIds).toEqual([91])
  expect(state.unavailableCapabilityIds).toEqual([91])
  state.s.testBases = ['GB/TEST']; state.s.testBasis = 'GB/TEST'
  vi.mocked(fetchCapabilityItems).mockRejectedValueOnce(new Error('offline'))
  await state.loadCapabilityItems()
  expect(state.currentSampleItem().capabilitySnapshots).toEqual([history])
  expect(state.s.testLocation).toBe('虚拟地址')
  expect(state.capabilityError).toContain('读取失败')
})

it('can explicitly remove the historical choice and then recompute inherited locations', async () => {
  const state = setup()
  Object.assign(state.s, { manualCapabilityItems: ['库外项目'],
    manualParameterLocations: { 库外项目: { mode: 'library', addresses: [] } } })
  await state.loadCapabilityItems()
  expect(state.s.testLocation).toBe('虚拟地址')
  state.removeTestItem('library:91')
  expect(state.currentSampleItem().capabilitySnapshots).toEqual([])
  expect(state.unavailableCapabilityIds).toEqual([])
  expect(state.parameterLocationError).toContain('需先选择')
  expect(state.s.actualTestLocations).toEqual([])
})

it('clears the unavailable state only when the current query returns the parameter', async () => {
  const state = setup()
  await state.loadCapabilityItems()
  vi.mocked(fetchCapabilityItems).mockResolvedValueOnce([{ ...history, address: '当前地址' }] as any)
  await state.loadCapabilityItems()
  expect(state.unavailableCapabilityIds).toEqual([])
  expect(state.s.testLocation).toBe('当前地址')
})

it('clears a previous read error after the picker confirms a current selection', async () => {
  const state = setup()
  state.capabilityError = '读取失败'
  state.capabilityOptions = [{ ...history, address: '当前地址' }]
  await state.confirmCapabilitySelection([91], [], [{ kind: 'library', id: 91 }], {})
  expect(state.capabilityError).toBe('')
  expect(state.s.testLocation).toBe('当前地址')
})

it('shows historical names in the picker without treating snapshots as authorization, and cancels removal', async () => {
  const wrapper = shallowMount(Picker, { props: { modelValue: true, selectedIds: [91],
    rows: [], selectedRows: [], historyRows: [history] as any, total: 0, standards: ['GB/TEST'], contextKey: 'sample' },
  global: { config: { warnHandler: () => undefined } } })
  wrappers.push(wrapper)
  const state = (wrapper.vm as any).$.setupState
  expect(state.draftRows[0].label).toBe('历史参数')
  expect(state.unresolved).toBe(true)
  expect(state.libraryAddresses).toEqual([])
  state.confirm()
  expect(wrapper.emitted('confirm')).toBeUndefined()
  state.remove('library:91')
  await wrapper.setProps({ modelValue: false })
  await wrapper.setProps({ modelValue: true })
  expect(state.draftRows[0].label).toBe('历史参数')
  state.remove('library:91'); state.confirm()
  expect(wrapper.emitted('confirm')![0][0]).toEqual([])
})
