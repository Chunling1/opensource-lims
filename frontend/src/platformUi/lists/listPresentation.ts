import {sortableBusinessColumns} from '../listSorting'
import {reportGroupChoices,matchesReportGroup} from '../reportGroups'
import {handlingDefault,handlingStates,handlingQuery} from '../handlingStatus'
import { useLiveSearch } from '@/composables/liveSearch'
import {reportDataStatusChoices} from '../reportDataStatus'
import { toRef } from 'vue'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {ElMessageBox} from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'
import { normalizeError } from '../../services/common/errors'
import { exportRowsXlsx } from '@/services/xlsxExport'
import { submitSampleDispose, voidSample, changeResubmit } from '@/services/pipeline'
import { flowColumns,flowStates,flowDateFields,flowDateEnabled } from '../../types/samples/flow'
import { disposalColumns,disposalStates,disposalRequirements,disposalSearchFields } from '../../types/samples/disposal'
import { taskQueryColumns } from '../../types/testing/taskQuery'
import { assignmentSearchFields,assignmentDateFields,assignmentConclusions } from '../../types/testing/assignment'
import { commissionChangeColumns } from '../../types/commissions/commissionChanges'
import { cancellationColumns,cancellationDate } from '../../types/commissions/cancellationApproval'
import { sampleTypes } from '../../types/commissions/registration'
import { emptyPlanSelection, inboundColumns } from '../../types/samples/inbound'
import { planMatches } from './planCatalogue'
import flowKeys from './FlowList.keys.json'
import storageKeys from './StorageList.keys.json'
import taskKeys from './TaskList.keys.json'
import changeKeys from './ChangeList.keys.json'
import cancelKeys from './CancellationList.keys.json'
type Row=Record<string,any>
export function listRow(r:Row):Row {
 const dates=r.workflowDates||{}, state=r.sampleStatus||'', ri=r.returnInfo||{};
 return {...r,source:r,id:r.reportNo,code:r.sampleNo,reportCode:r.reportNo,commissionCode:r.entrustNo,
 name:r.sampleOrProjectName||r.projectName||'',parameters:r.testItems||r.project||'',customer:r.client,owner:r.registrar||r.owner||'',dataEntryPerson:r.owner||'',
 contractCode:r.erpContractNo||'',contact:r.consignor,phone:r.consignorPhone,customerAddress:r.clientAddress,
 commissionDate:r.entrustDate||r.date,engineeringName:r.projectName,projectName:r.schemeName,testPlan:r.schemeName,testPlanName:r.schemeName,
 sampleType:({普通:'原始样品',英文:'英文报告样品',分项:'分项/阶段性报告样品',补充:'补充报告'} as Row)[r.reportCategory]||r.reportCategory||'',
 dataStatus:r.dataStatus||r.sampleStatus||r.status,requestedTestDate:/^\d{4}-\d{2}-\d{2}/.test(r.deadline||'')?r.deadline:'',inboundDate:r.inboundTime||dates.sampleInboundAt||'',outboundDate:r.outboundTime||r.samplePickup?.outTime||'',
 collectionDate:r.pickupTime||r.samplePickup?.pickupTime||dates.samplePickupAt||'',outboundPerson:r.outboundPerson||r.samplePickup?.managerName||r.samplePickup?.managerId||'',collectionPerson:r.pickupPerson||r.samplePickup?.receiverName||'',
 customerRequirement:r.sampleDisposition||'',disposalStatus:state==='已处置'?'样品已处置':canDisposeState(r)?'样品待处置':'',
 flowStatus:state==='已处置'?'样品已处置':state==='已领取'?'样品已领取':state==='已出库'?'样品已出库':state==='已入库'?'样品已入库':state,
 problemSource:ri.source||'',problemSubmitter:ri.by||'',problemSubmittedAt:ri.date||'',problemDescription:ri.note||'',
 processingResult:r.status==='委托更改中'?'问题处理中':ri.source?'问题已处理':'',approvalResult:r.voided?'已作废':'未作废',
 canReturn:false,canPrintTask:false}
}
export function canDisposeState(r:Row){return ['已领取','已出库'].includes(r.sampleStatus)&&!['待合同评审','待样品入库','待样品领取','检测录入中','退回待重传','委托更改中','检测更改中'].includes(r.workflowStatus||r.status)}
export function filterList(rows:Row[],q:Row,kind:string){return rows.filter(r=>{
 if(!matchesReportGroup(r,q.reportGroup))return false;
 const text=String(q.keyword||q.contains||q.code||'').trim().toLocaleLowerCase(),field=q.code?'code':q.searchField||'code';
 if(text&&!String(r[field]||'').toLocaleLowerCase().includes(text))return false;
 if(q.status&&r[kind==='flow'?'flowStatus':kind==='disposal'?'disposalStatus':'dataStatus']!==q.status)return false;
 if(q.sampleType&&r.sampleType!==q.sampleType||q.requirement&&r.customerRequirement!==q.requirement||q.source&&r.problemSource!==q.source||q.result&&r[kind==='cancel'?'approvalResult':'processingResult']!==q.result)return false;
 if(q.conclusion&&r.resultStatus!==q.conclusion)return false;
 const date=String(r[kind==='change'?'problemSubmittedAt':kind==='disposal'?'disposalDate':q.dateField||'commissionDate']||'').slice(0,10);
 if(q.from&&(!date||date<q.from)||q.to&&(!date||date>q.to))return false;
 for(const f of flowDateFields){if(kind==='flow'&&flowDateEnabled(f.key,q.status)){const range=q.dates?.[f.key]||{},d=String(r[f.column]||'').slice(0,10);if(range.from&&(!d||d<range.from)||range.to&&(!d||d>range.to))return false}}
 return planMatches(r.source||r,q.plans)
 }).sort((a,b)=>String(a[q.sort]||'').localeCompare(String(b[q.sort]||''),'zh-CN',{numeric:true})*(q.direction==='desc'?-1:1))}
export function useListPresentation(c:Row,kind:string){
 const keys=kind==='flow'?flowKeys:['disposal','inbound','outbound'].includes(kind)?storageKeys:kind==='task'?taskKeys:kind==='change'?changeKeys:cancelKeys;
 const allColumns:any[]= sortableBusinessColumns([...(kind==='flow'?flowColumns:['inbound','outbound'].includes(kind)?inboundColumns:kind==='disposal'?disposalColumns:kind==='task'?taskQueryColumns:kind==='change'?commissionChangeColumns:cancellationColumns)]);
 const m=reactive<Row>(Object.fromEntries(keys.map(k=>[k,undefined]))),draft=reactive<Row>({reportGroup:'',code:'',contains:'',keyword:'',searchField:'code',status:c.serverPaging?handlingDefault(kind):'',sampleType:'',result:'',source:'',from:'',to:'',dateField:kind==='disposal'?'disposalDate':kind==='cancel'?'voidedAt':'commissionDate',requirement:'',conclusion:''}),q=reactive<Row>({...draft,page:1,pageSize:10,sort:'code',direction:'asc',plans:emptyPlanSelection()}),dates=reactive(Object.fromEntries(flowDateFields.map(f=>[f.key,{from:'',to:''}])));
 const selected=ref<string[]>([]),columnKeys=ref(allColumns.filter(x=>x.default||x.required).map(x=>x.key)),busy=ref(false),error=ref<any>(''),exporting=ref(false),planState=ref<any>(),plans=ref(emptyPlanSelection());
 const source=computed(()=>(c.rows||[]).filter((r:Row)=>kind!=='disposal'||r.sampleStatus==='已处置'||canDisposeState(r))), mapped=computed(()=>source.value.map(listRow)),filtered=computed(()=>c.serverPaging?mapped.value:filterList(mapped.value,q,kind));
 const loading=computed(()=>!!c.loading||busy.value),rowError=computed(()=>c.error?normalizeError(c.error):'');
 persistTableSettings(()=>`list:${kind}`,{columns:columnKeys,pageSize:toRef(q,'pageSize'),sort:toRef(q,'sort'),direction:toRef(q,'direction')},['flow','disposal'].includes(kind)?['reportCode']:[]);
 function patch(values:Row){if('columns'in values)columnKeys.value=allColumns.filter(x=>x.default||x.required).map(x=>x.key);Object.assign(q,values,{page:Number(values.page??q.page)||1,pageSize:Number(values.size??q.pageSize)||10})}
 async function load(){error.value='';try{await c.load()}catch(e){error.value=normalizeError(e)}}
 async function exportRows(only:boolean){if(loading.value||exporting.value)return;exporting.value=true;try{const exportData=c.serverPaging?(await c.exportListRows()).map(listRow):filtered.value;await exportRowsXlsx(c.title,allColumns.map(x=>({label:x.label,key:x.key,width:20})),only?exportData.filter((r:Row)=>selected.value.includes(r.id)):exportData)}catch(e){error.value=normalizeError(e)}finally{exporting.value=false}}
 const allowedDispose=(r:Row)=>!loading.value&&c.session.canAction('sample.dispose')&&canDisposeState(r.source||r);
 const allowedVoid=(r:Row)=>!loading.value&&c.session.canAction('sample.register.void')&&!r.source.voided&&['待合同评审','委托更改中'].includes(r.source.status);
 async function perform(action:()=>Promise<any>){if(busy.value)return;busy.value=true;error.value='';try{await action();m.disposalOperation=undefined;await c.load()}catch(e){error.value=normalizeError(e)}finally{busy.value=false}}
 Object.assign(m,{reportGroupOptions:computed(()=>reportGroupChoices(c.session)),title:computed(()=>c.title),mode:kind,disposal:kind==='disposal',outbound:kind==='outbound',states:computed(()=>handlingDefault(kind)?handlingStates(kind):reportDataStatusChoices(mapped.value)),allColumns,flowColumns,taskQueryColumns,commissionChangeColumns,cancellationColumns,
 columnKeys,columns:computed(()=>allColumns.filter(x=>x.required||columnKeys.value.includes(x.key))),selected,loading,error:rowError,actionError:error,exportError:error,operationError:error,operationBusy:busy,actionLoading:busy,exporting,
 rows:computed(()=>({items:c.serverPaging?mapped.value:filtered.value.slice((q.page-1)*q.pageSize,q.page*q.pageSize),total:c.serverPaging?c.listPage.total:filtered.value.length,page:q.page,pageSize:q.pageSize})),draft,query:q,dateDraft:dates,flowDateFields,flowDateEnabled,flowStates,disposalStates,disposalRequirements,disposalSearchFields,assignmentSearchFields,assignmentDateFields,assignmentConclusions,sampleTypes,
 taskQueryStates:computed(()=>reportDataStatusChoices(mapped.value)),changeProblemSources:computed(()=>[...new Set(mapped.value.map((r:Row)=>r.problemSource).filter(Boolean))]),changeProcessingResults:['','问题处理中','问题已处理'],cancellationStates:['未作废','已作废'],cancellationDate,
 more:false,drawer:false,planBusy:false,planError:'',plans,planState,activeFilters:computed(()=>Number(!!draft.from||!!draft.to)+Number(!!draft.conclusion)),testingMode:false,currentActor:computed(()=>c.session),
 patch,sort:(key:string)=>{q.direction=q.sort===key&&q.direction==='asc'?'desc':'asc';q.sort=key;q.page=1;selected.value=[]},toggleColumn:(key:string,checked:boolean)=>{if(allColumns.find(x=>x.key===key)?.required)return;columnKeys.value=checked?[...new Set([...columnKeys.value,key])]:columnKeys.value.filter(k=>k!==key)},
 search:()=>{liveSearch.cancel();Object.assign(q,draft,{dates:structuredClone(JSON.parse(JSON.stringify(dates))),plans:JSON.parse(JSON.stringify(plans.value)),page:1});selected.value=[]},applyPlans:(v:any)=>{plans.value=v.selection;planState.value=v},exportRows,load,
 view:(r:Row)=>c.view(r.source),canDispose:(r:Row,a:string)=>a==='dispose'&&allowedDispose(r),openDisposal:(r:Row,a:string)=>{if(a==='dispose'&&allowedDispose(r))m.disposalOperation={row:r,action:a}},
 submitDisposal:()=>{const r=m.disposalOperation?.row;if(r&&allowedDispose(r))return perform(()=>submitSampleDispose(r.id))},refreshOperation:load,
 canOperate:(r:Row,a:string)=>!loading.value&&!busy.value&&Boolean(a==='undo'?c.canUndoInbound?.(r.source):a==='receive'&&c.canReceive?.(r.source)),openOperation:(r:Row,a:string)=>{if(loading.value||busy.value)return;if(a==='undo'&&c.canUndoInbound?.(r.source))return perform(()=>c.undoInbound(r.source));if(a==='receive'&&c.canReceive?.(r.source))return c.receive(r.source)},
 canOutbound:(r:Row,a:string)=>!loading.value&&(a==='undo'?c.canRecall?.(r.source):a==='return'?c.canReturn?.(r.source):c.canDispatch?.(r.source)),openOutbound:(r:Row,a:string)=>{if(loading.value)return;if(a==='undo'&&c.canRecall?.(r.source))return perform(()=>c.recall(r.source));if(a==='dispatch'&&c.canDispatch?.(r.source)||a==='return'&&c.canReturn?.(r.source))c.dispatch(r.source)},
 canApproveCancellation:()=>false,openApproval:()=>{},canVoid:allowedVoid,voidRow:(r:Row)=>{if(allowedVoid(r))return c.confirmVoid(r.source,()=>perform(()=>voidSample(r.id)))},
 allowed:(r:Row)=>!loading.value&&r.source.status==='委托更改中'&&c.session.can(c.permission||'entrust.change.view'),edit:(r:Row)=>c.edit(r.source),complete:async(r:Row)=>{if(!m.allowed(r))return;try{await ElMessageBox.confirm('确认完成 '+r.code+' 的委托更改？','完成更改',{type:'warning'});await perform(()=>changeResubmit(r.id,{}))}catch(e){if(e instanceof Error)error.value=normalizeError(e)}},
 returnBusy:false,openReturn:()=>{},printTask:()=>{},taskView:(r:Row)=>c.view(r.source),taskEnter:(r:Row)=>c.enter(r.source),taskRestock:(r:Row)=>c.restock(r.source),taskDispose:(r:Row)=>{if(allowedDispose(r))m.disposalOperation={row:r,action:'dispose'}},canRestock:(r:Row)=>r.source.canReturnStock===true&&c.session.canAction('sample.return_stock'),
 });
 watch(()=>JSON.stringify([q,c.activeListKind]),()=>{if(c.serverPaging&&(!c.activeListKind||c.activeListKind===kind))c.setListQuery({...handlingQuery(q),presentation:kind})},{immediate:true});
 watch(()=>c.identity,()=>{selected.value=[];m.disposalOperation=undefined;m.attachmentId=undefined;error.value='';q.page=1});const liveSearch = useLiveSearch(() => draft.contains, () => m.search());return m as any
}
