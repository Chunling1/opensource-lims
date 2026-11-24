import type { TableColumn } from '../common/table'
import type { DemoAttachment } from '../commissions/registration'
export const personnelFields = [
  { key: 'name', label: '姓名', required: true }, { key: 'code', label: '编号', required: true },
  { key: 'gender', label: '性别', required: true }, { key: 'education', label: '文化程度' },
  { key: 'qualification', label: '职称/资格', required: true }, { key: 'major', label: '所学专业' },
  { key: 'graduatedAt', label: '毕业时间', date: true }, { key: 'position', label: '岗位/职务', required: true },
  { key: 'testingScope', label: '检测业务范围' }, { key: 'inspectionScope', label: '检查业务范围' },
  { key: 'notes', label: '备注' }, { key: 'department', label: '所在部门', required: true },
  { key: 'birthDate', label: '出生日期', date: true }, { key: 'identityNumber', label: '身份证号' },
  { key: 'ethnicity', label: '民族' }, { key: 'nativePlace', label: '籍贯' },
  { key: 'politicalStatus', label: '政治情况' }, { key: 'school', label: '毕业院校' },
  { key: 'workStartedAt', label: '参加工作时间', date: true }, { key: 'joinedAt', label: '来单位时间', date: true },
] as const
export type PersonnelKey = typeof personnelFields[number]['key']
export const personnelAttachmentKinds = [
  { key: 'socialSecurity', label: '社保号附件' }, { key: 'education', label: '学历附件' },
  { key: 'degree', label: '学位附件' }, { key: 'qualification', label: '职称附件' },
] as const
export type PersonnelAttachmentKind = typeof personnelAttachmentKinds[number]['key']
export interface PersonnelHistory { id: string; date: string; name: string; project: string; issuer: string; place: string; content: string; result: string; attachments: DemoAttachment[] }
export interface PersonnelProfile {
  accountId: string; formerName: string; birthAddress: string; socialSecurityNumber: string; degree: string
  attachments: Record<PersonnelAttachmentKind, DemoAttachment[]>
  awards: PersonnelHistory[]; trainings: PersonnelHistory[]
}
export const emptyPersonnelProfile = (): PersonnelProfile => ({ accountId: '', formerName: '', birthAddress: '', socialSecurityNumber: '', degree: '', attachments: { socialSecurity: [], education: [], degree: [], qualification: [] }, awards: [], trainings: [] })
export type PersonnelDraft = Record<PersonnelKey, string> & { profile?: PersonnelProfile }
export interface PersonnelRecord extends PersonnelDraft { id: string; version: number; departmentId: string; deleted?: boolean }
export const personnelColumns: TableColumn<PersonnelKey>[] = personnelFields.map(f => ({ key: f.key, label: f.label, sort: f.key, required: f.key === 'name', default: ['name', 'code', 'gender', 'qualification', 'position', 'testingScope', 'inspectionScope', 'department'].includes(f.key), truncate: ['testingScope', 'inspectionScope', 'notes'].includes(f.key) ? 24 : undefined }))
export type PersonnelFilterKey = 'name' | 'code' | 'school' | 'major' | 'qualification' | 'education' | 'department'
export interface PersonnelQuery extends Partial<Record<PersonnelFilterKey, string>> { sort?: string; direction?: 'asc' | 'desc'; page?: number; pageSize?: number; ids?: string[] }
export interface PersonnelPage { items: PersonnelRecord[]; total: number; page: number; pageSize: number }
export const emptyPersonnel = (): PersonnelDraft => Object.fromEntries(personnelFields.map(f => [f.key, ''])) as Record<PersonnelKey, string>
export const personnelOptions: Partial<Record<PersonnelKey | 'degree', string[]>> = {
  politicalStatus: ['党员', '团员', '民主党派', '群众'],
  education: ['研究生', '本科', '大专', '高中', '高中以下'],
  degree: ['博士', '硕士', '学士'], qualification: ['教授级高级工程师', '高级工程师', '工程师', '助理工程师', '技术员'],
  position: ['负责人', '技术负责人', '质量负责人', '检测员', '审核人', '批准人', '采样员', '管理员'],
}
