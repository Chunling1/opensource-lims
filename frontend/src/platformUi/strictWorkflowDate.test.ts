import {describe,it,expect} from 'vitest'
import {createPinia,setActivePinia} from 'pinia'
import {useSessionStore} from '@/stores/session'
describe('mandatory workflow chronology',()=>{
 it('does not restore the retired bypass for administrators or legacy action grants',()=>{
  setActivePinia(createPinia());const session=useSessionStore()
  session.roleKey='admin';session.account='admin';session.actionPermissions=['workflow.date.override']
  expect(session.canOverrideWorkflowDate).toBe(false)
  session.roleKey='operator';session.account='qa'
  expect(session.canOverrideWorkflowDate).toBe(false)
 })
})
