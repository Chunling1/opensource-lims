import { describe, expect, it } from 'vitest'
import type { EquipItem } from '@/services/quality'
import { entryEquipment } from './entryEquipment'

const meter = (extra: Partial<EquipItem> = {}): EquipItem => ({ id: 1, archiveNo: 'M-01', name: '虚拟温度计', spec: '', dept: '试验部', status: '限制使用', manualStatus: '可用', keeper: '', lastCalDate: '2025-01-01', actualCalDate: '2026-01-01', planCalDate: '2027-01-01', validUntil: '2026-10-31', eligibility:{level:'notice',code:'equipment.covered',message:'覆盖全部试验区间',selectable:true}, ...extra })
const intervals = [{ start: '2026-10-01 09:00:00', end: '2026-10-31 18:00:00' }]
describe('entry equipment display and historical eligibility', () => {
  it('shows today expiry separately from historical test eligibility, using actual calibration and explicit expiry', () => {
    expect(entryEquipment(meter(), intervals, '2026-11-04')).toMatchObject({ id: '1', status: '已过期', lastCalibrationDate: '2026-01-01', validUntil: '2026-10-31', selectable: true, expiredNow: true, validityNote: '覆盖全部试验区间' })
  })
  it('includes the expiry day and warns only after that day', () => {
    expect(entryEquipment(meter(), intervals, '2026-10-31').expiredNow).toBe(false)
    expect(entryEquipment(meter(), intervals, '2026-11-01').expiredNow).toBe(true)
  })
  it.each(['停用', '维修中', '报废', '失效'])('keeps %s visible but unavailable', status => {
    expect(entryEquipment(meter({ status, manualStatus: '停用/报废',eligibility:{level:'block',code:'equipment.unavailable',message:status,selectable:false} }), intervals, '2026-11-04')).toMatchObject({ status, selectable: false })
  })
  it('uses the backend verdict even when the current ledger differs from historical calibration', () => {
    const item=meter({actualCalDate:'2026-11-01',eligibility:{level:'notice',code:'equipment.covered',message:'覆盖试验区间',selectable:true}})
    expect(entryEquipment(item,intervals).selectable).toBe(true)
    item.eligibility={level:'block',code:'equipment.expired',message:'未覆盖试验区间',selectable:false}
    expect(entryEquipment(item,intervals)).toMatchObject({selectable:false,validityNote:'未覆盖试验区间'})
  })
  it('does not guess when backend validation has not arrived',()=>{
    expect(entryEquipment(meter({eligibility:undefined}),intervals).selectable).toBe(false)
  })
  it('preserves unique IDs for matching instrument codes', () => {
    const rows = [meter(), meter({ id: 2, name: 'Thermometer' })].map(row => entryEquipment(row, intervals, '2026-11-04'))
    expect(rows.map(row => row.id)).toEqual(['1', '2'])
    expect(rows.map(row => row.code)).toEqual(['M-01', 'M-01'])
  })
})
