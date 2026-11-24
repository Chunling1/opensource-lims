import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { computed, ref } from 'vue'
import { createPinia } from 'pinia'
import { mount, shallowMount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import { reviewFormSchema, type ReviewForm } from './reviewForm'
vi.mock('@/services/reports', async original => ({ ...await original<any>(), fetchReportDetail: vi.fn() }))
vi.mock('@/services/pipeline', async original => ({ ...await original<any>(), fetchEntrustOptions: vi.fn(async () => []), fetchDepartments: vi.fn(async () => []), fetchDerivableReports: vi.fn(async () => []), fetchCapabilityItems: vi.fn(async () => []) }))
import { fetchReportDetail } from '@/services/reports'
import Form from '@/components/PipelineWizard.vue'

const wrappers: any[] = []
afterEach(() => wrappers.splice(0).forEach(w => w.unmount()))
const source = parse(readFileSync('src/modules/pages/ContractReviewPage.vue', 'utf8')).descriptor.scriptSetup!.content
const ast = ts.createSourceFile('review.ts', source, ts.ScriptTarget.Latest, true)
const declarations = ast.statements.filter(n => ts.isVariableStatement(n) &&
  n.declarationList.declarations.some(d => ['sealRequirement', 'requiredCma', 'requiredCnas'].includes(d.name.getText(ast))))
const js = ts.transpileModule(declarations.map(d => d.getText(ast)).join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText

it.each(['CMA + CNAS', 'CNAS', ''])('uses the current request (%s), not the stripped display value, for clickable review choices', async requestedSeal => {
  const detail = ref({ requestedSeal, summary: [{ title: '委托信息', fields: [['盖章要求', '']] }] })
  const flags = new Function('computed', 'detail', js + ';return {requiredCma, requiredCnas}') (computed, detail)
  const model = { items: {}, cma: false, cnas: false, opinion: '' }
  const schema = reviewFormSchema({ idPrefix: 'manual-review', crItems: [], checkedCount: 0,
    requiredCma: flags.requiredCma.value, requiredCnas: flags.requiredCnas.value, reviewDetailLoading: false })
  const view = mount(SchemaForm<ReviewForm>, { props: { schema, model } }); wrappers.push(view)
  for (const mark of ['cma', 'cnas'] as const) {
    const enabled = requestedSeal.includes(mark.toUpperCase())
    expect(view.get('#manual-review-' + mark).attributes('disabled') === undefined).toBe(enabled)
    if (enabled) { await view.get('#manual-review-' + mark).setValue(true); expect(model[mark]).toBe(true) }
  }
})

it('reopens a returned form with the requested marks and preserves manual items without requiring a reason', async () => {
  vi.mocked(fetchReportDetail).mockResolvedValue({ editVersion: 4, requestedSeal: 'CMA + CNAS',
    rawSample: { seal: '', manualCapabilityItems: ['尺寸偏差'], manualCapabilityReason: '', schemeCode: 'QA' },
    summary: [], projectName: '', entrustSnapshot: { entrustNo: 'WT-QA', info: { entrustDate: '2026-10-22' } } } as any)
  const wrapper = shallowMount(Form, { props: { modelValue: false, mode: 'samples', changeReportNo: 'LAB-QA-1' },
    global: { plugins: [createPinia()], config: { warnHandler: () => undefined } } })
  wrappers.push(wrapper)
  const state = (wrapper.vm as any).$.setupState
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  expect(state.s.seal).toBe('CMA + CNAS')
  expect(state.s.manualCapabilityItems).toEqual(['尺寸偏差'])
  const draftValid = state.validateSampleDraft()
  expect(draftValid, state.sampleConfigErrors.join("；")).toBe(true)
  await state.validateCurrentSample()
  expect(state.sampleConfigErrors.join('；')).not.toContain('使用原因')
  const saved = state.buildDetail(state.currentSampleItem())
  expect(saved.rawSample.manualCapabilityItems).toEqual(['尺寸偏差'])
  expect(saved.rawSample.seal).toBe('CMA + CNAS')
  expect(saved.requestedSeal).toBe('CMA + CNAS')
})
