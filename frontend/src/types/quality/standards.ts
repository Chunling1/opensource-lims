import type { Actor } from '../lims'
import { canManageDefinitions } from './equipmentGroups'
import type { TableColumn } from '../common/table'
export { canManageDefinitions as canManageStandards } from './equipmentGroups'
export const standardQualifications = ['检验', '检测', '检验和检测', '校准'] as const
export interface StandardDraft {
  controlNumber: string; code: string; name: string; category: string; location: string; quantity: number | null; issuer: string;
  implementedAt: string; abolished: boolean; abolishedAt: string; extensionDays: number | null; replacementCode: string;
  qualification: string; outsideScope: boolean; english: boolean; notes: string; departmentIds: string[]
}
export interface StandardRecord extends StandardDraft { id: string; version: number; ownerDepartmentId?: string; groupIds: string[] }
export interface StandardRow extends StandardRecord { departments: string }
export interface StandardQuery { code?: string; name?: string; category?: string; qualification?: string; controlNumber?: string; location?: string; departmentId?: string; ownDepartment?: boolean; page?: number; pageSize?: number; ids?: string[] }
export interface StandardOptions { departments: { id: string; name: string }[]; locations: string[] }
export interface StandardPage extends StandardOptions { items: StandardRow[]; total: number; page: number; pageSize: number }
export const emptyStandard = (): StandardDraft => ({ controlNumber: '', code: '', name: '', category: '', location: '', quantity: null, issuer: '', implementedAt: '', abolished: false, abolishedAt: '', extensionDays: null, replacementCode: '', qualification: '', outsideScope: false, english: false, notes: '', departmentIds: [] })
export const standardColumns = [
  { key: 'controlNumber', label: '受控号', default: true }, { key: 'code', label: '标准编号', default: true }, { key: 'name', label: '标准名称', required: true, truncate: 28, fullTitle: true },
  { key: 'qualification', label: '标准资质类别', default: true }, { key: 'category', label: '类别', default: true, truncate: 20, fullTitle: true },
  { key: 'location', label: '存放地点' }, { key: 'quantity', label: '发放数量' }, { key: 'issuer', label: '发放人' }, { key: 'departments', label: '使用部门', default: true, truncate: 20, fullTitle: true },
  { key: 'implementedAt', label: '实施日期', default: true }, { key: 'abolishedAt', label: '作废日期', default: true }, { key: 'extensionDays', label: '延期时间（天）' }, { key: 'replacementCode', label: '替换标准号' },
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true }, { key: 'outsideScope', label: '是否在资质范围外' }, { key: 'english', label: '是否英文标准' },
] as const satisfies readonly TableColumn<keyof StandardRow>[]

export const canEditStandard = (actor: Actor, row: StandardRecord) => canManageDefinitions(actor) && (actor.scope === 'all' || row.departmentIds.every(id => id === actor.departmentId))
export function standardExtensionDays(abolished: boolean, abolishedAt: string, today: string): number | null {
  if (!abolished || !abolishedAt || !Number.isFinite(Date.parse(abolishedAt)) || !Number.isFinite(Date.parse(today))) return null
  return Math.max(0, Math.floor((Date.parse(today) - Date.parse(abolishedAt)) / 86400000))
}
