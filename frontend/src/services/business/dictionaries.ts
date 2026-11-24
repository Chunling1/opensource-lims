import type { SampleAction, SampleStatus } from '../../types/sample'
export const categories = ['水质', '食品', '土壤', '化学品', '材料', '其他']
export const customers = ['华清环境检测中心', '安禾食品有限公司', '新源材料研究院', '市政水务实验室']
export const units = ['份', '瓶', '袋', 'g', 'mL', 'kg', 'L']
export const projects = ['pH 值', '重金属', '微生物', '水分', '密度', '有机物', '成分分析']
export const statusLabels: Record<SampleStatus, string> = { pending: '待接收', received: '已接收', returned: '已退回' }
export const statusClasses: Record<SampleStatus, string> = { pending: 'bg-warning-subtle text-warning', received: 'bg-success-subtle text-success', returned: 'bg-danger-subtle text-danger' }
export const actionLabels: Record<SampleAction, string> = { created: '登记样品', edited: '修改资料', received: '接收样品', returned: '退回样品', resubmitted: '重新提交' }
export function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
