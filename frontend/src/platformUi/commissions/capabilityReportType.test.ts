import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
vi.mock('@/services/pipeline', async original => ({
  ...await original<any>(), fetchCapabilityItems: vi.fn(async () => []),
  fetchCapabilityPage: vi.fn(async () => ({ rows: [], total: 0 })),
}))
vi.mock('@/services/quality', async original => ({
  ...await original<any>(), searchStdLib: vi.fn(async () => []),
  searchStdLibPage: vi.fn(async () => ({ rows: [], total: 0, page: 1 })),
}))
import { fetchCapabilityItems, fetchCapabilityPage } from '@/services/pipeline'
import { searchStdLib, searchStdLibPage } from '@/services/quality'
import Form from '@/components/PipelineWizard.vue'

const wrappers: ReturnType<typeof shallowMount>[] = []
const standard = { id: 1, code: 'JJG 229-2010', name: '虚拟校准标准', capabilityTypes: ['校准'] }
function setup(reportType = '校准报告', testCategory = '委托') {
  const w = shallowMount(Form, { props: { modelValue: false, mode: 'samples' },
    global: { plugins: [createPinia()], config: { warnHandler: () => undefined } } })
  wrappers.push(w)
  const s = (w.vm as any).$.setupState
  Object.assign(s.s, { reportType, testCategory, testDept: '虚拟校准部', sendDate: '2026-10-27',
    testBases: [standard.code], testBasis: standard.code, capabilityEntryIds: [91] })
  return s
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(searchStdLib).mockResolvedValue([standard] as any)
})
afterEach(() => wrappers.splice(0).forEach(w => w.unmount()))

it('forwards picker filters only to catalog results, not selected-row hydration', async () => {
  const s=setup(); s.capabilityDialogOpen=true
  await s.loadCapabilityCatalog({keyword:'温度',locationFilter:'测试地点',accreditationFilter:'CMA',page:1,size:20,selectedStandardsOnly:true})
  expect(fetchCapabilityPage).toHaveBeenLastCalledWith(expect.objectContaining({keyword:'温度',locationFilter:'测试地点',accreditationFilter:'CMA',page:1}),expect.any(AbortSignal))
  const hydration=vi.mocked(fetchCapabilityItems).mock.lastCall?.[0]
  expect(hydration).toMatchObject({ids:[91]})
  expect(hydration).not.toHaveProperty('accreditationFilter')
  expect(hydration).not.toHaveProperty('locationFilter')
})

it.each([
  ['校准报告', '委托', '校准'], ['校准报告', '型式检验', '校准'],
  ['检验报告', '委托', '检验'], ['检验（检查）报告', '校准', '检验'],
  ['产品报告', '校准', '检测'], ['工程报告', '委托', '检测'], ['抽样报告', '抽样检测', '检测'],
])('does not use report format %s or category %s to filter any query path', async (format, category, kind) => {
  const s = setup(format, category)
  await s.searchStd('JJG')
  expect(searchStdLib).toHaveBeenLastCalledWith('JJG', '虚拟校准部', { capabilityOnly: false })
  s.stdOptions = []
  await s.hydrateStandardOptions([standard.code])
  expect(searchStdLib).toHaveBeenLastCalledWith(standard.code, '虚拟校准部', {})
  await s.queryBasisStandards()
  expect(vi.mocked(searchStdLibPage).mock.lastCall?.[2]).not.toHaveProperty('capabilityType')
  await s.loadCapabilityItems()
  expect(vi.mocked(fetchCapabilityItems).mock.lastCall?.[0]).toMatchObject({ department: '虚拟校准部', ids: [91] })
  s.capabilityDialogOpen = true
  await s.loadCapabilityCatalog()
  expect(vi.mocked(fetchCapabilityPage).mock.lastCall?.[0]).toMatchObject({ department: '虚拟校准部' })
  for (const call of [...vi.mocked(fetchCapabilityPage).mock.calls, ...vi.mocked(fetchCapabilityItems).mock.calls]) {
    expect(call[0]).not.toHaveProperty('capabilityType'); expect(call[0]).not.toHaveProperty('date')
  }
})

it('discards a late detection response after switching to calibration', async () => {
  const s = setup('产品报告')
  let finish!: (rows: any) => void
  vi.mocked(searchStdLib).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const old = s.searchStd('JJG')
  s.s.reportType = '校准报告'
  await s.searchStd('JJG')
  finish([{ ...standard, capabilityTypes: ['检测'] }])
  await old
  expect(s.stdOptions[0].capabilityTypes).toEqual(['校准'])
})

it('preserves metadata and selections when report format or category changes', async () => {
  const s = setup('产品报告')
  s.stdOptions = [{ ...standard, capabilityTypes: ['校准'] }]
  s.basisPageRows = [...s.stdOptions]
  s.basisTotal = 1
  s.s.reportType = '校准报告'
  expect(s.stdOptions).toHaveLength(1)
  expect(s.basisPageRows).toHaveLength(1)
  expect(s.s.testBases).toEqual([standard.code])
  expect(s.s.capabilityEntryIds).toEqual([91])
  await s.hydrateStandardOptions([standard.code])
  expect(s.stdOptions[0].capabilityTypes).toEqual(['校准'])
  s.s.testCategory = '型式检验'
  expect(s.stdOptions[0].capabilityTypes).toEqual(['校准'])
})
