import { describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import OrderedList from '@/components/OrderedSelectionList.vue'
import Picker from '@/components/CapabilityPicker.vue'

const rows = [1, 2].map(id => ({ id, itemName: id === 1 ? '传热系数' : '气密性能', standardCode: 'GB/T 1000', objectName: '虚拟样品', address: id===1 ? '虚拟地址甲' : '虚拟地址乙', accreditation: id===1 ? 'CMA' : 'CNAS' }))
const mountPicker = () => shallowMount(Picker, {
  props: { modelValue: true, selectedIds: [1], rows: rows as any, standards: ['GB/T 1000'], contextKey: 'sample-a' },
  global: { config: { warnHandler: () => undefined } },
})

it('combines accreditation, location and keyword without losing selected parameters', async () => {
  const wrapper=mountPicker(), state=(wrapper.vm as any).$.setupState
  state.accreditationFilter='CNAS'
  expect(state.filtered.map((r:any)=>r.id)).toEqual([2])
  state.locationFilter='虚拟地址甲'
  expect(state.filtered).toHaveLength(0)
  state.locationFilter='虚拟地址乙'; state.keyword='气密'
  expect(state.filtered.map((r:any)=>r.id)).toEqual([2])
  state.toggle(2,true); state.accreditationFilter='CMA'; state.keyword=''; state.locationFilter=''
  expect(state.filtered.map((r:any)=>r.id)).toEqual([1])
  state.confirm(); expect(wrapper.emitted('confirm')!.at(-1)![0]).toEqual([1,2])
  await wrapper.setProps({modelValue:false}); await wrapper.setProps({modelValue:true})
  expect(state.accreditationFilter).toBe('')
  wrapper.unmount()
})

it('sends accreditation with the server page and retains complete location choices', async () => {
  const wrapper=shallowMount(Picker,{props:{modelValue:true,selectedIds:[1],selectedRows:[rows[0]] as any,
    rows:rows as any,total:41,catalogLocations:['虚拟地址甲','虚拟地址乙'],standards:['GB/T 1000'],contextKey:'qualifications'},
    global:{stubs:{BootstrapModal:{template:'<div><slot name="toolbar"/><slot/><slot name="footer"/></div>'}},config:{warnHandler:()=>undefined}}})
  const state=(wrapper.vm as any).$.setupState
  state.goPage(3)
  await wrapper.find('#sample-capability-accreditation').setValue('CNAS')
  expect(wrapper.emitted('query')!.at(-1)).toEqual([{keyword:'',locationFilter:'',accreditationFilter:'CNAS',page:1,size:20,selectedStandardsOnly:true}])
  await wrapper.find('#sample-capability-location').setValue('虚拟地址乙')
  expect(wrapper.emitted('query')!.at(-1)![0]).toMatchObject({accreditationFilter:'CNAS',locationFilter:'虚拟地址乙',page:1})
  expect(state.availableLocations).toEqual(['虚拟地址甲','虚拟地址乙'])
  await wrapper.setProps({rows:[],total:0})
  expect(wrapper.text()).toContain('调整关键词、地点或资质筛选')
  state.confirm(); expect(wrapper.emitted('confirm')!.at(-1)![0]).toEqual([1])
  wrapper.unmount()
})

it('filters the full local catalog by location before paging and preserves selected rows', async () => {
  const wrapper=mountPicker(), state=(wrapper.vm as any).$.setupState
  await wrapper.setProps({rows:[...rows, {id:3,itemName:'另一个标准',standardCode:'OTHER',address:'其他地点'}] as any})
  expect(state.availableLocations).toEqual(['虚拟地址乙','虚拟地址甲'])
  state.locationFilter='虚拟地址乙'; state.search()
  expect(state.pageRows.map((r:any)=>r.id)).toEqual([2])
  state.toggle(2,true); state.confirm()
  expect(wrapper.emitted('confirm')!.at(-1)![0]).toEqual([1,2])
  state.keyword='不存在'
  expect(state.filtered).toHaveLength(0)
  expect(state.availableLocations).toHaveLength(2)
  state.keyword=''; state.locationFilter=''
  expect(state.filtered).toHaveLength(2)
  wrapper.unmount()
})

it('uses complete server locations, resets page on change, and keeps earlier selections', async()=>{
  const wrapper=shallowMount(Picker,{props:{modelValue:true,selectedIds:[1],selectedRows:[rows[0]] as any,
    rows:[rows[0]] as any,total:41,catalogLocations:['虚拟地址甲','虚拟地址乙','__unspecified__'],
    standards:['GB/T 1000'],contextKey:'locations'},global:{stubs:{BootstrapModal:{template:'<div><slot name="toolbar"/><slot/><slot name="footer"/></div>'}},config:{warnHandler:()=>undefined}}})
  const state=(wrapper.vm as any).$.setupState
  expect(wrapper.findAll('#sample-capability-location option').map(o=>o.text())).toEqual(['全部地点','虚拟地址甲','虚拟地址乙','未维护地点'])
  state.goPage(3)
  await wrapper.find('#sample-capability-location').setValue('虚拟地址乙')
  expect(wrapper.emitted('query')!.at(-1)).toEqual([{keyword:'',locationFilter:'虚拟地址乙',accreditationFilter:'',page:1,size:20,selectedStandardsOnly:true}])
  await wrapper.setProps({rows:[rows[1]] as any,total:1,selectedRows:rows as any})
  state.toggle(2,true); state.confirm()
  expect(wrapper.emitted('confirm')!.at(-1)![0]).toEqual([1,2])
  await wrapper.setProps({modelValue:false}); await wrapper.setProps({modelValue:true})
  expect(state.locationFilter).toBe('')
  wrapper.unmount()
})
describe('template capability picker selection', () => {
  it('keeps selected rows across keyword filtering and confirms the complete draft', async () => {
    const wrapper = mountPicker(), state = (wrapper.vm as any).$.setupState
    state.keyword = '气密'
    expect(state.filtered.map((row: any) => row.id)).toEqual([2])
    state.toggle(2, true)
    state.confirm()
    expect(wrapper.emitted('confirm')).toEqual([[[1, 2], [], [{kind:'library',id:1},{kind:'library',id:2}],{}]])
    wrapper.unmount()
  })
  it('cancelling and reopening discards unconfirmed changes', async () => {
    const wrapper = mountPicker(), state = (wrapper.vm as any).$.setupState
    state.toggle(2, true)
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    expect(state.draft).toEqual([{kind:'library',id:1}])
    expect(wrapper.emitted('confirm')).toBeUndefined()
    wrapper.unmount()
  })
  it('blocks confirmation during loading or errors and closes on sample context changes', async () => {
    const wrapper = mountPicker(), state = (wrapper.vm as any).$.setupState
    await wrapper.setProps({ loading: true })
    state.confirm()
    await wrapper.setProps({ loading: false, error: '读取失败' })
    state.confirm()
    expect(wrapper.emitted('confirm')).toBeUndefined()
    await wrapper.setProps({ contextKey: 'sample-b' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })
})

it('mixes manual and library parameters, keeps commas, deduplicates and commits the chosen order', async () => {
  const wrapper=mountPicker(), state=(wrapper.vm as any).$.setupState
  state.toggle(2,true); state.manualText='颗粒物（0.3, 0.5μm）；特殊参数\n特殊参数'; state.addManual()
  state.reorder(['manual:特殊参数','library:2','manual:颗粒物（0.3, 0.5μm）','library:1'])
  state.keyword='no matches'; state.confirm()
  expect(wrapper.emitted('confirm')![0]).toEqual([[2,1],['特殊参数','颗粒物（0.3, 0.5μm）'],[
    {kind:'manual',name:'特殊参数'},{kind:'library',id:2},{kind:'manual',name:'颗粒物（0.3, 0.5μm）'},{kind:'library',id:1}],{'特殊参数':{mode:'library',addresses:[]},'颗粒物（0.3, 0.5μm）':{mode:'library',addresses:[]}}])
  wrapper.unmount()
})
it('does not silently discard unavailable historic choices or unsent manual text', async()=>{
  const wrapper=mountPicker(), state=(wrapper.vm as any).$.setupState
  state.manualText='尚未加入';state.confirm();expect(wrapper.emitted('confirm')).toBeUndefined()
  state.manualText='';await wrapper.setProps({rows:[]});state.confirm();expect(wrapper.emitted('confirm')).toBeUndefined()
  state.remove('library:1');state.confirm();expect(wrapper.emitted('confirm')![0]).toEqual([[],[],[],{}]);wrapper.unmount()
})

it('drags a mixed selection to another position and blocks reordering in readonly mode',async()=>{
  const items=[{key:'library:1',label:'温度'},{key:'manual:温差',label:'温差',manual:true},{key:'library:2',label:'湿度'}]
  const list=shallowMount(OrderedList,{props:{items,label:'排序',showSource:true}})
  await list.findAll('[draggable]')[1].trigger('dragstart',{dataTransfer:{effectAllowed:'',setData:()=>undefined}})
  await list.findAll('li')[0].trigger('dragover')
  await list.findAll('li')[0].trigger('drop')
  expect(list.emitted('reorder')).toEqual([[['manual:温差','library:1','library:2']]])
  await list.setProps({readonly:true});expect(list.findAll('button')).toHaveLength(0)
  await list.findAll('li')[2].trigger('drop');expect(list.emitted('reorder')).toHaveLength(1)
  list.unmount()
})


it('requests server pages and retains ordered choices from earlier pages',async()=>{
  const wrapper=shallowMount(Picker,{props:{modelValue:true,selectedIds:[1],selectedRows:[rows[0]] as any,rows:[rows[0]] as any,total:41,standards:['GB/T 1000'],contextKey:'remote'},global:{config:{warnHandler:()=>undefined}}})
  const state=(wrapper.vm as any).$.setupState
  expect(wrapper.emitted('query')![0]).toEqual([{keyword:'',locationFilter:'',accreditationFilter:'',page:1,size:20,selectedStandardsOnly:true}])
  state.goPage(2)
  expect(wrapper.emitted('query')!.at(-1)).toEqual([{keyword:'',locationFilter:'',accreditationFilter:'',page:2,size:20,selectedStandardsOnly:true}])
  await wrapper.setProps({rows:[rows[1]] as any,selectedRows:rows as any})
  expect(state.pageRows.map((row:any)=>row.id)).toEqual([2])
  state.toggle(2,true);state.reorder(['library:2','library:1']);state.confirm()
  expect(wrapper.emitted('confirm')![0][0]).toEqual([2,1])
  wrapper.unmount()
})
it('debounces remote search, resets page, and cancels delayed search on close',async()=>{
  vi.useFakeTimers()
  const wrapper=shallowMount(Picker,{props:{modelValue:true,selectedIds:[],rows:[],total:41,standards:[],contextKey:'remote'},global:{config:{warnHandler:()=>undefined}}})
  const state=(wrapper.vm as any).$.setupState
  state.keyword='参';state.scheduleSearch();state.keyword='参数';state.scheduleSearch()
  await vi.advanceTimersByTimeAsync(349);expect(wrapper.emitted('query')).toHaveLength(1)
  await vi.advanceTimersByTimeAsync(1);expect(wrapper.emitted('query')!.at(-1)).toEqual([{keyword:'参数',locationFilter:'',accreditationFilter:'',page:1,size:20,selectedStandardsOnly:true}])
  state.keyword='取消';state.scheduleSearch();await wrapper.setProps({modelValue:false});await vi.advanceTimersByTimeAsync(400)
  expect(wrapper.emitted('query')).toHaveLength(2)
  wrapper.unmount();vi.useRealTimers()
})


it('only offers the chosen standards and requires an explicit database location for manual-only work',async()=>{
 const wrapper=mountPicker(),state=(wrapper.vm as any).$.setupState
 await wrapper.setProps({rows:[...rows,{id:3,itemName:'其他标准参数',standardCode:'OTHER'}] as any,locationOptions:['虚拟地址乙']})
 expect(state.filtered.map((r:any)=>r.id)).toEqual([1,2])
 state.remove('library:1');state.manualText='特殊参数';state.addManual()
 expect(state.draft).toEqual([])
 state.manualChoice={mode:'selected',addresses:['虚拟地址乙']};state.addManual();state.confirm()
 expect(wrapper.emitted('confirm')!.at(-1)![3]).toEqual({'特殊参数':{mode:'selected',addresses:['虚拟地址乙']}})
 await wrapper.setProps({modelValue:false,manualItems:['历史库外'],legacyManualLocation:'旧地址',selectedIds:[]})
 await wrapper.setProps({modelValue:true})
 expect(state.invalidManualLocations).toBe(true)
 expect(state.draftLocations['历史库外'].addresses).toEqual(['旧地址'])
 wrapper.unmount()
})
it('inherited manual locations follow library changes and cannot survive removal of the last library parameter',async()=>{
 const wrapper=mountPicker(),state=(wrapper.vm as any).$.setupState
 state.manualText='库外参数';state.addManual();state.toggle(2,true)
 expect(state.libraryAddresses).toEqual(['虚拟地址甲','虚拟地址乙'])
 state.remove('library:1');expect(state.libraryAddresses).toEqual(['虚拟地址乙'])
 state.remove('library:2');state.confirm();expect(wrapper.emitted('confirm')).toBeUndefined()
 wrapper.unmount()
})

it('allows all returned standard-owned parameters regardless of display metadata', async () => {
  const metadataRow = {id: 3, standardCode: 'CURRENT', sourceStandardCode: 'OLD', itemName: '温度',
    capabilityType: '校准', active: false, superseded: true, accreditation: 'CMA', address: ''}
  const wrapper = shallowMount(Picker, {props: {modelValue: true, selectedIds: [], rows: [metadataRow] as any,
    total: 1, standards: ['CURRENT'], contextKey: 'metadata'}, global: {config: {warnHandler: () => undefined}}})
  const state = (wrapper.vm as any).$.setupState
  expect(state.pageRows).toEqual([metadataRow])
  state.toggle(3, true)
  expect(state.libraryAddresses).toEqual([])
  expect(state.accreditationFor('library:3')).toBe('CMA')
  state.confirm()
  expect(wrapper.emitted('confirm')![0][0]).toEqual([3])
  wrapper.unmount()
})
