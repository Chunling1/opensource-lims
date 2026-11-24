import { afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { reactive } from 'vue'
import { ElAutocomplete } from 'element-plus'
import JudgmentBasisInput from '@/components/JudgmentBasisInput.vue'
import JudgmentStandardDisplay from './JudgmentStandardDisplay.vue'
import { judgmentRows, type StandardDisplaySettings } from './reportTextDisplay'
vi.mock('@/services/quality', () => ({
 loadStandardDisplayNames:vi.fn(async (codes:string[]) => Object.fromEntries(codes.map(code => [code,`名称${code.match(/\d+/)?.[0]}`]))),
 searchJudgmentStandards:vi.fn(async () => ({total:1,rows:[{code:'JJF 1001',name:'通用计量术语、定义'}]})),
}))
let wrapper:VueWrapper
afterEach(() => wrapper?.unmount())
it('uses all standards in preview while paging five choices and retaining settings after reopen', async () => {
  const codes = Array.from({length:7}, (_,i) => `GB ${i+1}-2024`)
  const settings = reactive<StandardDisplaySettings>({standardShowName:true,standardTitleStyles:{},standardSeparatorText:'；\n'})
  const props = {id:'judge',source:codes.join('；'),settings,language:'CN',readonly:false}
  wrapper = mount(JudgmentStandardDisplay,{props}); await flushPromises()
  expect(wrapper.findAll('[id^="judge-style-"]')).toHaveLength(5)
  await wrapper.get('#judge-style-0').setValue('EN')
  await wrapper.get('#judge-search').setValue('GB 7-')
  await wrapper.get('#judge-style-0').setValue('none')
  const text = (wrapper.get('#judge-preview').element as HTMLTextAreaElement).value
  expect(text).toContain('GB 1-2024 <名称1>')
  expect(text).toContain('GB 7-2024 名称7')
  expect(text.split('；\n')).toHaveLength(7)
  const saved = JSON.parse(JSON.stringify(settings)); wrapper.unmount()
  wrapper = mount(JudgmentStandardDisplay,{props:{...props,settings:saved,language:'EN'}}); await flushPromises()
  expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value).toContain('GB 7-2024 名称7')
  await wrapper.get('#judge-show-name').setValue(false)
  expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value).toBe(codes.join('；\n'))
})
it('keeps explicit names, handwritten criteria and slash without inventing standards', () => {
  expect(judgmentRows('ISO 1234:2024 <Doors>；按委托要求；/')).toEqual({codes:['ISO 1234:2024','按委托要求','/'],names:{'ISO 1234:2024':'<Doors>'}})
})
it('readonly choices do not mutate persisted settings', async () => {
  const settings = {standardShowName:true,standardTitleStyles:{},standardSeparatorText:'；'}
  wrapper = mount(JudgmentStandardDisplay,{props:{id:'judge',source:'GB 1-2024',settings,language:'CN',readonly:true}})
  await flushPromises()
  expect(wrapper.findAll('input,select').every(control => control.attributes('disabled') !== undefined)).toBe(true)
  expect(settings.standardTitleStyles).toEqual({})
})

it('shows both selected same-code names with independent title settings', async()=>{
 const code='EN 442-1:2014',records=[{id:11,key:'id:11',code,name:'散热器'},{id:12,key:'id:12',code,name:'Radiators'}]
 const settings={standardShowName:true,standardTitleStyles:{'id:11':'CN','id:12':'EN'} as any,standardSeparatorText:'；'}
 wrapper=mount(JudgmentStandardDisplay,{props:{id:'judge',source:code,records,settings,language:'CN',readonly:false}});await flushPromises()
 expect(wrapper.findAll('[id^="judge-style-"]')).toHaveLength(2)
 expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value).toBe(`${code} 《散热器》；${code} <Radiators>`)
})


it('keeps judgment order independently from detection records and handwritten criteria', async () => {
 const records=[{id:2,key:'id:2',code:'GB/T 5237.1-2017',name:'型材'},{id:1,key:'id:1',code:'GB/T 3190-2020',name:'成分'}]
 const settings={standardShowName:true,standardTitleStyles:{},standardSeparatorText:'；'}
 wrapper=mount(JudgmentStandardDisplay,{props:{id:'judge',source:'GB/T 3190-2020；按委托要求；GB/T 5237.1-2017',records,settings,language:'CN',readonly:false}})
 await flushPromises()
 expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value).toBe('GB/T 3190-2020 《成分》；按委托要求；GB/T 5237.1-2017 《型材》')
 await wrapper.setProps({source:'GB/T 3190-2020《登记名称》；按委托要求；GB/T 5237.1-2017'})
 await flushPromises()
 expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value).toBe('GB/T 3190-2020 《登记名称》；按委托要求；GB/T 5237.1-2017 《型材》')
 expect(records.map(row=>row.id)).toEqual([2,1])
})

it('adds each library or handwritten standard as one item and preserves punctuation after reopening',async()=>{
 const manual='GB/T 31433-2015 建筑幕墙、门窗通用技术条件'
 const selected='JJF 1001 《通用计量术语、定义》'
 const editor=mount(JudgmentBasisInput,{props:{modelValue:undefined,legacy:''},global:{components:{ElAutocomplete}}})
 const update=()=>editor.emitted('update:modelValue')!.at(-1)![0] as string[]
 try {
  await editor.get('input').setValue(manual)
  expect(editor.emitted('update:modelValue')).toBeUndefined()
  await editor.findAll('button').find(button=>button.text()==='添加')!.trigger('click')
  expect(update()).toEqual([manual])
  await editor.setProps({modelValue:update()})
  await editor.get('input').setValue('JJF')
  await flushPromises()
  await editor.findAll('button').find(button=>button.text()===selected)!.trigger('click')
  expect(update()).toEqual([manual,selected])
  await editor.setProps({modelValue:update()})
  await editor.get('[aria-label="编辑第 1 条判定标准"]').trigger('click')
  await editor.get('input').setValue(manual+'；附录 A')
  await editor.get('input').trigger('keydown',{key:'Enter'})
  const persisted=JSON.parse(JSON.stringify(update()))
  expect(persisted).toEqual([manual+'；附录 A',selected])
  await editor.setProps({modelValue:persisted})
  await editor.get('[aria-label="移除第 2 条判定标准"]').trigger('click')
  expect(update()).toEqual([manual+'；附录 A'])
  wrapper=mount(JudgmentStandardDisplay,{props:{id:'judge',source:persisted,settings:{standardShowName:true},language:'CN',readonly:false}})
  expect((wrapper.get('#judge-preview').element as HTMLTextAreaElement).value)
   .toBe('GB/T 31433-2015 《建筑幕墙、门窗通用技术条件；附录 A》；JJF 1001 《通用计量术语、定义》')
 } finally {editor.unmount()}
})
