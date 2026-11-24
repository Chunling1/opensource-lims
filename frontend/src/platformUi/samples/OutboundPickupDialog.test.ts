import {expect, it} from 'vitest'
import {mount} from '@vue/test-utils'
import {defineComponent} from 'vue'
import Dialog from './OutboundPickupDialog.vue'
const modal = defineComponent({template:'<div><slot/><slot name="footer"/></div>'})
const picker = defineComponent({props:{modelValue:String,previousDate:String,strictOrder:Boolean,requirePrevious:Boolean},emits:['update:modelValue'],template:'<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"/>'})
it('offers one outbound/pickup date, preserves receipt boundary and submits explicitly', async () => {
  const form={managerId:'QA',managerName:'测试',outTime:'2026-10-23',pickupTime:'2026-10-23',receiverName:'测试',returnNote:''}
  const w=mount(Dialog,{props:{open:true,form,previousDate:'2026-10-22',canSign:true,allowSign:true,allowReturn:false},global:{stubs:{BootstrapModal:modal,WorkflowDatePicker:picker,StorageSampleSummary:true}}})
  expect(w.text()).toContain('出库领取日期')
  expect(w.findAllComponents(picker)).toHaveLength(1)
  expect(w.findComponent(picker).props()).toMatchObject({previousDate:'2026-10-22',strictOrder:true,requirePrevious:true})
  expect(w.emitted('submit')).toBeUndefined()
  await w.findAll('button').find(b=>b.text()==='签字领取')!.trigger('click')
  expect(w.emitted('submit')).toEqual([['sign']])
  w.unmount()
})
