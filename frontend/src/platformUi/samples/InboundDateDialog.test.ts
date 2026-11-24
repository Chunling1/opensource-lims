import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {defineComponent} from 'vue'
import Dialog from './InboundDateDialog.vue'
import {submitSampleInbound} from '@/services/pipeline'
vi.mock('@/services/pipeline',()=>({submitSampleInbound:vi.fn()}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({canOverrideWorkflowDate:true})}))
const modal=defineComponent({props:['open'],template:'<div v-if="open"><slot/><slot name="footer"/></div>'})
const picker=defineComponent({props:{modelValue:String,previousDate:String,strictOrder:Boolean,disabled:Boolean},emits:['update:modelValue'],template:'<input :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)"/>'})
const wrappers:any[]=[]
const row={sampleNo:'S1',reportNo:'R1',sendDate:'2026-10-12',entrustDate:'2026-10-10'} as any
function setup(){const w=mount(Dialog,{props:{row},global:{stubs:{BootstrapModal:modal,WorkflowDatePicker:picker}}});wrappers.push(w);return w}
beforeEach(()=>{vi.clearAllMocks();vi.mocked(submitSampleInbound).mockResolvedValue({reportNo:'R1',sampleStatus:'已入库'})})
afterEach(()=>wrappers.splice(0).forEach(w=>w.unmount()))
it('does not submit on opening/cancel and accepts delivery-day receipt',async()=>{
 const w=setup();expect(submitSampleInbound).not.toHaveBeenCalled()
 expect(w.findComponent(picker).props('strictOrder')).toBe(true)
 expect(w.findComponent(picker).props('previousDate')).toBe('2026-10-12')
 await w.find('button').trigger('click');expect(w.emitted('close')).toHaveLength(1)
 await w.get('input').setValue('2026-10-12');await w.get('form').trigger('submit');await flushPromises()
 expect(submitSampleInbound).toHaveBeenCalledWith('R1','2026-10-12');expect(w.emitted('completed')).toHaveLength(1)
})
it.each(['2026-10-11','','2026-02-30'])('rejects invalid or early date %s before sending',async value=>{
 const w=setup();await w.get('input').setValue(value);await w.get('form').trigger('submit')
 expect(submitSampleInbound).not.toHaveBeenCalled();expect(w.get('[role="alert"]').text()).toMatch(/有效|不得早于/)
})
it('uses the later entrust boundary and keeps server errors open for correction',async()=>{
 const w=setup();await w.setProps({row:{...row,entrustDate:'2026-10-14'}})
 expect(w.findComponent(picker).props('previousDate')).toBe('2026-10-14')
 vi.mocked(submitSampleInbound).mockRejectedValueOnce(new Error('样品日期已变化，请核对'))
 await w.get('input').setValue('2026-10-15');await w.get('form').trigger('submit');await flushPromises()
 expect(w.text()).toContain('样品日期已变化');expect(w.emitted('completed')).toBeUndefined()
 await w.get('input').setValue('2026-10-16');await w.get('form').trigger('submit');await flushPromises()
 expect(w.emitted('completed')).toHaveLength(1)
})
it('prevents duplicate confirmation while saving',async()=>{
 let finish:any;vi.mocked(submitSampleInbound).mockImplementationOnce(()=>new Promise(r=>{finish=r}))
 const w=setup();await w.get('input').setValue('2026-10-15');await w.get('form').trigger('submit');await w.get('form').trigger('submit')
 expect(submitSampleInbound).toHaveBeenCalledTimes(1);expect(w.findComponent(picker).props('disabled')).toBe(true)
 finish({reportNo:'R1',sampleStatus:'已入库'});await flushPromises();expect(w.emitted('completed')).toHaveLength(1)
})
