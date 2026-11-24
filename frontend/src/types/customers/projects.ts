import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
export interface ProjectField { key: string; label: string; kind?: 'unit' | 'number' | 'select' | 'region'; options?: readonly string[] }
export interface ProjectSection { title: string; fields: ProjectField[] }
export const projectSections: ProjectSection[] = [
  { title: '委托人信息', fields: [{ key: 'client', label: '委托人' }, { key: 'clientPhone', label: '委托人电话' }] },
  { title: '委托单位信息', fields: [{ key: 'customer', label: '委托单位', kind: 'unit' }, { key: 'customerAddress', label: '委托单位地址' }, { key: 'customerLegal', label: '委托单位法人' }, { key: 'customerPhone', label: '委托单位电话' }, { key: 'customerPostcode', label: '委托单位邮编' }] },
  { title: '工程基本属性', fields: [
    { key: 'supervisionNumber', label: '监督登记号' }, { key: 'tradingCode', label: '工程编码（交易中心）' }, { key: 'name', label: '工程名称' }, { key: 'subproject', label: '分项工程' },
    { key: 'address', label: '工程地址' }, { key: 'area', label: '工程片区' }, { key: 'province', label: '工程所属行政区域（省）', kind: 'region' }, { key: 'city', label: '工程所属行政区域（市）', kind: 'region' }, { key: 'district', label: '工程所属行政区域（区县）', kind: 'region' }, { key: 'regionCode', label: '区域代码' },
    { key: 'projectType', label: '工程类型', kind: 'select', options: ['市政', '建筑', '水务', '交通', '其他'] }, { key: 'buildingNature', label: '建筑性质', kind: 'select', options: ['保障房', '非保障房'] }, { key: 'structure', label: '建筑结构型式', kind: 'select', options: ['框架结构', '剪力墙结构', '膜结构'] },
    { key: 'buildingArea', label: '建筑面积', kind: 'number' }, { key: 'floors', label: '建筑结构层数', kind: 'number' }, { key: 'director', label: '项目总监' }, { key: 'manager', label: '项目经理' },
  ] },
  { title: '工程主体单位', fields: ['建设', '施工', '监理', '设计', '勘察'].flatMap((label, index) => {
    const key = ['developer', 'builder', 'supervisor', 'designer', 'surveyor'][index]!
    return [{ key: `${key}Code`, label: `${label}单位代码` }, { key: `${key}Contact`, label: `${label}单位联系人` }, { key: `${key}Phone`, label: `${label}单位电话` }, { key, label: `${label}单位`, kind: 'unit' as const }]
  }) },
  { title: '监督信息', fields: [{ key: 'authorityCode', label: '监督单位编号' }, { key: 'authority', label: '监督单位' }, { key: 'inspectorCode', label: '监督员编号' }, { key: 'inspector', label: '监督员' }, { key: 'inspectorPhone', label: '监督员电话' }] },
  { title: '见证取样信息', fields: [{ key: 'witnessUnit', label: '见证单位', kind: 'unit' }, { key: 'witness', label: '见证人' }, { key: 'witnessCode', label: '见证号' }, { key: 'witnessPhone', label: '见证人电话' }, { key: 'samplingUnit', label: '抽样单位', kind: 'unit' }, { key: 'sampler', label: '抽样人' }, { key: 'samplingPlace', label: '抽样地点' }] },
]
export const projectFields = projectSections.flatMap(section => section.fields)
export type ProjectDraft = Record<string, string>
export interface CustomerProject extends ProjectDraft { id: string; code: string; departmentId: string }
export interface ProjectQuery { name?: string; code?: string; supervisionNumber?: string; ids?: string[]; page?: number; pageSize?: number }
export interface ProjectPage { items: CustomerProject[]; total: number; page: number; pageSize: number }
export interface ProjectOptions { organizations: string[]; regions: Record<string, string[]> }
export const emptyProject = (batch = false): ProjectDraft => Object.fromEntries(projectFields.map(field => [field.key, !batch && ['province', 'city'].includes(field.key) ? '北京市' : '']))
export const canManageProjects = (actor: Actor) => actor.roles.some(role => ['admin', 'commissions'].includes(role))
export const projectColumns: readonly TableColumn[] = [
  { key: 'code', label: '工程编号', required: true }, { key: 'name', label: '工程名称', default: true, truncate: 30, fullTitle: true }, { key: 'supervisionNumber', label: '监督登记号', default: true },
  { key: 'address', label: '工程地址', default: true, truncate: 30, fullTitle: true }, { key: 'developer', label: '建设单位', default: true, truncate: 24, fullTitle: true }, { key: 'supervisor', label: '监理单位', default: true, truncate: 24, fullTitle: true }, { key: 'builder', label: '施工单位', default: true, truncate: 24, fullTitle: true },
]
