import {sortableBusinessColumns,compareBusinessRows,businessSortKeys} from '../listSorting'
import {reportGroupChoices,matchesReportGroup} from '../reportGroups'
import {handlingDefault,handlingStates,handlingQuery} from '../handlingStatus'
import { useLiveSearch } from '@/composables/liveSearch'
import {reportDataStatusChoices} from '../reportDataStatus'
import { toRef } from 'vue'
import { reportQueryColumns } from './reportQueryColumns'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {computed,reactive,ref,watch} from 'vue'
import keys from './ReportStagePresentation.keys.json'
import {type ErrorValue} from '../../services/common/errors'
import {exportRowsXlsx} from '@/services/xlsxExport'
import type {ReportReviewStage} from './reportStageUndo'
import {planMatches} from '../lists/planCatalogue'
type Row=Record<string,any>
export type ReportStageContext = Row & {undoReport: (reportNo:string, stage:ReportReviewStage)=>Promise<void>}
export function createReportStagePresentation(c:ReportStageContext){
 const m=reactive<Row>(Object.fromEntries(keys.map(k=>[k,undefined]))),selected=ref<string[]>([]),busy=ref(false),error=ref<ErrorValue>(''),q=reactive<Row>({page:1,pageSize:10,searchField:c.route?.query?.keyword?'reportCode':'all',contains:String(c.route?.query?.keyword||'')}),draft=reactive<Row>({reportGroup:'',searchField:c.route?.query?.keyword?'reportCode':'all',contains:String(c.route?.query?.keyword||''),status:c.serverPaging?handlingDefault(c.pageKey):'',sampleType:'',conclusion:'',dateField:'commissionDate',from:'',to:'',checkStatus:'',state:'',collectionMethod:''});
 q.status=draft.status;q.sort='';q.direction='asc';
 const label=computed(()=>c.pageKey==='approval'?'批准':'审核');
 const baseColumns=[{key:'code',label:'样品编号',required:true},{key:'reportCode',label:'报告编号'},{key:'customer',label:'委托单位',wrap:true},{key:'name',label:'检测项目',wrap:true},{key:'dataStatus',label:'数据状态'},{key:'sampleStatus',label:'样品状态'},{key:'version',label:'报告版本'},{key:'deadline',label:'时限'}],columns=computed(()=>sortableBusinessColumns(c.pageKey==='query'?reportQueryColumns:[...baseColumns,...reportQueryColumns.filter(col=>businessSortKeys.has(col.key)&&!baseColumns.some(base=>base.key===col.key))])),chosen=ref(baseColumns.map(x=>x.key));
 persistTableSettings(()=>`report-stage:${c.pageKey}`,{columns:chosen,pageSize:toRef(q,'pageSize'),sort:toRef(q,'sort'),direction:toRef(q,'direction')});
 const dateFields=[{value:'commissionDate',label:'委托日期'},{value:'sampleRegisteredAt',label:'样品登记日期'},{value:'testStartDate',label:'试验开始日期'},{value:'testEndDate',label:'试验结束日期'},{value:'checkDate',label:'校核日期'},{value:'auditDate',label:'审核日期'},{value:'approvalDate',label:'批准日期'},{value:'printDate',label:'签发日期'},{value:'archiveDate',label:'归档日期'},{value:'distributionDate',label:'发放日期'}]
 const mapRows=(rows:Row[])=>rows.map((r:Row)=>({...r,id:r.reportNo,code:r.sampleNo,reportCode:r.reportNo,commissionCode:r.entrustNo,customer:r.client,name:r.testItems||r.project,commissionDate:r.entrustDate||'',resultStatus:r.resultStatus||'',checkStatus:c.pageKey==='approval'?(r.status==='待批准'?'未批准':'已批准'):(r.status==='待审核'?'未审核':'已审核'),dataStatus:r.dataStatus||r.status,source:r,actions:[{id:'preview',label:'查看',enabled:true},{id:'workflow',label:c.pageKey==='release'?'发放':c.pageName,enabled:c.pageKey!=='query'&&(c.pageKey!=='release'||r.allowedActions?.includes('report.distribution.complete'))&&(c.pageKey!=='archive'||r.allowedActions?.some((a:string)=>['report.archive.pass','report.archive.undo'].includes(a)))}]}));const data=computed(()=>mapRows(c.workRows)),filtered=computed(()=>c.serverPaging?data.value:data.value.filter((r:Row)=>{
  if(!matchesReportGroup(r,q.reportGroup))return false
  if(!planMatches(r.source||r,q.plans))return false
  const term=String(q.contains||'').toLowerCase()
  if(term&&!(q.searchField==='all'?Object.values(r).filter(x=>typeof x!=='object').join(' '):String(r[q.searchField]||'')).toLowerCase().includes(term))return false
  if(q.status&&r.dataStatus!==q.status||q.sampleType&&r.reportCategory!==q.sampleType)return false
  if(q.conclusion&&r.resultStatus!==q.conclusion||q.checkStatus&&r.checkStatus!==q.checkStatus)return false
  if(q.collectionMethod&&r.collectionMethod!==q.collectionMethod)return false
  if(q.state&&r[c.pageKey==='release'?'releaseStatus':'issueStatus']!==q.state)return false
  const date=String(r[q.dateField]||'').slice(0,10)
  return !(q.from&&(!date||date<q.from)||q.to&&(!date||date>q.to))
 }).sort((a:Row,b:Row)=>compareBusinessRows(a,b,q)));
 async function load(){busy.value=true;try{await c.refreshReportList()}finally{busy.value=false}}
 watch(()=>c.pageKey,()=>{selected.value=[];Object.assign(draft,{contains:'',status:c.serverPaging?handlingDefault(c.pageKey):'',conclusion:'',from:'',to:'',dateField:'commissionDate',checkStatus:'',state:'',collectionMethod:''});Object.assign(q,draft,{page:1});error.value='';m.statusAction=undefined;m.statusError=''}, {flush:'sync'})
 Object.assign(m,{
 reportGroupOptions:computed(()=>reportGroupChoices(c.session)),
 applyPlans:(value:Row)=>{m.plans=value.selection;m.planState=value},
 title:computed(()=>c.pageName),stage:computed(()=>c.pageKey),config:computed(()=>({label:label.value,pending:c.pageKey==='approval'?'待批准':'待审核'})),query:q,draft,more:false,activeFilters:computed(()=>Number(!!draft.from||!!draft.to)+Number(!!draft.conclusion)+Number(!!draft.checkStatus)+Number(!!draft.state)+Number(!!draft.collectionMethod)),dateInput:undefined,
 rows:computed(()=>({items:c.serverPaging?data.value:filtered.value.slice((q.page-1)*q.pageSize,q.page*q.pageSize),total:c.serverPaging?c.reportPageState.total:filtered.value.length,page:q.page,pageSize:q.pageSize})),selected,loading:computed(()=>c.reportPresentationLoading||busy.value),error:computed(()=>error.value||c.reportPresentationError||''),actionBusy:false,exporting:false,exportError:'',planError:'',planBusy:false,planState:undefined,drawer:false,plans:{groupIds:[],planIds:[],excludedPlanIds:[]},toolbarActions:[],canQuickReview:false,
 reportCheckColumns:columns,columns:computed(()=>columns.value.filter(x=>chosen.value.includes(x.key))),columnKeys:chosen,
 reportCheckSearchFields:computed(()=>[{value:'all',label:'全部'},...columns.value.map(x=>({value:x.key,label:x.label}))]),reportCheckStates:computed(()=>handlingDefault(c.pageKey)?handlingStates(c.pageKey):reportDataStatusChoices(data.value)),sampleTypes:['普通','英文','分项','补充'],assignmentConclusions:['合格','不合格','不判定','复检','其它'],reportCheckDateFields:dateFields,reportCheckStatuses:computed(()=>c.pageKey==='approval'?['未批准','已批准']:['未审核','已审核']),
 reportCheckActions:computed(()=>[{label:'查看',icon:'ti ti-eye'},{label:label.value,icon:'ti ti-circle-check'},{label:'撤销'+label.value,icon:'ti ti-arrow-back-up'}]),
 actionAllowed:(row:Row,action:string)=>action==='查看'||(action.startsWith('撤销')?row.rowProjection==='recall':row.rowProjection!=='recall')&&c.session.canAction(`report.${c.pageKey}.${action.startsWith('撤销')?'undo':'pass'}`),
 rowAction:(row:Row,action:string)=>{if(!m.actionAllowed(row,action))return;if(action.startsWith('撤销')){m.statusError='';m.statusAction={row}}else c.openForm(row.source,action==='查看')},load,
 statusAction:undefined,statusError:'',undoCheck:async()=>{
  const target=m.statusAction,stage=c.pageKey
  if(!target||m.actionBusy||!['review','approval'].includes(stage))return
  m.actionBusy=true;m.statusError=''
  try{await c.undoReport(target.row.source.reportNo,stage);if(m.statusAction===target&&c.pageKey===stage)m.statusAction=undefined}
  catch(e){if(m.statusAction===target&&c.pageKey===stage)m.statusError=e}
  finally{m.actionBusy=false}
 },
 search:()=>{liveSearch.cancel();error.value='';if((draft.checkStatus.startsWith('已')||draft.state.startsWith('已'))&&draft.status==='待处理')draft.status='';Object.assign(q,draft,{plans:JSON.parse(JSON.stringify(m.plans)),page:1})},
 patch:(v:Row)=>{if('columns'in v)chosen.value=baseColumns.map(x=>x.key);if(v.page)q.page=Number(v.page);if(v.size)q.pageSize=Number(v.size);if(v.sort&&businessSortKeys.has(v.sort)){q.sort=v.sort;q.direction=v.direction==='desc'?'desc':'asc';q.page=1;selected.value=[]}},toggleColumn:(key:string,checked:boolean)=>chosen.value=checked?[...new Set([...chosen.value,key])]:chosen.value.filter(k=>k!==key),
 exportRows:async()=>exportRowsXlsx(c.pageName,columns.value.filter(x=>chosen.value.includes(x.key)).map(x=>({key:x.key,label:x.label,width:20})),(c.serverPaging?mapRows(await c.exportReportRows()):filtered.value).filter((r:Row)=>!selected.value.length||selected.value.includes(r.id))),
 });watch(()=>JSON.stringify([q,c.pageKey,c.pagingActive]),()=>{if(c.serverPaging&&c.pagingActive!==false)c.setReportQuery({...handlingQuery(q),...(q.state?{[c.pageKey==='release'?'releaseStatus':'issueStatus']:q.state}:{})})},{immediate:true});const liveSearch = useLiveSearch(() => draft.contains, () => m.search());return m as any
}
