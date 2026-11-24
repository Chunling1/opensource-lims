import { localPlanSelection } from '../../services/common/localPlanSelection'
import { platformRequest } from '../../services/platform/http'
import { emptyPlanSelection } from '../../types/samples/inbound'
type Row=Record<string,any>
const key=(dept:string,code:string)=>JSON.stringify([dept,code])
const departments=(r:Row)=>[r.department,r.testDept,r.testDepartment,r.schemeDept].filter(Boolean)
export function planMatches(row:Row,selection:any){
 if(!selection||!selection.groupIds?.length&&!selection.planIds?.length)return true
 const matches=(id:string)=>{try{const[d,code]=JSON.parse(id);return code===row.schemeCode&&(!d||departments(row).includes(d))}catch{return false}}
 return !(selection.excludedPlanIds||[]).some(matches)&&((selection.planIds||[]).some(matches)||(selection.groupIds||[]).some((id:string)=>departments(row).includes(id)))
}
export function planCounts(rows:Row[]){
 const early=['待合同评审','待样品入库','待样品领取','检测录入中','退回待重传','委托更改中','检测更改中']
 return Object.fromEntries(Object.entries({
  flow:()=>true,
  disposal:(r:Row)=>r.sampleStatus==='已处置'||['已领取','已出库'].includes(r.sampleStatus)&&!early.includes(r.status),
  taskQuery:(r:Row)=>['已领取','已出库'].includes(r.sampleStatus),
  dataEntry:(r:Row)=>['检测录入中','退回待重传','待审核'].includes(r.status),
  dataChange:(r:Row)=>r.status==='检测更改中',
  inbound:(r:Row)=>r.status==='待样品入库',outbound:(r:Row)=>r.sampleStatus==='已入库',
 }).map(([scope,predicate])=>[scope+'SampleCount',rows.filter(predicate).length]))
}
// Scheme IDs are selection keys only; all writes continue to use backend report IDs.
export async function planRequest(path:string,q:Row,signal?:AbortSignal){
 const reportViews:Record<string,string>={'report-query':'query','report-review':'review','report-approval':'approval','report-print':'print','report-signing':'print','report-archive':'archive','report-distribution':'release'}
 const reportView=reportViews[String(q.sampleScope||'')]
 const scope=String(q.sampleScope||'flow').replace(/-([a-z])/g,(_,c)=>c.toUpperCase()).replace('dataChanges','dataChange')+'SampleCount'
 const counts=reportView?[scope]:Object.keys(planCounts([]))
 const [result,list]=await Promise.all([
  platformRequest<{tree:Row[]}>('/api/reports/lib/schemes',{method:'POST',body:{keyword:''},signal}),
  platformRequest<{rows:Row[]}>(reportView?'/api/reports/plan-counts':'/api/samples/plan-counts',{method:'POST',body:reportView?{view:reportView}:{view:'flow_query',includeVoided:false},signal}),
 ])
 const rows=list.rows||[],groups=result.tree.map(g=>({id:g.dept,name:g.dept,kind:'group'}))
 const plans:Row[]=result.tree.flatMap(g=>(g.schemes||[]).map((s:Row)=>({id:key(g.dept,s.code),parentId:g.dept,name:s.name,code:s.code,groupName:g.dept,kind:'plan',...Object.fromEntries(counts.map(k=>[k,rows.filter(r=>r.schemeCode===s.code&&departments(r).includes(g.dept)).reduce((sum,r)=>sum+Number((reportView?r.sampleCount:r[k])||0),0)]))})))
 const nodes=groups.map(g=>({...g,...Object.fromEntries(counts.map(k=>[k,plans.filter(p=>p.parentId===g.id).reduce((sum,p)=>sum+p[k],0)]))}))
 const catalogue={groups:groups.map(g=>({id:g.id})),plans:plans.map(p=>({id:p.id,parentId:p.parentId,name:p.name})),populatedPlanIds:plans.filter(p=>p[scope]>0).map(p=>p.id)}
 if(path.endsWith('/selection'))return{...localPlanSelection(catalogue,q.selection||emptyPlanSelection(),q.toggle),catalogue}
 const term=String(q.keyword||'').toLowerCase(),items=term?plans.filter(p=>(p.name+' '+p.code+' '+p.groupName).toLowerCase().includes(term)):q.parentId?plans.filter(p=>p.parentId===q.parentId):nodes
 const page=Number(q.page)||1,pageSize=Number(q.pageSize)||10
 return{items:items.slice((page-1)*pageSize,page*pageSize),total:items.length,page,pageSize}
}
