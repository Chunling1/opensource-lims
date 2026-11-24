import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export type MaterialKind = 'materials' | 'acceptances'
export interface MaterialDraft { name: string; specification: string; supplier: string; manufacturer: string; purchasedAt: string; purchasedQuantity: number | null; purchaseStatus: string; receivedAt: string; receivedQuantity: number | null; validity: string; notes: string }
export interface MaterialRecord extends MaterialDraft { id: string; version: number; departmentId: string; accepted: boolean; acceptanceStatus: string; createdAt: string; updatedAt: string; updatedBy: string }
export interface AcceptanceDraft { materialId: string; materialVersion: number; useDepartmentId: string; location: string; supplier: string; supplierAddress: string; supplierPhone: string; manufacturer: string; manufacturerPhone: string; basis: string; status: string; acceptedAt: string; certificate: string; acceptorId: string; keeperId: string; notes: string }
export interface AcceptanceRecord extends AcceptanceDraft { id: string; version: number; departmentId: string; name: string; specification: string; useDepartment: string; acceptor: string; keeper: string; createdAt: string; updatedAt: string; updatedBy: string }
export interface MaterialQuery { name?: string; manufacturer?: string; useDepartment?: string; materialIds?: string[]; ids?: string[]; page?: number; pageSize?: number }
export interface MaterialPage<Row> { items: Row[]; total: number; page: number; pageSize: number }
export const emptyMaterial = (): MaterialDraft => ({ name: '', specification: '', supplier: '', manufacturer: '', purchasedAt: '', purchasedQuantity: null, purchaseStatus: '', receivedAt: '', receivedQuantity: null, validity: '', notes: '' })
export const emptyAcceptance = (): AcceptanceDraft => ({ materialId: '', materialVersion: 0, useDepartmentId: '', location: '', supplier: '', supplierAddress: '', supplierPhone: '', manufacturer: '', manufacturerPhone: '', basis: '', status: '', acceptedAt: '', certificate: '', acceptorId: '', keeperId: '', notes: '' })
export const canWriteMaterials = (actor: Actor) => actor.roles.includes('admin') || actor.roles.some(role => ['quality', 'inventory'].includes(role)) && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export const materialTextFields = [{ key: 'name', label: '品名' }, { key: 'specification', label: '规格' }, { key: 'supplier', label: '供应单位' }, { key: 'manufacturer', label: '生产厂家' }, { key: 'purchaseStatus', label: '购置状态' }, { key: 'validity', label: '有效期' }] as const
export const acceptanceTextFields = [{ key: 'location', label: '存放地点' }, { key: 'supplier', label: '供货单位' }, { key: 'supplierAddress', label: '供货单位地址' }, { key: 'supplierPhone', label: '供货单位电话' }, { key: 'manufacturer', label: '生产单位' }, { key: 'manufacturerPhone', label: '生产单位电话' }, { key: 'basis', label: '验收依据' }, { key: 'certificate', label: '相关证书' }] as const
export const acceptanceStatuses = ['合格', '不合格'] as const
export const materialColumns = [
  { key: 'name', label: '品名', required: true, truncate: 18, fullTitle: true }, { key: 'specification', label: '规格', default: true },
  { key: 'supplier', label: '供应单位', truncate: 18, fullTitle: true }, { key: 'manufacturer', label: '生产厂家', default: true, truncate: 18, fullTitle: true },
  { key: 'purchasedAt', label: '购置日期' }, { key: 'purchasedQuantity', label: '购置数量', default: true }, { key: 'validity', label: '有效期', default: true }, { key: 'purchaseStatus', label: '购置状态' },
  { key: 'acceptanceStatus', label: '是否验收', default: true }, { key: 'receivedAt', label: '领用日期' }, { key: 'receivedQuantity', label: '领用数量' }, { key: 'notes', label: '备注', truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<keyof MaterialRecord>[]
export const acceptanceColumns = [
  { key: 'name', label: '物质名称', required: true, truncate: 18, fullTitle: true }, { key: 'useDepartment', label: '使用部门', default: true },
  { key: 'supplier', label: '供货单位', truncate: 18, fullTitle: true }, { key: 'status', label: '验收状态', default: true }, { key: 'acceptedAt', label: '验收日期', default: true },
  { key: 'location', label: '存放地点' }, { key: 'acceptor', label: '验收人', default: true }, { key: 'keeper', label: '保管人' },
  { key: 'specification', label: '规格' }, { key: 'supplierAddress', label: '供货单位地址' }, { key: 'supplierPhone', label: '供货单位电话' },
  { key: 'manufacturer', label: '生产单位' }, { key: 'manufacturerPhone', label: '生产单位电话' }, { key: 'basis', label: '验收依据' }, { key: 'certificate', label: '相关证书' }, { key: 'notes', label: '备注', truncate: 18, fullTitle: true },
] as const satisfies readonly TableColumn<keyof AcceptanceRecord>[]
