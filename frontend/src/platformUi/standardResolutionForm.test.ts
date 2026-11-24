import {describe,it,expect,vi} from 'vitest'
import {ref} from 'vue'
import {standardResolutionForm} from './standardResolutionForm'
import {resolveReportStandards} from '@/services/pipeline'
vi.mock('@/services/pipeline',()=>({resolveReportStandards:vi.fn(async()=>({}))}))
describe('standard identity selection',()=>{
 it('submits explicit IDs, evidence and version then refreshes without approval',async()=>{
  const p=ref<any>({stage:'contract_review',preflightVersion:'v1',standardChoices:[{code:'GB1',candidates:[{id:7,code:'GB1',name:'English',department:'QA',implementationDate:'2026-01-01',marks:'CNAS'}]}]})
  const refresh=vi.fn(async()=>{}),form=standardResolutionForm(p,()=> 'R1',refresh)
  const fields=form.schema.sections[0].fields
  expect(form.needed).toBe(true)
  expect((fields[0] as any).options[0].label).toContain('English')
  ;(fields[0] as any).binding.set({},'7');(fields[1] as any).binding.set({},'原委托指定英文标准')
  await form.resolve()
  expect(resolveReportStandards).toHaveBeenCalledWith('R1',{stage:'contract_review',preflightVersion:'v1',selections:{GB1:7},reason:'原委托指定英文标准'})
  expect(refresh).toHaveBeenCalledOnce();expect(form.selected).toEqual({})
 })
})
