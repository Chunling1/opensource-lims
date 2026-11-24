import type { Actor } from '../lims'
import type { DemoAttachment } from '../commissions/registration'
import type { TableColumn } from '../common/table'
export type DocumentModule = 'library' | 'monitoring'
export const documentModuleTitle = (module: DocumentModule) => module === 'monitoring' ? '质量监控计划' : '文件基础信息库'
export type DocumentMovementKind = 'issue' | 'recover'
export interface LibraryDocumentDraft { code: string; category: string; name: string; quantity: number; notes: string }
export interface LibraryDocument extends LibraryDocumentDraft { id: string; version: number; departmentId: string; outstanding: number; files: DemoAttachment[] }
export interface LibraryDocumentRow extends LibraryDocument { remaining: number; usage: string; historyCount: number }
export interface DocumentMovement { id: string; documentId: string; kind: DocumentMovementKind; code: string; category: string; name: string; quantity: number; date: string; person: string; operatorId: string; operator: string; operatedAt: string }
export interface DocumentQuery { name?: string; category?: string; documentId?: string; ids?: string[]; page?: number; pageSize?: number }
export interface DocumentPage<T> { items: T[]; total: number; page: number; pageSize: number }
export const canManageDocuments = (actor: Actor) => actor.roles.includes('admin') || actor.roles.includes('quality') && !actor.roles.some(role => ['reviewer', 'approver'].includes(role))
export const documentColumns = [
  { key: 'code', label: '文件编号', default: true }, { key: 'category', label: '文件分类', default: true, truncate: 20, fullTitle: true },
  { key: 'name', label: '文件名称', required: true, truncate: 24, fullTitle: true }, { key: 'remaining', label: '剩余数量', default: true },
  { key: 'notes', label: '备注', truncate: 30, fullTitle: true }, { key: 'usage', label: '使用情况', default: true }, { key: 'quantity', label: '总数量' },
] as const satisfies readonly TableColumn<keyof LibraryDocumentRow>[]
export const movementColumns = [
  { key: 'code', label: '文件编号', default: true }, { key: 'category', label: '文件类型', default: true },
  { key: 'name', label: '文件名称', required: true }, { key: 'quantity', label: '数量', default: true },
  { key: 'date', label: '日期', default: true }, { key: 'person', label: '领用人', default: true }, { key: 'operator', label: '操作人', default: true },
] as const satisfies readonly TableColumn<keyof DocumentMovement>[]

export const documentMovementColumns = (kind: DocumentMovementKind) => movementColumns.map(column => column.key === 'person' ? { ...column, label: kind === 'issue' ? '领用人' : '回收人' } : column)
