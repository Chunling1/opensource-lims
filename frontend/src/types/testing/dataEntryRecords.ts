import type { RegistrationPage } from '../commissions/registration'

export interface FieldChange { field: string; before: string; after: string }
export interface EntryChangeRow extends FieldChange { id: string; actor: string; at: string; type: string; sequence: number }
export interface EntryIssueRow {
  destination?: string
  id: string; submitterId: string; submitter: string; description: string; type: string; submittedAt: string
  handlerId: string; handler: string; opinion: string; handledAt: string; sequence: number
}
export type EntryRecordKind = 'commission' | 'testing' | 'issues' | 'workflow'
export interface EntryRecordsQuery { kind: EntryRecordKind; page?: number; pageSize?: number }
export type EntryRecordsPage = RegistrationPage<EntryChangeRow | EntryIssueRow>
