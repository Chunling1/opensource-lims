import {describe,it,expect} from 'vitest'
import {mount} from '@vue/test-utils'
import {reactive,h} from 'vue'
import SchemaForm from '../components/forms/SchemaForm.vue'
import {createAgreementSchema} from './agreementForm'

const model=()=>reactive({agreementNo:'KD-123',client:'客户',erpType:'标准合同',projectName:'工程',owner:'负责人',amount:'001.20',category:'',payment:'',department:'',info:{fromErp:'',auditTime:'2026-10-14 15:16:49.819',erpLogReceivedAt:'2026-10-14 15:17:32.001900',contractStartDate:'2026-10-14',sourceFieldSummary:'来源',registrar:'登记人',regTime:'2026-10-14',remark:''}} as any)
const context={locked:false,roLock:false,isAdmin:true,tab:'basic'}
function render(data:any,ctx=context,readonly=false){const schema=createAgreementSchema(data,ctx);const slots=Object.fromEntries(schema.sections.flatMap(s=>s.fields.filter(f=>f.control==='custom').map(f=>[(f as any).slot,()=>h('span','业务专用控件')])));return mount(SchemaForm as any,{props:{schema,model:data,readonly},slots})}

describe('Agreement form uses the unchanged package renderer with platform bindings',()=>{
 it('covers all 34 original field positions in six template sections without visual configuration',()=>{
  const data=model(),sections=['basic','more'].flatMap(tab=>createAgreementSchema(data,{...context,tab}).sections)
  expect(sections).toHaveLength(6)
  expect(sections.flatMap(s=>s.fields).filter(f=>f.id!=='agreement-source')).toHaveLength(34)
  for(const field of sections.flatMap(s=>s.fields))expect(Object.keys(field).filter(k=>/class|style|font|color/i.test(k))).toEqual([])
 })
 it('keeps the local contract type visible and immutable',async()=>{
  const data=model();data.erpType='不回传外部ERP合同'
  const wrapper=render(data)
  const field=wrapper.get('#agreement-field-1')
  expect((field.element as HTMLInputElement).value).toBe('不回传外部ERP合同')
  expect((field.element as HTMLInputElement).disabled).toBe(true)
  await field.setValue('虚拟框架');expect(data.erpType).toBe('不回传外部ERP合同')
  expect(wrapper.text()).toContain('本地合同（不回传外部ERP）')
 })
 it('writes nested business values through the real FormControl without changing amount representation',async()=>{
  const data=model(),basic=render(data)
  await basic.get('#agreement-field-12').setValue('登记备注');expect(data.info.remark).toBe('登记备注')
  const more=render(data,{...context,tab:'more'})
  await more.get('#agreement-field-24').setValue('001.25');expect(data.amount).toBe('001.25')
  await more.get('#agreement-field-14').setValue('委托人');expect(data.info.consignor).toBe('委托人')
 })
 it('locks Erp fields while leaving permitted registration fields editable and preserves timestamp precision',()=>{
  const data=model();data.info.fromErp='1'
  const wrapper=render(data,{...context,roLock:true})
  expect((wrapper.get('#agreement-field-0').element as HTMLInputElement).disabled).toBe(true)
  expect((wrapper.get('#agreement-field-12').element as HTMLTextAreaElement).disabled).toBe(false)
  expect((wrapper.get('#agreement-field-7').element as HTMLInputElement).value).toBe('2026-10-14 15:17:32.001900')
  expect((wrapper.get('#agreement-field-9').element as HTMLInputElement).disabled).toBe(false)
  const ordinary=render(data,{...context,roLock:true,isAdmin:false})
  expect((ordinary.get('#agreement-field-9').element as HTMLInputElement).disabled).toBe(true)
  expect((ordinary.get('#agreement-field-11').element as HTMLInputElement).disabled).toBe(true)
 })
 it('blocks readonly edits even if an input event is dispatched',async()=>{
  const data=model(),wrapper=render(data,context,true)
  await wrapper.get('#agreement-field-0').setValue('伪修改');expect(data.agreementNo).toBe('KD-123')
  await wrapper.get('#agreement-field-12').setValue('伪修改');expect(data.info.remark).toBe('')
 })
 it('keeps source provenance restricted to administrator Erp records',()=>{
  const data=model();data.info.fromErp='1'
  expect(render(data).text()).toContain('原文信息')
  expect(render(data,{...context,isAdmin:false}).text()).not.toContain('原文信息')
 })
})
