import {request} from '@/services/http'
export type FinanceMode = 'send' | 'reverse'
interface FinanceProgress {
  retry?: {intakeId:string;attemptId:string;label:string} | null
  receipts?: {operation:string;receivedAt:string}[]
}
export interface FinanceState extends FinanceProgress {done:boolean;allowed:boolean;message:string;refreshOnly?:boolean}
export interface FinanceResult extends FinanceProgress {intakeId:string;done:boolean;blocked:boolean;retryable:boolean;message:string}
const base='/api/erp-outbound'
const post=<T>(path:string,body:unknown)=>request<T>(base+path,{method:'POST',headers:{'X-Erp-Outbound':'1'},body:JSON.stringify(body)})
export const retryFinanceStep=(retry:NonNullable<FinanceProgress['retry']>)=>
  post<FinanceResult>(`/one-click/${encodeURIComponent(retry.intakeId)}/retry/${encodeURIComponent(retry.attemptId)}`,{})
export const manualStatus=(reportNo:string)=>request<Record<FinanceMode,FinanceState>>(`${base}/reports/${encodeURIComponent(reportNo)}/manual-status`)
export async function runManualFinance(reportNo:string,mode:FinanceMode,onProgress:(result:FinanceResult)=>void=()=>{}):Promise<FinanceResult>{
  let result=await post<FinanceResult>(`/reports/${encodeURIComponent(reportNo)}/one-click`,{phase:mode==='send'?'contract':'issuance',mode,nonce:crypto.randomUUID()})
  onProgress(result)
  // Advance at most four distinct ACK-gated steps; never retry failed steps automatically.
  for(let step=0;step<(mode==='send'?1:4)&&!result.done&&!result.blocked;step++){
    result=await post<FinanceResult>(`/one-click/${encodeURIComponent(result.intakeId)}/advance`,{})
    onProgress(result)
  }
  return result
}
