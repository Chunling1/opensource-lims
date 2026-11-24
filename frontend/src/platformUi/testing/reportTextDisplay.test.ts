import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import ReportStandardDisplay from './ReportStandardDisplay.vue'
import ReportTextPreview from './ReportTextPreview.vue'
import { standardPreview, equipmentPreview, type TitleStyle } from './reportTextDisplay'

describe('report text controls', () => {
  const codes = ['GB 1-2024','GB 2-2024','GB 3-2024']
  const names = Object.fromEntries(codes.map((code,i) => [code, `名称${i + 1}`]))
  it('renders independent Chinese, English and unbracketed names with a composite separator', () => {
    expect(standardPreview(codes,names,true,{[codes[0]]:'CN',[codes[1]]:'EN',[codes[2]]:'none'},'EN','；\n')).toBe('GB 1-2024 《名称1》；\nGB 2-2024 <名称2>；\nGB 3-2024 名称3')
    expect(standardPreview(codes,names,false,{},'CN','')).toBe(codes.join(''))
  })
  it('keeps equipment snapshot order and matches report output flags', () => {
    const rows = [{id:1,archiveNo:'A',name:'温度计',spec:'T1'},{id:2,archiveNo:'B',name:'压力计',spec:'P1'}]
    expect(equipmentPreview([2,1],rows,{archiveNo:true,spec:true},'；\n')).toBe('B 压力计 P1；\nA 温度计 T1')
  })
  it('updates individual choices immediately and preserves them after reopening and changing report language', async () => {
    const settings = reactive({ standards:codes,standardShowName:true,standardNames:names,standardTitleStyles:{} as Record<string,TitleStyle>,standardSeparatorText:'；' })
    const props = {settings,options:[],language:'CN',readonly:false}
    const wrapper = mount(ReportStandardDisplay,{props})
    await wrapper.get('#report-standard-style-1').setValue('EN')
    await wrapper.get('#report-standard-style-2').setValue('none')
    expect((wrapper.get('#report-standard-preview').element as HTMLTextAreaElement).value).toContain('GB 2-2024 <名称2>；GB 3-2024 名称3')
    wrapper.unmount()
    const reopened = mount(ReportStandardDisplay,{props:{...props,settings:JSON.parse(JSON.stringify(settings)),language:'EN'}})
    expect((reopened.get('#report-standard-style-2').element as HTMLSelectElement).value).toBe('none')
    reopened.unmount()
  })
  it('disables every setting in readonly state and never emits separator changes', async () => {
    const wrapper = mount(ReportStandardDisplay,{props:{settings:{standards:codes,standardShowName:true},options:[],language:'CN',readonly:true}})
    expect(wrapper.findAll('select,input').every(el => el.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })
  it('builds a separator without a page break and supports undo and empty separators', async () => {
    const wrapper = mount(ReportTextPreview,{props:{id:'test',label:'效果',text:'A；B',separator:'；','onUpdate:separator':(value:string)=>wrapper.setProps({separator:value})}})
    await wrapper.get('select').setValue('custom')
    await wrapper.findAll('button').find(b => b.text()==='添加换行')!.trigger('click')
    expect(wrapper.props('separator')).toBe('；\n')
    await wrapper.findAll('button').find(b => b.text()==='撤销一个')!.trigger('click')
    expect(wrapper.props('separator')).toBe('；')
    await wrapper.findAll('button').find(b => b.text()==='清空')!.trigger('click')
    expect(wrapper.props('separator')).toBe('')
    wrapper.unmount()
  })
})

it('keeps the selected language name when general search returns the other variant',()=>{
 const code='EN 442-1:2014'
 const wrapper=mount(ReportStandardDisplay,{props:{settings:{standards:[code],standardShowName:true,standardNames:{[code]:'Specification for radiators'}},options:[{code,name:'散热器和对流器'}],language:'EN',readonly:false}})
 expect(wrapper.text()).toContain('Specification for radiators')
 expect(wrapper.text()).not.toContain('散热器和对流器')
 wrapper.unmount()
})

it('previews two independent language names and title styles for one code',()=>{
 const code='EN 442-1:2014'
 const wrapper=mount(ReportStandardDisplay,{props:{settings:{standards:[code],standardShowName:true,standardRecords:[{id:101,key:'id:101',code,name:'中文名称'},{id:102,key:'id:102',code,name:'English title'}],standardTitleStyles:{'id:101':'CN','id:102':'EN'}},options:[],language:'CN',readonly:false}})
 expect(wrapper.text()).toContain('统一设置全部 2 条')
 const area=wrapper.find('textarea');expect((area.element as HTMLTextAreaElement).value).toContain(`${code} 《中文名称》；${code} <English title>`)
 expect(wrapper.findAll('select').filter(el=>el.attributes('aria-label')?.includes('书名号'))).toHaveLength(2)
 wrapper.unmount()
})
