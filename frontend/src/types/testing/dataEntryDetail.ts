import { clientToday } from '../../services/common/date'
import type { DemoAttachment, DemoEvent, RegistrationSample } from '../commissions/registration'

export const entryConclusions = ['不判定', '复检', '合格', '不合格'] as const
export const normalizeConclusion = (value: string) => value === '其它' ? '不判定' : value
export interface TrialDate { kind: 'single' | 'range'; from: string; to: string }
export function legacyTrialDates(from = '', to = ''): TrialDate[] {
  if (!from && !to) from = to = clientToday()
  return [{ kind: 'range', from, to }]
}
export function trialDatesText(dates: TrialDate[]): string {
  return [...dates].filter(row => row.from || row.to).sort((a, b) => a.from.localeCompare(b.from)).map(row => row.kind === 'single' || row.from === row.to ? row.from : `${row.from || '待填写'} 至 ${row.to || '待填写'}`).join('；')
}
export interface TrialForm {
  conclusion: string; conclusionStatus: string; failedParameters: string; notes: string
  tester1Id: string; tester2Id: string; reviewerId: string; approverId: string
  testDates: TrialDate[]; testStartDate: string; testEndDate: string; calibrationEnabled: boolean; calibrationDate: string
  reportDateEnabled: boolean; reportDate: string; environment: string; equipmentIds: string[]
  showStandard: boolean; showEquipmentCode: boolean; showEquipmentModel: boolean; showEquipmentManufacturer: boolean; showEquipmentSerial: boolean
}
export function emptyTrialForm(): TrialForm {
  return { conclusion: '', conclusionStatus: '', failedParameters: '', notes: '', tester1Id: '', tester2Id: '', reviewerId: '', approverId: '', testDates: legacyTrialDates(), testStartDate: '', testEndDate: '', calibrationEnabled: false, calibrationDate: '', reportDateEnabled: false, reportDate: '', environment: '', equipmentIds: [], showStandard: true, showEquipmentCode: true, showEquipmentModel: false, showEquipmentManufacturer: false, showEquipmentSerial: false }
}
export interface EntryTemplate { id: string; version: string; labels: string[]; error?: string }
export type EntryFileKind = 'report' | 'appendix' | 'original'
export interface EntryFile extends DemoAttachment { kind: EntryFileKind; template?: EntryTemplate }
export type EntryFileSummary = Omit<EntryFile, 'dataUrl'>
export type EntryScenario = 'failure' | 'word-failure' | 'pdf-failure' | 'slow'
export interface EntryJob { id: string; sourceRevision: number; sourceKey: string; templateKey: string; createdAt: number; status: 'running' | 'ready' | 'failed'; phase?: 'queued' | 'preparing' | 'converting' | 'composing' | 'ready' | 'failed'; error?: string; scenario?: EntryScenario; stage?: string; elapsedMs?: number; fileErrors?: Record<string, string> }
export interface EntryTemplateJob {
  kind?: 'template' | 'complete-report'
  id: string; sourceKey: string; sourceRevision: number; layoutId: string; templateVersion: string; createdAt: number; conversionStartedAt?: number
  stage: 'word' | 'queued' | 'converting' | 'ready' | 'word-failed' | 'pdf-failed'
  wordAvailable: boolean; pdfAvailable: boolean; elapsedMs: number; error?: string; scenario?: EntryScenario; wordOnly?: boolean
}
export interface EntryState {
  version: number; reportRevision: number; form: TrialForm; files: EntryFile[]; job?: EntryJob
  layoutId?: string; layoutAdopted?: boolean; templateJobs?: EntryTemplateJob[]; taskSnapshots?: Record<string, EntryDetail>
  reportConfirmation?: { taskId: string; at: string; actor: string }
  events: DemoEvent[]; requests: { id: string; actor: string; fingerprint: string }[]
}
export interface EntryCapabilities { canView: boolean; canEdit: boolean; canManageReport: boolean; canManageOriginals: boolean; canComplete: boolean; canUndo: boolean; canCheck?: boolean; canReportCheck?: boolean; canReportReview?: boolean; canReportApprove?: boolean }
export interface EntryPerson { id: string; name: string }
export type EntryPersonRole = 'tester' | 'reviewer' | 'approver'
export type EntryPeopleScope = 'preset' | 'department' | 'all'
export interface EntryPersonCandidate extends EntryPerson { departmentId: string; departmentName: string; certificateNumber: string; phone: string; disabledReason?: string; email?: string; position?: string; jobTitle?: string }
export interface EntryPeopleQuery { role: EntryPersonRole; scope?: EntryPeopleScope; keyword?: string; page?: number; pageSize?: number; excludeId?: string }
export interface EntryPeoplePage { items: EntryPersonCandidate[]; total: number; page: number; pageSize: number; scope: EntryPeopleScope; presetConfigured: boolean; departmentName: string }
export interface EntryEquipment extends EntryPerson {
  code: string; model: string; manufacturer: string; serial: string
  departmentId?: string; departmentName?: string; cycle?: string; status?: string
  lastCalibrationDate?: string; validUntil?: string; validityNote?: string
  selectable?: boolean; expiredNow?: boolean
  location?: string; inspectionOrganization?: string; storageOrganization?: string; remarks?: string
}
export interface EntryEquipmentConfig { version: number; associatedIds: string[]; defaultIds: string[] }
export function trialEquipmentText(form: TrialForm, equipment: EntryEquipment[]): string {
  return form.equipmentIds.map(id => {
    const item = equipment.find(item => item.id === id)
    if (!item) return `设备已不可选（${id}）`
    const name = [form.showEquipmentCode ? item.code : '', item.name].filter(Boolean).join(' ')
    return [name, form.showEquipmentModel ? item.model : '', form.showEquipmentManufacturer ? item.manufacturer : '', form.showEquipmentSerial ? item.serial : ''].filter(Boolean).join(' / ')
  }).join('；')
}
export interface EntryOptions { people: EntryPerson[]; reviewers: EntryPerson[]; approvers: EntryPerson[]; equipment: EntryEquipment[]; maxFileSize: number }
export interface EntryDetail {
  equipmentConfig: EntryEquipmentConfig
  sample: RegistrationSample; version: number; reportRevision: number; form: TrialForm; files: EntryFileSummary[]
  template: EntryTemplate; options: EntryOptions; capabilities: EntryCapabilities; job?: EntryJob
  layoutId: string; layoutAdopted: boolean; layouts: { id: string; label: string }[]; templateJob?: EntryTemplateJob; templateStale: boolean
  completeReportGeneration: { layoutIds: string[]; unavailableReason: string }
  completeReportJob?: EntryTemplateJob; completeReportStale: boolean
  reportStatus: 'pending' | 'running' | 'ready' | 'failed' | 'stale'; simulated: true
  reportConfirmed: boolean
}
