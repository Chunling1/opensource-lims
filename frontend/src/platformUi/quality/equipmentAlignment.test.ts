import {expect,it,vi} from 'vitest'
import {reactive} from 'vue'
import {mount} from '@vue/test-utils'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {equipmentSchema,createEquipmentPresentation} from './equipmentPresentation'

it('uses the same calibration start in the ledger and edit form',()=>{
 const context=reactive({rows:[{id:1,actualCalDate:'2025-01-01',lastCalDate:'2026-01-01',validUntil:'2027-01-01',planCalDate:'2026-12-31'}],depts:[],size:20,departmentOnly:false})
 const presentation=createEquipmentPresentation(context)
 expect(presentation.rows.items[0].lastTestDate).toBe('2025-01-01')
 expect(presentation.rows.items[0].plannedTestDate).toBe('2027-01-01')
 expect(presentation.equipmentLedgerColumns.find((c:{key:string})=>c.key==='lastTestDate').label).toBe('本次校准日期')
})

it('offers one start date and recalculates on current calibration edits',async()=>{
 const recalculateNextDate=vi.fn(),model=reactive({actualCalDate:'2026-01-01'})
 const schema=equipmentSchema({depts:[],recalculateNextDate})
 const wrapper=mount(SchemaForm<typeof model>,{props:{model,schema}})
 expect(wrapper.find('#equipment-lastCalDate').exists()).toBe(false)
 expect(wrapper.text()).toContain('本次校准日期')
 await wrapper.get('#equipment-actualCalDate').setValue('2026-02-01')
 expect(recalculateNextDate).toHaveBeenCalledOnce()
})
