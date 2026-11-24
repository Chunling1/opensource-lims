// Both stock queues use the same saved sample fields and table preferences.
export { inboundColumns as outboundColumns } from './inbound'
export const outboundStates = ['样品出库中', '样品待领取', '样品已领取'] as const
export type OutboundAction = 'dispatch' | 'undo' | 'return'
export interface OutboundReceipt { account: string; name: string; date: string }
export const outboundReturnTypes = [{ value: 'commission', label: '委托信息错误' }, { value: 'assignment', label: '任务分配错误' }] as const
export type OutboundReturnType = typeof outboundReturnTypes[number]['value']
export interface OutboundReturn { type: OutboundReturnType; reason: string; details: string; date: string }
export type OutboundSubmission = { action: 'dispatch'; receipt: OutboundReceipt } | { action: 'undo' } | { action: 'return'; returned: OutboundReturn }
export interface OutboundInfo {
  receipt?: OutboundReceipt & { recordedAt: string; recordedBy: { id: string; name: string } }
  returns?: (OutboundReturn & { recordedAt: string; recordedBy: { id: string; name: string }; previousDataStatus: string })[]
}
