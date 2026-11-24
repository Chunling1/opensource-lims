import type { DemoAttachment, DemoEvent } from '../commissions/registration'

export interface OriginalRecord {
  id: string; name: string; source: 'file' | 'scan' | 'eln'; files?: DemoAttachment[]; eln?: { systemId: string; recordId: string; version?: string; updatedAt?: string; importedAt?: string; status?: string }
  // Compatibility only: preserve previously uploaded files; no OCR workflow remains.
  draft?: { files: DemoAttachment[] }; revisions?: { files: DemoAttachment[] }[]
}
export interface OriginalPreview { sourceVersion: number; file: DemoAttachment; pageCount: number }
export interface OriginalStore { version: number; records: OriginalRecord[]; migratedFileIds: string[]; requests: { id: string; actor: string; fingerprint: string }[]; events: DemoEvent[]; preview?: OriginalPreview }
export interface OriginalCapabilities { canUpload: boolean; canLink: boolean; canDelete: boolean }
export interface OriginalRecordView { id: string; name: string; source: 'file' | 'eln'; files: Omit<DemoAttachment, 'dataUrl'>[]; status: string; eln?: OriginalRecord['eln']; capabilities: OriginalCapabilities }
export interface OriginalContext { version: number; sampleVersion: number; sampleCode: string; records: OriginalRecordView[]; capabilities: OriginalCapabilities; maxFileSize: number; simulated: true }
export interface ElnRecord { systemId: string; id: string; sampleCode: string; name: string; status: string; version: string; updatedAt: string; fields: { label: string; value: string }[]; openUrl?: string; simulated: true }
export interface ElnPage { items: (ElnRecord & { linked: boolean })[]; total: number; page: number; pageSize: number }
