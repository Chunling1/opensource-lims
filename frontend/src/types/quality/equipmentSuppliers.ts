import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export type SupplierListKind = 'suppliers' | 'evaluations'
export interface SupplierDraft { name: string; code: string; address: string; phone: string; postalCode: string; contact: string; services: string; notes: string }
export interface SupplierRecord extends SupplierDraft { id: string; version: number; departmentId: string; createdAt: string; updatedAt: string; updatedBy: string }
export interface EvaluationDraft { supplierId: string; services: string; quality: string; price: string; service: string; opinions: string; conclusion: string; reviewDate: string }
export interface EvaluationRecord extends EvaluationDraft { id: string; version: number; name: string; departmentId: string; createdAt: string; updatedAt: string; updatedBy: string }
export interface SupplierQuery { field?: string; value?: string; page?: number; pageSize?: number; ids?: string[]; supplierIds?: string[] }
export interface SupplierPage<Row> { items: Row[]; total: number; page: number; pageSize: number }
export const emptySupplier = (): SupplierDraft => ({ name: '', code: '', address: '', phone: '', postalCode: '', contact: '', services: '', notes: '' })
export const emptyEvaluation = (): EvaluationDraft => ({ supplierId: '', services: '', quality: '', price: '', service: '', opinions: '', conclusion: '', reviewDate: '' })
export const canWriteSuppliers = (actor: Actor) => actor.roles.includes('admin') || actor.roles.some(role => ['quality', 'inventory'].includes(role)) && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export const supplierFields = [
  { key: 'name', label: '单位名称', max: 200 }, { key: 'code', label: '单位编码', max: 100 }, { key: 'address', label: '单位地址', max: 500 },
  { key: 'phone', label: '联系电话', max: 100 }, { key: 'postalCode', label: '邮编', max: 20 }, { key: 'contact', label: '联系人', max: 100 },
] as const
export const supplierSearchFields = [{ key: 'code', label: '单位编号' }, { key: 'name', label: '单位名称' }, { key: 'address', label: '单位地址' }, { key: 'services', label: '服务提供项目' }] as const
export const evaluationSearchFields = [{ key: 'name', label: '单位名称' }, { key: 'services', label: '服务提供项目' }] as const
export const supplierColumns = [
  { key: 'code', label: '单位编号', default: true }, { key: 'name', label: '单位名称', required: true, truncate: 18, fullTitle: true },
  { key: 'address', label: '单位地址', truncate: 18, fullTitle: true }, { key: 'phone', label: '电话', default: true },
  { key: 'postalCode', label: '邮编' }, { key: 'contact', label: '联系人', default: true },
  { key: 'services', label: '服务提供项目', default: true, truncate: 18, fullTitle: true }, { key: 'notes', label: '备注', truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<keyof SupplierRecord>[]
export const evaluationColumns = [
  { key: 'name', label: '单位名称', required: true, truncate: 18, fullTitle: true }, { key: 'services', label: '服务提供项目', default: true, truncate: 18, fullTitle: true },
  { key: 'quality', label: '评审（质量）', truncate: 14, fullTitle: true }, { key: 'price', label: '评审（价格）', truncate: 14, fullTitle: true },
  { key: 'service', label: '评审（服务）', truncate: 14, fullTitle: true }, { key: 'opinions', label: '其它意见', truncate: 18, fullTitle: true },
  { key: 'conclusion', label: '评审结论', default: true, truncate: 18, fullTitle: true }, { key: 'reviewDate', label: '评审日期', default: true },
] as const satisfies readonly TableColumn<keyof EvaluationRecord>[]
