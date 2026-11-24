export interface PrintOptions { type: 'product' | 'engineering'; layout: 'normal' | 'extended'; copies: number[] }
export type PrintScenario = 'normal' | 'slow' | 'failure' | 'expired'
export interface PrintDocument { documentType: 'commission' | 'sample'; documentCode: string }
export type PrintRequest = PrintDocument & PrintOptions
export interface PrintContext {
  kind: 'commissions' | 'samples'; id: string; code: string; name: string; canPrint: boolean
}
export interface PrintTask extends PrintRequest {
  id: string; createdAt: number; kind: PrintContext['kind']; sourceId: string
  status: 'queued' | 'running' | 'ready' | 'failed'; stage?: string; error?: string; expiresAt: number
}
export const printStatus = { queued: '排队中', running: '生成中', ready: '已生成', failed: '生成失败' }
export const copyNames = ['第一联', '第二联', '第三联', '第四联']
export function printDescription(task: PrintOptions) { return `${task.type === 'product' ? '产品' : '工程'} · ${task.layout === 'normal' ? '标准版' : '扩展版'} · ${task.copies.map(n => copyNames[n - 1]).join('、')}` }
