import type { Sample } from './sample'

export type Value = string | number | boolean | string[]
export type Fields = Record<string, Value>
export interface BusinessRecord {
  id: string; kind: string; code: string; name: string; status: string; version: number
  departmentId: string; ownerId: string; createdAt: string; updatedAt: string; data: Fields
}
export interface Actor { id: string; name: string; roles: string[]; departmentId: string; scope: 'all' | 'department'; active?: boolean; avatar?: string; certificateNumber?: string; phone?: string; email?: string; position?: string; jobTitle?: string }
export interface AuditEvent { id: string; entityId: string; kind: string; action: string; actorId: string; actor: string; at: string; reason: string; before?: BusinessRecord; after?: BusinessRecord }
export interface ApprovalInstance {
  id: string; entityId: string; kind: string; action: string; applicantId: string; applicantName: string
  approverRoles: string[]; approverIds: string[]; configVersion: number; status: 'pending' | 'approved' | 'rejected'
  createdAt: string; resolvedAt?: string; resolverId?: string; reason: string
}
export interface Attachment { id: string; entityId: string; name: string; type: string; size: number; blob: Blob; actor: string; at: string }
export interface LimsDatabase {
  schema: 2; revision: number; records: BusinessRecord[]; samples: Sample[]; sampleMeta: Record<string, { departmentId: string; ownerId: string; version: number }>
  actors: Actor[]; audits: AuditEvent[]; approvals: ApprovalInstance[]; attachments: Attachment[]
}
export interface FieldDefinition {
  key: string; label: string; type?: 'text' | 'textarea' | 'number' | 'date' | 'select' | 'checkbox' | 'multi'
  required?: boolean; options?: string[]; reference?: string; min?: number; default?: Value; readonly?: boolean
}
export interface ActionDefinition { id: string; label: string; from: string[]; to: string; roles?: string[]; approval?: boolean; reason?: boolean; fields?: FieldDefinition[] }
export interface ModuleDefinition { id: string; title: string; group: string; icon: string; prefix: string; fields: FieldDefinition[]; actions: ActionDefinition[]; roles: string[]; initial: string; editable: string[]; columns?: string[] }
export interface ListQuery { keyword?: string; status?: string; from?: string; to?: string; page?: number; pageSize?: number; sort?: string; direction?: string }
