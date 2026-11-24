import {authedFetch} from './http'
export async function downloadIssuanceRecord(reportNos:string[],kind:'product'|'engineering') {
  const response=await authedFetch('/api/reports/issuance-record/export',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reportNos,kind}),
  })
  if(!response.ok){
    const error=await response.json().catch(()=>null)
    throw new Error(error?.message||'发放登记表导出失败，请重试')
  }
  const url=URL.createObjectURL(await response.blob())
  const link=document.createElement('a');link.href=url
  link.download=`报告发放登记表（${kind==='engineering'?'工程类':'产品类'}）.docx`
  document.body.appendChild(link);link.click();link.remove()
  setTimeout(()=>URL.revokeObjectURL(url),1000)
}
