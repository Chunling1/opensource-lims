import {afterEach,expect,it,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {reactive} from 'vue'
import Fields from './RegistrationCommissionFields.vue'
import Organizations from './RegistrationOrganizationPicker.vue'
const wrappers:any[]=[]
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.useRealTimers()})
it.each(['标准合同','框架','虚拟框架','不回传外部ERP合同'])('renders the party input matrix for %s',async(kind)=>{
 const form=reactive<any>({contractParty:'原甲方',payer:'原付款方',customer:'原委托单位'})
 const locked=['标准合同','框架'].includes(kind),manual=kind==='不回传外部ERP合同'
 const w=mount(Fields,{props:{form},global:{provide:{'platform-registration-context':{departments:[],contractPartyLocked:locked,manualParties:manual,organizationPicked:vi.fn()}},stubs:{RegistrationContractPicker:true,RegistrationOrganizationPicker:true}}});wrappers.push(w)
 expect(w.get<HTMLInputElement>('#commission-contractParty').element.readOnly).toBe(!manual)
 expect(w.get<HTMLInputElement>('#commission-payer').element.readOnly).toBe(!manual)
 expect(w.get<HTMLTextAreaElement>('#commission-customer').element.readOnly).toBe(false)
 expect(w.get('button[aria-label="选择合同甲方"]').attributes('disabled')!==undefined).toBe(locked)
 await w.get('#commission-customer').setValue('新手写委托');expect(form.customer).toBe('新手写委托')
 if(manual){await w.get('#commission-contractParty').setValue('手写甲方');await w.get('#commission-payer').setValue('手写付款');expect(form.contractParty).toBe('手写甲方');expect(form.payer).toBe('手写付款')}
 await w.setProps({readonly:true});expect(w.get<HTMLTextAreaElement>('#commission-customer').element.readOnly).toBe(true)
})
it('keeps selected customers across search and supports removing every selection',async()=>{
 vi.useFakeTimers();const service=vi.fn(async()=>({items:[{id:'2',name:'客户乙'}],total:58154,page:1,pageSize:10}))
 const w=mount(Organizations,{props:{open:true,title:'选择委托单位',multiple:true,value:'已保存甲；已保存乙'},global:{provide:{'platform-registration-services':{organizations:service}},stubs:{BootstrapModal:{template:'<div><slot name="toolbar"/><slot/><slot name="footer"/></div>'},SingleChoice:true,TablePagination:true,RouterLink:true}}});wrappers.push(w);await flushPromises()
 const input=w.get('input[maxlength="200"]');await input.setValue('客户');await vi.advanceTimersByTimeAsync(250);await flushPromises()
 expect(service).toHaveBeenLastCalledWith({keyword:'客户',page:1,pageSize:10},expect.any(AbortSignal))
 await w.get('button[aria-label="移除 已保存甲"]').trigger('click')
 await w.get('button[aria-label="移除 已保存乙"]').trigger('click')
 await w.findAll('button').find(b=>b.text()==='确定')!.trigger('click');expect(w.emitted('select')).toEqual([['']])
 await w.setProps({open:false});await w.setProps({open:true});await flushPromises();expect(service).toHaveBeenCalledTimes(3)
})
