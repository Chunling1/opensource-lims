import type { DemoAttachment } from '../commissions/registration'
import type { EquipmentLedgerRow } from './equipmentLedger'

export const equipmentTabs = [
  { key: 'basic', label: '基本信息' }, { key: 'projects', label: '检测方案' },
  { key: 'calibrations', label: '检定记录' }, { key: 'maintenance', label: '维修维护记录' },
  { key: 'usage', label: '使用记录' }, { key: 'checks', label: '期间核查记录' }, { key: 'reports', label: '报告信息' },
] as const
export type EquipmentTab = typeof equipmentTabs[number]['key']
export type EquipmentHistoryKind = 'calibrations' | 'maintenance' | 'usage' | 'checks'
export interface EquipmentField { key: string; label: string; date?: boolean; required?: boolean; area?: boolean }
export const equipmentHistoryFields: Record<EquipmentHistoryKind, EquipmentField[]> = {
  calibrations: [{ key: 'organization', label: '检定单位' }, { key: 'certificate', label: '证书号' }, { key: 'conclusion', label: '检定结论' }, { key: 'date', label: '检定日期', date: true }, { key: 'cycle', label: '检定周期' }, { key: 'nextDate', label: '下次检定日期', date: true }],
  maintenance: [{ key: 'date', label: '维修维护日期', date: true }, { key: 'reason', label: '维修维护原因' }, { key: 'content', label: '维修维护内容', area: true }, { key: 'person', label: '维修人员' }, { key: 'notes', label: '备注', area: true }],
  usage: [{ key: 'date', label: '使用日期', date: true }, { key: 'person', label: '使用人' }, { key: 'before', label: '使用前仪器状态' }, { key: 'after', label: '使用后仪器状态' }, { key: 'notes', label: '备注', area: true }],
  checks: [{ key: 'standard', label: '计量参考标准名称' }, { key: 'standardDate', label: '计量参考标准检定日期', date: true }, { key: 'person', label: '期间核查人员' }, { key: 'date', label: '检查日期', date: true }, { key: 'project', label: '期间核查项目' }, { key: 'conclusion', label: '评审分析及结论', area: true }],
}
export const equipmentCheckMeasurements = [
  { key: 'point', label: '期间核查点' },
  { key: 'first', label: '第一次实测值' },
  { key: 'second', label: '第二次实测值' },
  { key: 'third', label: '第三次实测值' },
  { key: 'average', label: '平均实测值' },
  { key: 'error', label: '误差' },
] as const
// Detail-only fields are persisted without expanding the record list columns.
export function equipmentRecordFields(kind: EquipmentHistoryKind): EquipmentField[] {
  return kind === 'checks' ? [
    ...equipmentHistoryFields.checks,
    { key: 'equipmentDate', label: '设备检定日期', date: true },
    { key: 'accuracyRequirement', label: '精度要求' },
    ...equipmentCheckMeasurements.flatMap(field => Array.from({ length: 5 }, (_, index) => ({ key: `${field.key}${index + 1}`, label: `核查点 ${index + 1} ${field.label}` }))),
  ] : equipmentHistoryFields[kind]
}
export const equipmentAttachmentKinds = [{ key: 'usage', label: '使用记录' }, { key: 'manual', label: '说明书' }, { key: 'certificate', label: '合格证' }, { key: 'acceptance', label: '验收单' }] as const
export type EquipmentAttachmentKind = typeof equipmentAttachmentKinds[number]['key']
export interface EquipmentProject { id: string; code: string; name: string; parentId?: string }
export interface EquipmentHistory { id: string; [key: string]: string }
export interface EquipmentReport { id: string; commissionCode: string; sampleCode: string; reportCode: string; project: string }
export interface EquipmentProfile {
  equipmentType: string; tester: string; validity: string; projects: EquipmentProject[]
  calibrations: EquipmentHistory[]; maintenance: EquipmentHistory[]; usage: EquipmentHistory[]; checks: EquipmentHistory[]
  attachments: Record<EquipmentAttachmentKind, DemoAttachment[]>
}
export interface EquipmentRecord extends EquipmentLedgerRow { profile: EquipmentProfile; version: number }
export type EquipmentDraft = Omit<EquipmentRecord, 'id' | 'version'>
export interface EquipmentFormOptions { departments: { id: string; name: string }[]; equipmentTypes: string[]; projects: EquipmentProject[] }
export const equipmentBatchFields = [
  { key: 'equipmentType', label: '设备类型', kind: 'type' },
  { key: 'departmentId', label: '所属部门', kind: 'department' },
  { key: 'keeper', label: '仪器保管人', kind: 'text' },
  { key: 'status', label: '设备状态', kind: 'status' },
  { key: 'lastTestDate', label: '最近检定/测试日期', kind: 'date' },
  { key: 'plannedTestDate', label: '计划检定/测试日期', kind: 'date' },
  { key: 'actualTestDate', label: '实际检定/测试日期', kind: 'date' },
  { key: 'testOrganization', label: '检定/测试单位', kind: 'text' },
  { key: 'purchasedAt', label: '购入日期', kind: 'date' },
  { key: 'price', label: '购入价格', kind: 'price' },
  { key: 'location', label: '放置单位', kind: 'text' },
] as const
export type EquipmentBatchKey = typeof equipmentBatchFields[number]['key']
export type EquipmentBatchChanges = Partial<Pick<EquipmentDraft, Exclude<EquipmentBatchKey, 'equipmentType'>> & { equipmentType: string }>
export interface EquipmentBatchInput { records: { id: string; version: number }[]; changes: EquipmentBatchChanges }
export function emptyEquipment(): EquipmentDraft {
  return { code: '', name: '', model: '', serial: '', manufacturer: '', testOrganization: '', status: '可用', departmentId: '', department: '', location: '', lastTestDate: '', cycle: '', plannedTestDate: '', actualTestDate: '', notes: '', range: '', accuracy: '', keeper: '', purchasedAt: '', price: null, usageRecordCount: 0, manualCount: 0, certificateCount: 0, acceptanceCount: 0,
    profile: { equipmentType: '', tester: '', validity: '', projects: [], calibrations: [], maintenance: [], usage: [], checks: [], attachments: { usage: [], manual: [], certificate: [], acceptance: [] } } }
}
