import type { EquipItem } from '@/services/quality'
import { equipmentCoversTestIntervals, equipmentManualUnavailable, equipmentValidityText, isLongTermEquipment, type EquipmentTestInterval } from '@/composables/equipmentValidity'
import { clientToday } from '../../services/common/date'
import type { EntryEquipment } from '../../types/testing/dataEntryDetail'

// Visibility follows the authorized catalogue; eligibility follows the test window.
export function entryEquipment(item: EquipItem, intervals: EquipmentTestInterval[], today = clientToday()): EntryEquipment {
  const lastCalibrationDate = (item.actualCalDate || item.lastCalDate || '').slice(0, 10)
  const validUntil = (item.validUntil || item.planCalDate || '').slice(0, 10)
  const parsed = new Date(`${validUntil}T00:00:00Z`)
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(validUntil) && !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === validUntil
  const expiredNow = !isLongTermEquipment(item) && validDate && validUntil < today
  const manualUnavailable = equipmentManualUnavailable(item)
  return {
    id: String(item.id), code: item.archiveNo || '', name: item.name,
    model: item.spec || '', manufacturer: item.maker || '', serial: item.factoryNo || '',
    departmentName: item.dept, cycle: item.period, location: item.place,
    inspectionOrganization: item.calUnit, remarks: item.remark,
    status: manualUnavailable ? item.status || item.manualStatus : expiredNow ? '已过期' : item.status,
    lastCalibrationDate, validUntil: isLongTermEquipment(item) ? '长期有效' : validUntil,
    validityNote: equipmentValidityText(item, intervals),
    selectable: equipmentCoversTestIntervals(item, intervals), expiredNow,
  }
}
