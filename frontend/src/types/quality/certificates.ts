import type { DemoAttachment } from '../commissions/registration'

export type CertificateListKind = 'people' | 'certificates' | 'projects'
export type CertificateListRow = { id: string; [key: string]: string }
export interface CertificateQuery {
  filters?: Record<string, string>; scope?: 'related' | 'all'; parentIds?: string[]
  page?: number; pageSize?: number; ids?: string[]; columns?: string[]
}
export interface CertificatePage { items: CertificateListRow[]; total: number; page: number; pageSize: number }
export interface CertificateRecord { id: string; personId: string; version: number; category: string; number: string; notes: string; files: DemoAttachment[] }
export interface ApprovedProjectRecord { id: string; certificateId: string; version: number; code: string; item: string; category: string; notes: string }
export interface CertificateDetail extends CertificateRecord { name: string; code: string; projectCount: number }
export interface ApprovedProjectDetail extends ApprovedProjectRecord { name: string; number: string }
export interface CertificateOptions { departments: string[]; categories: string[]; projectCategories: string[] }
export const certificateExportColumns: Record<CertificateListKind, Record<string, string>> = {
  people: { code: '编号', name: '姓名', gender: '性别', department: '所在部门', position: '职务' },
  certificates: { code: '编号', name: '姓名', category: '上岗证类别', number: '上岗证号', notes: '备注', attachments: '附件' },
  projects: { code: '检测项目代码', item: '核准检测项目', category: '类别', name: '姓名', number: '上岗证号', notes: '备注' },
}
