import {describe,it,expect} from 'vitest'
import {mount} from '@vue/test-utils'
import Steps from './SigningFlowSteps.vue'
describe('Signing flow from actual signer records',()=>{
 it('shows the second examiner and organization seal, including a pending node',()=>{
 const steps=['主检','主检2','审核','批准','组织盖章'].map((title,i)=>({key:String(i),title,description:'人员'+i+' · '+(i<2?'已签':'待签'),complete:i<2}))
 const v=mount(Steps,{props:{steps}})
 expect(v.findAll('[role=tab]')).toHaveLength(5)
 expect(v.findAll('.done')).toHaveLength(2)
 expect(v.get('[aria-current=step]').text()).toContain('审核')
 expect(v.text()).toContain('主检2');expect(v.text()).toContain('组织盖章')
 })
 it('reflects backend refresh to completed without triggering a signing operation',async()=>{
 const v=mount(Steps,{props:{steps:[{key:'a',title:'主检',description:'待签',complete:false}]}})
 await v.setProps({steps:[{key:'a',title:'主检',description:'已签',complete:true}]})
 expect(v.findAll('.done')).toHaveLength(1)
 await v.get('button').trigger('click');expect(v.emitted()).not.toHaveProperty('dispatch')
 })
})
