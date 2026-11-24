import {reportDataStates} from './reportDataStatus'
export const PENDING_STATUS='待处理'
// Include persisted legacy labels still admitted by the canonical lifecycle.
const lifecycleStates=[...reportDataStates.filter(s=>s!=='样品单已作废'),'已归档','待领取','待检测','检测中','样品入库中（历史数据）','样品出库领取中（历史数据）']
const states:Record<string,string[]>={
 register:lifecycleStates,
 contract_review:lifecycleStates,
 inbound:['样品入库中','样品出库领取中'],outbound:['样品出库领取中','样品出库领取完成','检测数据录入中'],
 data_entry:['样品出库领取完成','检测数据录入中','报告审核中'],data_change:['检测数据录入中','检测更改中'],
 review:['报告审核中','报告批准中'],approval:['报告批准中','报告签发中','报告盖章中','报告已盖章，归档中，未发放'],
 print:['报告签发中','报告盖章中','报告已盖章，归档中，未发放','报告已归档，发放中','报告发放完成','已归档'],
 archive:lifecycleStates,release:['报告已归档，发放中','报告发放完成'],
}
export function handlingStates(view:string){return states[view]?[PENDING_STATUS,...new Set(states[view])]:reportDataStates}
export function handlingDefault(view:string){return view in states?PENDING_STATUS:''}
export function handlingQuery(query:Record<string,any>,key='status'){
 return {...query,[key]:query[key]===PENDING_STATUS?'':query[key],rowProjection:query[key]===PENDING_STATUS?'active':''}
}
