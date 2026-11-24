import {describe,it,expect} from 'vitest'
import {mount} from '@vue/test-utils'
import ErpPermissionEditor from './ErpPermissionEditor.vue'
import {canOperateErp,toggleErpRole} from './erpPermissions'
describe('individual Erp grants',()=>{
 it('requires all prerequisites and distinguishes send from reverse',()=>{
  expect(canOperateErp(undefined,'send')).toBe(false)
  expect(canOperateErp(['send'],'send')).toBe(false)
  expect(canOperateErp(['view','review','send'],'send')).toBe(true)
  expect(canOperateErp(['view','review','send'],'reverse')).toBe(false)
 })
 it('adds prerequisites and removes dependent grants',()=>{
  expect(toggleErpRole([],'reverse',true)).toEqual(['view','review','send','reverse'])
  expect(toggleErpRole(['view','review','send','reverse'],'review',false)).toEqual(['view'])
 })
 it('edits personnel with checkbox buttons',async()=>{
  const w=mount(ErpPermissionEditor,{props:{modelValue:[],administrator:false,canManage:true}})
  await w.get('#erp-grant-send').setValue(true)
  expect(w.emitted('update:modelValue')![0]).toEqual([['view','review','send']])
 })
 it.each([{administrator:true,canManage:true},{administrator:false,canManage:false}])('prevents altering inherited or unauthorized grants %j',props=>{
  const w=mount(ErpPermissionEditor,{props:{modelValue:[],...props}})
  expect(w.findAll('input').every(i=>(i.element as HTMLInputElement).disabled)).toBe(true)
  expect(w.findAll('input').every(i=>(i.element as HTMLInputElement).checked)).toBe(props.administrator)
 })
})
