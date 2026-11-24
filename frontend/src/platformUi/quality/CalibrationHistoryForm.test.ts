import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CalibrationHistoryForm from './CalibrationHistoryForm.vue'
const api=vi.hoisted(()=>({backfillEquipmentCalibration:vi.fn()}))
vi.mock('@/services/quality',()=>api)
beforeEach(()=>{ api.backfillEquipmentCalibration.mockReset() })
async function fill(w:ReturnType<typeof mount>) {
 const inputs=w.findAll('input');await inputs[0]!.setValue('2025-01-01');await inputs[1]!.setValue('2025-12-31');await inputs[2]!.setValue('OLD');await w.get('textarea').setValue('核对旧证书');await w.get('input[type="checkbox"]').setValue(true)
}
describe('historical calibration backfill',()=>{
 it('requires evidence and confirmation',async()=>{const w=mount(CalibrationHistoryForm,{props:{equipmentId:42}});await w.get('form').trigger('submit');expect(api.backfillEquipmentCalibration).not.toHaveBeenCalled();expect(w.get('[role="alert"]').text()).toContain('核对凭证')})
 it('saves old dates for exact ID, clears form only on success',async()=>{api.backfillEquipmentCalibration.mockResolvedValue({});const w=mount(CalibrationHistoryForm,{props:{equipmentId:42}});await fill(w);await w.get('form').trigger('submit');await flushPromises();expect(api.backfillEquipmentCalibration).toHaveBeenCalledWith(42,expect.objectContaining({start:'2025-01-01',end:'2025-12-31',confirmed:true,certificateNo:'OLD'}));expect(w.emitted('saved')).toHaveLength(1);expect(w.get('[role="status"]').text()).toContain('当前校准信息未改变')})
 it('keeps input and shows server error when rejected',async()=>{api.backfillEquipmentCalibration.mockRejectedValue(new Error('该开始日期的校准记录已存在'));const w=mount(CalibrationHistoryForm,{props:{equipmentId:42}});await fill(w);await w.get('form').trigger('submit');await flushPromises();expect(w.get('[role="alert"]').text()).toContain('已存在');expect((w.findAll('input')[0]!.element as HTMLInputElement).value).toBe('2025-01-01');expect(w.emitted('saved')).toBeUndefined()})
 it('rejects reversed dates before submitting',async()=>{const w=mount(CalibrationHistoryForm,{props:{equipmentId:42}});await fill(w);await w.findAll('input')[1]!.setValue('2024-01-01');await w.get('form').trigger('submit');expect(api.backfillEquipmentCalibration).not.toHaveBeenCalled()})
})
