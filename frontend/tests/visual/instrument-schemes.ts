import { createApp, h, ref } from 'vue'
import EntryEquipmentPicker from '../../src/platformUi/testing/EntryEquipmentPicker.vue'
import { emptyTrialForm } from '../../src/types/testing/dataEntryDetail'
const ids = ref(['9'])
const detail: any = { sample: { id: 'QA-REPORT' }, capabilities: { canEdit: true }, equipmentConfig: { version: 0, associatedIds: ['1','2','9'], defaultIds: [] }, form: { ...emptyTrialForm(), testDates: [{ kind: 'range', from: '2026-10-01', to: '2026-10-02' }] }, options: { equipment: [1,2,9].map(id => ({ id: String(id), code: `EQ-${id}`, name: id === 2 ? '温度记录仪' : '压力仪', model: '', serial: '', manufacturer: '', selectable: id !== 2, validityNote: id === 2 ? '校准有效期不足' : '覆盖试验区间' })) } }
const app=createApp({setup:()=>()=>h(EntryEquipmentPicker,{detail,value:ids.value,onSelect:(value:string[])=>{ids.value=value;(window as any).selectedIds=value}})})
app.provide('platform-entry-services', {});app.mount('#app')
