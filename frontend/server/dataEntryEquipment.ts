import { AppError } from '../src/services/common/errors'
import type { RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import type { EntryEquipment, EntryEquipmentConfig } from '../src/types/testing/dataEntryDetail'
import { registrationDepartments } from '../src/types/commissions/commissionForm'

const equipment = [
  { id: 'equipment-1', code: 'DEMO-001', name: '多参数分析仪', departmentId: 'lab' },
  { id: 'equipment-2', code: 'DEMO-002', name: '压力试验机', departmentId: 'lab' },
  { id: 'equipment-3', code: 'DEMO-003', name: '温度记录仪', departmentId: 'lab2' },
]
export function equipmentOptions(sample: Pick<RegistrationSample, 'departmentId'>): EntryEquipment[] {
  return equipment.filter(row => row.departmentId === sample.departmentId).map(({ id, name, code, departmentId }) => ({ id, name, code, departmentId, departmentName: registrationDepartments.find(row => row.id === departmentId)?.name || departmentId, model: '演示通用型', manufacturer: '演示设备厂商', serial: `${id}-SN` }))
}
export function equipmentConfig(state: RegistrationState, sample: RegistrationSample): EntryEquipmentConfig {
  const key = `${sample.departmentId}:${sample.details?.testPlanId || ''}`
  return state.equipmentPlans?.[key] || { version: 1, associatedIds: equipmentOptions(sample).slice(0, 1).map(row => row.id), defaultIds: [] }
}
export function updateEquipmentConfig(state: RegistrationState, sample: RegistrationSample, action: string, input: Record<string, unknown>) {
  if (!sample.details?.testPlanId) throw new AppError('BUSINESS_RULE', '当前样品尚未关联检测方案。')
  const config = equipmentConfig(state, sample), ids = input.ids
  
  if (!Array.isArray(ids) || ids.length > 100 || new Set(ids).size !== ids.length || ids.some(id => typeof id !== 'string' || !equipmentOptions(sample).some(item => item.id === id))) throw new AppError('VALIDATION', '请选择当前部门可用的仪器设备。')
  if (action === 'equipment-associate') config.associatedIds = [...new Set([...config.associatedIds, ...ids])]
  else {
    if (ids.some(id => !config.associatedIds.includes(id))) throw new AppError('VALIDATION', '只能修改已关联设备的默认设置。')
    config.defaultIds = action === 'equipment-unset-defaults' ? config.defaultIds.filter(id => !ids.includes(id)) : [...new Set([...config.defaultIds, ...ids])]
  }
  config.version++
  ;(state.equipmentPlans ??= {})[`${sample.departmentId}:${sample.details.testPlanId}`] = config
}
