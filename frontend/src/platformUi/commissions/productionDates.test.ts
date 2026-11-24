import { expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import Editor from '@/components/ProductionDatesEditor.vue'
import { productionDatesIssues, productionDatesText, singleProductionDate, type ProductionDateRow } from '@/composables/productionDates'
import { sampleDateOrderErrors, savedSampleDates } from '@/composables/sampleDateRules'
vi.mock('@/stores/session', () => ({useSessionStore: () => ({canOverrideWorkflowDate: false})}))
const rows: ProductionDateRow[] = [
  {name:'室外机',precision:'day',value:'2026-10-20',note:'以铭牌为准'},
  {name:'室内机',precision:'month',value:'2026-09',note:''},
]
it('infers missing precision when reopening historical rows', () => {
  for (const [value, precision] of [['2026-10-20','day'], ['2026-10','month'], ['未标注','custom'], ['','custom']]) {
    expect(singleProductionDate(value).precision).toBe(precision)
  }
  const w = mount(Editor, {props:{rows:[{name:'室内机',value:'2026-10',note:''} as ProductionDateRow]},global:{stubs:{ProductionDatePicker:true}}})
  expect(w.findComponent({name:'ProductionDatePicker'}).props('datePrecision')).toBe('month')
  expect(w.text()).not.toContain('格式无效')
  w.unmount()
})
it('does not revive an explicitly cleared form date from the display summary', () => {
  expect(savedSampleDates({rawSample:{sendDate:''},summary:[{fields:[['送样日期','2026-10-20']]}]}).sendDate).toBe('')
  expect(savedSampleDates({summary:[{fields:[['送样日期','2026-10-20']]}]}).sendDate).toBe('2026-10-20')
  const legacy = [{name:'室内机',value:'2026-10-20',note:''} as ProductionDateRow]
  expect(productionDatesIssues(legacy,{sendDate:'2026-10-19'}).errors).toContain('室内机：送样日期不得早于生产日期')
})
it('compares every component and reports the correct name without inventing a day', () => {
  expect(sampleDateOrderErrors({productionDates:rows,produceDate:'/',sendDate:'2026-10-19'})).toContain('室外机：送样日期不得早于生产日期')
  const issues = productionDatesIssues(rows,{sendDate:'2026-09-10'})
  expect(issues.warnings).toContain('室内机：生产月份与送样日期同月，无法确定具体先后，请核对')
  expect(rows[1]!.value).toBe('2026-09')
  expect(productionDatesIssues([{...rows[0]!,precision:'custom',value:'未标注'}],{}).warnings[0]).toContain('无法校验')
  expect(productionDatesIssues([{...rows[0]!,precision:'custom',value:'生产于2026-10-20'}],{}).errors).toHaveLength(1)
})
it('keeps bilingual labels, month precision and literal notes in the preview', () => {
  expect(productionDatesText(rows,'CN',true)).toBe('室外机：2026年10月20日（以铭牌为准）\n室内机：2026年9月')
  expect(productionDatesText(rows,'EN',true)).toBe('Outdoor unit: 20 Oct 2026 (以铭牌为准)\nIndoor unit: Sep 2026')
})
it('edits, splits, changes precision, adds, deletes and reopens without losing existing values', async () => {
  let saved: ProductionDateRow[] = []
  const Host=defineComponent({components:{Editor},setup(){const value=ref('2026-10-20'),items=ref<ProductionDateRow[]>([]);return {value,items,capture:(v:ProductionDateRow[])=>{saved=v;items.value=v}}},template:'<Editor v-model="value" :rows="items" @update:rows="capture" />'})
  const w=mount(Host, {global:{stubs:{WorkflowDatePicker:true}}})
  await w.findAll('button').find(x=>x.text()==='室内机／室外机')!.trigger('click')
  expect(saved.map(x=>[x.name,x.value])).toEqual([['室外机','2026-10-20'],['室内机','']])
  await w.findAll('select')[1]!.setValue('custom')
  expect(saved[1]!.precision).toBe('custom')
  await w.get('[aria-label="生产日期替代字符"]').setValue('未标注')
  await w.get('[aria-label="第2项说明"]').setValue('铭牌缺失')
  expect(saved[1]).toMatchObject({precision:'custom',value:'未标注',note:'铭牌缺失'})
  await w.findAll('button').find(x=>x.text().includes('添加一项'))!.trigger('click')
  expect(saved).toHaveLength(3)
  await w.get('[aria-label="删除第3项"]').trigger('click')
  w.unmount()
  const reopen=mount(Editor,{props:{rows:saved,disabled:true},global:{stubs:{WorkflowDatePicker:true}}})
  expect((reopen.get('[aria-label="生产日期替代字符"]').element as HTMLInputElement).value).toBe('未标注')
  expect(reopen.findAll('button')).toHaveLength(0)
  expect(reopen.text()).toContain('铭牌缺失')
  reopen.unmount()
})
