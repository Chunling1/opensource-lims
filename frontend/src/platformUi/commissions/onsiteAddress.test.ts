import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { expect, it } from 'vitest'
import { actualParameterAddresses } from '@/data/parameterLocations'

// Execute the owning controller, with local catalog data and no network.
const script = parse(readFileSync('src/modules/components/PipelineWizard.vue', 'utf8')).descriptor.scriptSetup!.content
const tree = ts.createSourceFile('wizard.ts', script, ts.ScriptTarget.Latest, true)
it('retains selected standards, parameters and order while toggling address mode in both directions', async () => {
  const s: any = { isOnsiteTesting: true, onsiteTestLocation: '客户现场地址', locationWorkflowVersion: 1,
    testBases: ['GB-OTHER', 'GB-FIRST'], capabilityEntryIds: [8, 3], projectList: ['参数乙', '参数甲'],
    testItemOrder: [{ kind: 'library', id: 8 }, { kind: 'library', id: 3 }],
    capabilitySnapshots: [], standardJudge: '保留判定依据', manualCapabilityItems: [] }
  const before = structuredClone(s)
  const deps = { s, actualParameterAddresses, unavailableCapabilityIds: { value: [] }, capabilityError: { value: '' },
    parameterLocationError: { value: '' }, capabilityOptions: { value: [{ id: 8, itemName: '参数乙', address: '实验室乙' }, { id: 3, itemName: '参数甲', address: '实验室甲' }] } }
  const names = ['onOnsiteTestingChange', 'syncParameterLocations']
  const source = tree.statements.filter(n => ts.isFunctionDeclaration(n) && names.includes(n.name?.text || '')).map(n => n.getText(tree)).join('\n')
  const js = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const toggle = new Function(...Object.keys(deps), js + ';return onOnsiteTestingChange')(...Object.values(deps))
  await toggle()
  expect(s.actualTestLocations).toEqual(['客户现场地址'])
  s.isOnsiteTesting = false
  await toggle()
  expect(s.actualTestLocations).toEqual(['实验室乙', '实验室甲'])
  for (const key of ['testBases', 'capabilityEntryIds', 'testItemOrder', 'projectList', 'standardJudge']) expect(s[key]).toEqual(before[key])
})

it('allows a manually entered onsite address even when the library has no laboratory address', () => {
  const rows = [{ itemName: '温差', address: '' }]
  const context = { isOnsiteTesting: true, onsiteTestLocation: ' 客户现场地址 ', manualCapabilityItems: [], manualTestLocation: '' }
  expect(actualParameterAddresses(rows, context)).toEqual(['客户现场地址'])
  expect(actualParameterAddresses(rows, { ...context, isOnsiteTesting: false })).toEqual([])
})
