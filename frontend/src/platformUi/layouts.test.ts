import {describe,it,expect,vi} from 'vitest'
import {mount} from '@vue/test-utils'
import {h,defineComponent,ref,nextTick,Fragment,createCommentVNode} from 'vue'
vi.mock('../components/common/table/AdaptiveTableActions.vue',()=>({default:defineComponent({props:['actions'],emits:['action'],setup(p,{slots,emit}){return()=>h('div',[slots.default?.(),...p.actions.map((action:any,index:number)=>h('button',{disabled:action.disabled,onClick:()=>emit('action',index)},action.label))])}})}))
import {TemplateFilterFields,TemplateBusinessActions} from './layouts'
import {ElButton,ElInput,ElSelect,ElOption,ElFormItem,ElPagination} from './controls'
import TemplateOptionSelect from './TemplateOptionSelect.vue'
describe('Template composition preserves business contracts',()=>{
 it('gives filters responsive template columns and preserves typed model updates',async()=>{
  const value=ref(''),wrapper=mount(defineComponent({setup:()=>()=>h(TemplateFilterFields,{},()=>[h(Fragment,{},[createCommentVNode('unavailable filter'),h(ElInput,{modelValue:value.value,placeholder:'项目名称','onUpdate:modelValue':(v:string)=>value.value=v})])])}))
  expect(wrapper.findAll('label')).toHaveLength(1)
  expect(wrapper.find('label').classes()).toContain('form-label')
  expect(wrapper.find('input').attributes('id')).toBe(wrapper.find('label').attributes('for'))
  await wrapper.find('input').setValue('核对项目');expect(value.value).toBe('核对项目')
  expect(wrapper.find('input').element.closest('.col-sm-6')).not.toBeNull()
 })
 it('retains numeric select values and permission-disabled fields',async()=>{
  const value=ref<number|undefined>(),wrapper=mount(defineComponent({setup:()=>()=>h(ElFormItem,{label:'部门'},()=>h(ElSelect,{modelValue:value.value,'onUpdate:modelValue':(v:number)=>value.value=v},()=>[h(ElOption,{label:'检测部',value:7})]))}))
  await wrapper.find('select').setValue('0');expect(value.value).toBe(7)
  expect(wrapper.find('select').attributes('id')).toBe(wrapper.find('label').attributes('for'))
  const disabled=mount(ElInput,{props:{modelValue:'只读',disabled:''}});expect((disabled.find('input').element as HTMLInputElement).disabled).toBe(true)
 })
 it('keeps primary actions, secondary callbacks and disabled rules through the template toolbar',async()=>{
  const add=vi.fn(),edit=vi.fn(),remove=vi.fn(),locked=ref(true)
  const wrapper=mount(defineComponent({setup:()=>()=>h(TemplateBusinessActions,{},()=>[h(ElButton,{onClick:add},()=> '新增'),h(ElButton,{onClick:edit},()=> '修改'),h(ElButton,{disabled:locked.value,onClick:remove},()=> '删除')])}))
  await wrapper.findAll('button')[0]!.trigger('click');await wrapper.findAll('button')[1]!.trigger('click');await wrapper.findAll('button')[2]!.trigger('click')
  expect(add).toHaveBeenCalledTimes(1);expect(edit).toHaveBeenCalledTimes(1);expect(remove).not.toHaveBeenCalled()
  locked.value=false;await nextTick();await wrapper.findAll('button')[2]!.trigger('click');expect(remove).toHaveBeenCalledTimes(1)
 })
 it('uses template pagination without changing original page and size events',async()=>{
  const wrapper=mount(ElPagination,{props:{currentPage:2,pageSize:10,pageSizes:[10,20],total:90}})
  await wrapper.find('select').setValue('20')
  expect(wrapper.emitted('update:pageSize')?.[0]).toEqual([20]);expect(wrapper.emitted('update:currentPage')?.[0]).toEqual([1])
  expect(wrapper.find('.pagination-wrap').exists()).toBe(true)
 })
 it('uses the package dropdown structure while keeping numeric values and disabled options',async()=>{
  const value=ref(7)
  const wrapper=mount(defineComponent({setup:()=>()=>h(TemplateOptionSelect,{id:'department',label:'部门',rawValue:value.value,choiceOptions:[{value:7,label:'甲部门'},{value:8,label:'乙部门',disabled:true},{value:9,label:'丙部门'}],'onUpdate:rawValue':(v:number)=>value.value=v})}),{attachTo:document.body})
  expect(wrapper.findAll('input')).toHaveLength(1)
  expect(wrapper.find('.input-group > .dropdown-menu').exists()).toBe(true)
  const choices=wrapper.findAll('.dropdown-menu button')
  await choices[1]!.trigger('click');expect(value.value).toBe(7)
  await choices[2]!.trigger('click');expect(value.value).toBe(9)
  expect((wrapper.find('input').element as HTMLInputElement).value).toBe('丙部门')
  wrapper.unmount()
 })
 it('filters without submitting arbitrary text and preserves selections outside a multiple-choice search',async()=>{
  const value=ref([1,3])
  const wrapper=mount(defineComponent({setup:()=>()=>h(TemplateOptionSelect,{id:'projects',label:'项目',multiple:true,rawValue:value.value,choiceOptions:[{value:1,label:'甲项目'},{value:2,label:'乙项目'},{value:3,label:'丙项目'}],'onUpdate:rawValue':(v:number[])=>value.value=v})}),{attachTo:document.body})
  await wrapper.find('input.form-control').setValue('乙')
  expect(value.value).toEqual([1,3]);expect(wrapper.findAll('.dropdown-menu li')).toHaveLength(1)
  await wrapper.find('.dropdown-menu input').setValue(true);expect(value.value).toEqual([1,3,2])
  wrapper.unmount()
 })
})
