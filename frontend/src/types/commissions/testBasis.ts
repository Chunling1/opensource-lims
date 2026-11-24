import type { RegistrationPage } from './registration'

export interface TestBasisStandard {
  id: string
  controlNumber: string
  qualification: string
  code: string
  name: string
  category: string
  location: string
  implementedDate: string
  revokedDate: string
  extensionDays: number | null
  replacementCode: string
  notes: string
}
export const testBasisSearchFields = [
  { key: 'code', label: '标准编号' }, { key: 'name', label: '标准名称' }, { key: 'controlNumber', label: '受控号' },
] as const
export const testBasisFilterFields = [
  { key: 'code', label: '标准编号' }, { key: 'name', label: '标准名称' }, { key: 'category', label: '类别' },
  { key: 'qualification', label: '标准资质类别' }, { key: 'controlNumber', label: '受控号' },
] as const
export const testBasisSorts = [
  { value: 'code:asc', label: '标准编号 ↑' }, { value: 'code:desc', label: '标准编号 ↓' },
  { value: 'name:asc', label: '标准名称 ↑' }, { value: 'name:desc', label: '标准名称 ↓' },
  { value: 'implementedDate:asc', label: '实施日期 ↑' }, { value: 'implementedDate:desc', label: '实施日期 ↓' },
] as const
export const maxTestBasisSelection = 50
export type TestBasisSort = typeof testBasisSorts[number]['value']
export interface TestBasisQuery {
  planId: string
  code?: string; name?: string; category?: string; qualification?: string; controlNumber?: string
  departmentCategory?: string; ownDepartment?: boolean; sort?: TestBasisSort
  ids?: string[]; page?: number; pageSize?: number
}
export interface TestBasisPage extends RegistrationPage<TestBasisStandard> { departmentCategories: string[]; qualifications: string[] }
export interface TestBasisSelection { ids: string[]; text: string; englishBookMarks: boolean; separators: string[] }
