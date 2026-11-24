import { describe, it, expect } from 'vitest'
import {
  equipmentCoversTestIntervals,
  equipmentManualUnavailable,
  equipmentValidityText,
  isLongTermEquipment,
} from '../../src/modules/composables/equipmentValidity'
import type { EquipItem } from '../../src/modules/services/quality'

const meter = (changes: Partial<EquipItem> = {}): EquipItem => ({
  id: 1, archiveNo: 'QA', name: '虚拟仪器', spec: '', dept: '', keeper: '',
  status: '限制使用', manualStatus: '可用', period: '1',
  lastCalDate: '2025-06-18', planCalDate: '2027-06-16', ...changes,
})
const spans = [{ start: '2026-10-31 12:00:00', end: '2026-10-31 20:00:00' }]

describe('test-window equipment eligibility', () => {
  it('delegates interval eligibility to backend evaluator metadata', () => {
    const ok = meter({ eligibility: { selectable: true, message: '覆盖全部试验区间' } as any })
    expect(equipmentCoversTestIntervals(ok, spans)).toBe(true)
    expect(equipmentValidityText(ok, spans)).toBe('覆盖全部试验区间')
    expect(equipmentCoversTestIntervals(meter(), spans)).toBe(false)
    expect(equipmentValidityText(meter(), spans)).toBe('正在核对仪器有效期')
  })
  it.each(['停用', '报废', '维修中', '失效'])('detects manual restriction %s', status => {
    expect(equipmentManualUnavailable(meter({ status }))).toBe(true)
    expect(equipmentManualUnavailable(meter({ status: '可用', manualStatus: status }))).toBe(true)
  })
  it('identifies long-term calibration periods', () => {
    expect(isLongTermEquipment(meter({ period: '长期' }))).toBe(true)
    expect(isLongTermEquipment(meter({ period: '1年' }))).toBe(false)
  })
})
