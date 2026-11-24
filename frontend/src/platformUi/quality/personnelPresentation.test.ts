import {describe,it,expect,vi} from 'vitest'
import {reactive} from 'vue'
import {mount} from '@vue/test-utils'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {personnelSchema,createPersonnelPresentation} from './personnelPresentation'
describe('Personnel template/controller contract',()=>{
 it('writes the roster mobile to the personnel record, separately from a signing request',async()=>{
   const form=reactive({mobile:'',esignAccountInput:''})
   const w=mount(SchemaForm,{props:{model:form,schema:personnelSchema({form,canSensitive:true})}})
   await w.get('#platform-personnel-mobile').setValue('13800000001')
   expect(form.mobile).toBe('13800000001'); expect(form.esignAccountInput).toBe('')
   await w.setProps({schema:personnelSchema({form,canSensitive:false})})
   expect(w.find('#platform-personnel-mobile').exists()).toBe(false)
 })
 it('keeps identity fields and department numeric IDs while using SchemaForm',async()=>{const form=reactive<any>({name:'甲',code:'a01',departmentId:1,linkedUserId:9,idNo:'masked'}),sync=vi.fn();const schema=personnelSchema({form,canManageAccounts:true,canSensitive:false,deptOptions:[{id:1,name:'A'},{id:2,name:'B'}],syncDepartmentName:sync});const w=mount(SchemaForm as any,{props:{model:form,schema}});expect(w.get('#platform-personnel-code').attributes('disabled')).toBeDefined();expect(w.get('#platform-personnel-idNo').attributes('disabled')).toBeDefined();await w.get('#platform-personnel-department').setValue('2');expect(form.departmentId).toBe(2);expect(sync).toHaveBeenCalledWith(2);expect(w.findAll('section.card')).toHaveLength(1)});
 it('retains unknown stored values and blocks all profile edits in readonly mode',()=>{const form={name:'甲',approvalPosition:'custom',idNo:'**'};const w=mount(SchemaForm as any,{props:{model:form,schema:personnelSchema({form,canManageAccounts:false,canSensitive:false,deptOptions:[]}),readonly:true}});expect(w.get('#platform-personnel-approval').text()).toContain('custom');expect(w.get('#platform-personnel-name').attributes('readonly')).toBeDefined()});
 it('separates create/update/delete permission and delegates row operations to the original controller',()=>{const c=reactive<any>({kw:'',deptFilter:'',rows:[],deptOptions:[],session:{canAction:(p:string)=>p.endsWith('.update')},openCreate:vi.fn(),openEdit:vi.fn(),confirmRemove:vi.fn(),reload:vi.fn()});const m=createPersonnelPresentation(c);expect(m.canCreate).toBe(false);expect(m.canUpdate).toBe(true);expect(m.canDelete).toBe(false);m.modal={mode:'view',record:{source:{id:5}}};expect(c.personnelViewOnly).toBe(true);expect(c.openEdit).toHaveBeenCalledWith({id:5});expect(m.modal).toBeUndefined()});
});
