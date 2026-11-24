import {sortableBusinessColumns} from '../listSorting'
import {reportGroupChoices,matchesReportGroup} from '../reportGroups'
import {handlingStates,handlingQuery,PENDING_STATUS} from '../handlingStatus'
import { reportDataStatus, reportDataStatusChoices } from '../reportDataStatus'
import { toRef } from 'vue'
import { persistTableSettings } from '../../services/platform/tablePreferences'
import {sampleRegAction,voidSample} from '@/services/pipeline'
import {ElMessageBox} from 'element-plus'
import {sampleWorkflowDateFields} from '../../types/commissions/sampleWorkflow'
import {computed,reactive,ref,watch} from 'vue'
import keys from './registration.keys.json'
import {clientYearRange} from '../../services/common/date'
import {AppError, type ErrorValue} from '../../services/common/errors'
import {commissionColumns as templateCommissionColumns,sampleColumns as templateSampleColumns} from '../../services/commissions/registrationColumns'
import {commissionSearchFields,sampleSearchFields} from '../../types/commissions/registration'
import {exportRowsXlsx} from '@/services/xlsxExport'
type Row=Record<string,any>
const commissionColumns: any[]=sortableBusinessColumns([...templateCommissionColumns,...Object.entries({erpProjectNo:'外部ERP项目编号',erpProjectType:'外部ERP项目类型',contractPartyA:'合同甲方',otherPartyA:'其他甲方（付款方）',handlerDepartment:'委托经办部门',dataStatus:'数据状态',clientAddress:'委托单位地址'}).map(([key,label])=>({key,label,default:false,wrap:true}))])
const sampleColumns: any[]=sortableBusinessColumns([...templateSampleColumns,...Object.entries({erpProjectNo:'外部ERP项目编号',erpProjectType:'外部ERP项目类型',erpContractNo:'外部ERP合同编号',handler:'委托经办人',amount:'金额',reportCategory:'报告类别',reportFormat:'报告格式',testCategory:'检测类别',commissionDate:'委托日期',sampleRegisteredAt:'样品登记时间',sendDate:'送样日期',reportTitle:'报告标题',sealRequirement:'盖章要求',samplingUnit:'抽样单位',sampler:'抽样人',samplingTime:'抽样时间',contractReviewedAt:'合同评审通过操作时间'}).map(([key,label])=>({key,label,default:false,wrap:true}))])

const money=(v:unknown)=>v==null||String(v).trim()===''?null:Number.isFinite(Number(v))?Number(v):null
export function registrationRows(rows:Row[]):Row[]{return rows.map(r=>({...r,id:String(r.id),code:r.no,contract:r.erpContractNo||r.info?.erpContractNo||'',name:r.projectName,customer:r.client,owner:r.handler||r.owner,commissionDate:r.entrustDate||r.date,receivableAmount:money(r.amount),contact:r.consignor,source:r}))}
export function registrationSamples(rows:Row[]){return rows.flatMap(c=>(c.linkedSamples||[]).map((r:Row)=>({...r,dataStatus:reportDataStatus(r),id:String(r.reportNo),code:r.sampleNo,reportCode:r.reportNo,sampleType:({普通:'原始样品',英文:'英文报告样品',分项:'分项/阶段性报告样品',补充:'补充报告'} as Row)[r.reportCategory]||r.reportCategory||'',standardPrice:money(r.amount),discountPrice:money(r.discountPrice),actualPrice:money(r.actualPrice),name:r.sampleOrProjectName||r.projectName,customer:r.client,commissionId:String(c.id),commissionCode:c.no,commissionDate:r.entrustDate||c.entrustDate||c.date,testPlan:r.schemeName,commissionOwner:r.handler||c.handler,owner:r.registrar||r.owner,parameters:r.testItems||r.project,source:r})))}
// Review reports have their own authorization scope. A missing parent must not
// remove an already authorized report or expose an unauthorized commission.
export function reviewSampleRows(parents:Row[],samples:Row[]){
 const byNumber=new Map(parents.map(p=>[p.no,p]));
 return samples.flatMap(r=>registrationSamples([{...(byNumber.get(r.entrustNo)||{id:r.entrustId??'',no:r.entrustNo}),linkedSamples:[r]}]));
}
/** Filtering is over the controller's complete authorized list, never a single backend page. */
export function filterRegistration(rows:Row[],q:Row){const value=(r:Row,k:string)=>String(r[k]??'');return rows.filter(r=>{
 if(!matchesReportGroup(r,q.reportGroup))return false;
 const term=String(q.contains||q.keyword||'').trim().toLocaleLowerCase(),field=q.searchField||'all';
 if(term&&!(field==='all'?Object.values(r).filter(v=>typeof v!=='object').join(' '):value(r,field)).toLocaleLowerCase().includes(term))return false;
 if(q.status&&r.status!==q.status&&!(q.status==='已完成'&&r.status==='委托完成')&&!(q.status==='未完成'&&r.status==='委托中'))return false;
 if(q.dataStatus&&r.dataStatus!==q.dataStatus)return false;
 if(q.sampleType&&r.sampleType!==q.sampleType)return false;
 for(const [key,v]of Object.entries(q.fields||{}))if(v&&!value(r,key).toLocaleLowerCase().includes(String(v).toLocaleLowerCase()))return false;
 for(const [key,range]of Object.entries(q.workflowDates||{}) as [string,any][]){if(range.enabled){const d=String(r.workflowDates?.[key]||'').slice(0,10);if(range.from&&(!d||d<range.from)||range.to&&(!d||d>range.to))return false}}
 const from=q.from||q.commissionFrom,to=q.to||q.commissionTo,date=value(r,'commissionDate').slice(0,10);
 return !(from&&(!date||date<from)||to&&(!date||date>to));
 }).sort((a,b)=>q.sort?value(a,q.sort).localeCompare(value(b,q.sort),'zh-CN',{numeric:true})*(q.direction==='desc'?-1:1):0)}
export function registrationActions(row:Row,c:Row){const r=row.source||row,complete=r.status==='委托完成';return [{id:complete?'uncomplete':'complete',label:complete?'撤销完成':'完成登记',disabled:complete?!(c.session.can('entrust.registration.view')&&(r.completionAccount===c.session.account||(c.session.fullPlatformAuthority || c.session.roleKey === 'admin')||c.session.account==='admin')):!(r.status==='委托中'&&(c.session.can('entrust.registration.view')||c.session.canAction('entrust.register.complete'))),disabledReason:'当前状态或权限不允许此操作'}]}
export function useRegistrationPresentation(c:Row){
 const m=reactive<Row>(Object.fromEntries(keys.map(k=>[k,undefined]))),q=reactive<Row>({c:{page:1,pageSize:5,searchField:'all',status:'',contains:'',...clientYearRange()},s:{reportGroup:'',page:1,pageSize:10,searchField:'all',dataStatus:'',sampleType:'',contains:'',commissionFrom:clientYearRange().from,commissionTo:clientYearRange().to}}),scope=ref(c.samplesOnly?'all':'current'),selected=ref<string[]>([]),samplesSelected=ref<string[]>([]),busy=ref(false),error=ref<ErrorValue>('');
 const columns=ref(commissionColumns.filter(x=>x.default).map(x=>String(x.key))),sColumns=ref(sampleColumns.filter(x=>x.default).map(x=>String(x.key)));
 const mode=computed(()=>c.mode||'registration');
 q.c.sort='';q.c.direction='asc';q.s.sort='';q.s.direction='asc';
 persistTableSettings(()=>`registration:${mode.value}:${c.samplesOnly?'samples':'workspace'}:commissions`,{columns,pageSize:toRef(q.c,'pageSize'),sort:toRef(q.c,'sort'),direction:toRef(q.c,'direction')});
 persistTableSettings(()=>`registration:${mode.value}:${c.samplesOnly?'samples':'workspace'}:samples`,{columns:sColumns,pageSize:toRef(q.s,'pageSize'),sort:toRef(q.s,'sort'),direction:toRef(q.s,'direction')});
 if(mode.value==='review'){q.s.commissionFrom='';q.s.commissionTo='';q.s.dataStatus=c.serverPaging?PENDING_STATUS:'合同评审中'}
 if(c.serverPaging&&c.samplesOnly&&mode.value==='registration')q.s.dataStatus=PENDING_STATUS;
 const rows=computed(()=>registrationRows(c.backendEntrust)),allSamples=computed(()=>c.serverPaging?reviewSampleRows(c.backendEntrust,c.registrationPageSamples):c.reviewSamples ? reviewSampleRows(c.backendEntrust,c.reviewSamples) : registrationSamples(c.backendEntrust));
 const filtered=computed(()=>c.serverPaging?rows.value:filterRegistration(rows.value,q.c)),filteredSamples=computed(()=>c.serverPaging?allSamples.value:filterRegistration(allSamples.value.filter(r=>scope.value==='all'||selected.value.includes(r.commissionId)),q.s));
 const page=(items:Row[],query:Row)=>({items:items.slice((query.page-1)*query.pageSize,query.page*query.pageSize),total:items.length,page:query.page,pageSize:query.pageSize});
 function select(ids:string[]){selected.value=ids;c.onWorkbenchSelectionChange(rows.value.filter(r=>ids.includes(r.id)).map(r=>r.source));q.s.page=1}
 function choose(r:Row){c.selectedRow=r.source||r;c.selectedRows=[r.source||r]}
 const unsupported=(message:string)=>{error.value=new AppError('BUSINESS_RULE',message)}
 function navigate(to:Row){const r=to.kind==='samples'?allSamples.value.find(r=>r.id===to.id):rows.value.find(r=>r.id===to.id);if(to.id==='new'){if(c.samplesOnly&&to.kind==='samples'){c.openAdd();return}if(to.kind==='samples'){const parent=rows.value.find(r=>r.id===(to.parentId||selected.value[0]));if(parent&&parent.status==='委托完成')c.addSampleFor(parent.source);else unsupported('请选择一张已完成登记的委托，再新增样品')}else c.openWizard('entrust');return}
 if(!r&&to.path){const path=to.path.split('/'),id=decodeURIComponent(path.at(-2)),sample=path.includes('samples')?allSamples.value.find(r=>r.id===id):undefined,row=sample||rows.value.find(r=>r.id===id);if(row){choose(row);if(path.at(-1)==='assess')c.reviewSample?.(row.source);else if(sample)c.printSample?.(row.source);else {const linked=allSamples.value.filter(s=>s.commissionId===row.id);if(linked.length===1)c.printSample?.(linked[0]!.source);else if(linked.length>1){scope.value='current';select([row.id]);unsupported('该委托包含多个样品，请在下方样品行选择打印，查看或下载对应评审人签字的委托单')}else void c.openSelectedEntrustPrint()}}return}
 if(!r)return unsupported('记录已变化，请刷新列表');choose(r);if(to.kind==='samples')to.edit?c.editSample(r.source):c.viewSample(r.source);else to.edit?c.editEntrust(r.source):c.viewEntrust(r.source)}
 async function reload(){busy.value=true;error.value='';try{await c.loadEntrust()}catch(e){error.value=new AppError('NETWORK',e instanceof Error?e.message:String(e))}finally{busy.value=false}}
 async function action(kind:string,row:Row,id:string){if(kind!=='commissions'){
 const allowed=sampleActions(row).find(a=>a.id===id&&!a.disabled);if(!allowed)return;
 if(id==='review')return c.reviewSample?.(row.source);if(id==='unreview')return c.undoReview?.(row.source);
 try{await ElMessageBox.confirm('确认对 '+row.code+' 执行'+allowed.label+'？',allowed.label,{type:'warning'});busy.value=true;if(id==='void')await voidSample(row.id);else await sampleRegAction(row.id,id as 'complete'|'uncomplete');await c.loadEntrust()}catch(e){if(e instanceof Error)unsupported(e.message)}finally{busy.value=false}return;
 }const permitted=registrationActions(row,c).find(a=>a.id===id&&!a.disabled);if(!permitted)return;choose(row);busy.value=true;try{await (id==='complete'?c.completeSelectedEntrust():c.uncompleteSelectedEntrust())}finally{busy.value=false}}
 function sampleActions(row:Row){const r=row.source||row,can=c.session.canAction;
 if(mode.value==='query')return [];
 if(mode.value==='review')return [{id:'review',label:'开始评审',disabled:r.status!=='待合同评审'||(r.sampleRegState||'登记完成')!=='登记完成'||!c.session.can('entrust.contract_review.view')},{id:'unreview',label:'撤销评审',disabled:!r.allowedActions?.includes('report.contract_review.undo')},{id:'void',label:'作废',disabled:!can('sample.register.void')||!['待合同评审','委托更改中'].includes(r.status)}];
 return [{id:'complete',label:'完成登记',disabled:r.sampleRegState!=='登记中'||!c.session.can('entrust.sample_register.view')},{id:'uncomplete',label:'撤销完成',disabled:r.sampleRegState!=='登记完成'||r.status!=='待合同评审'||!(r.canRecallSampleRegistration??((c.session.fullPlatformAuthority || c.session.roleKey === 'admin')||can('sample.register.undo')))},{id:'void',label:'作废',disabled:!can('sample.register.void')||!['待合同评审','委托更改中'].includes(r.status)}]
 }
 Object.assign(m,{
 reportGroupOptions:computed(()=>reportGroupChoices(c.session)),
 samplesOnly:!!c.samplesOnly,actionKind:'commissions',attachmentKind:'commissions',quickReviewRecords:[],
 context:computed(()=>({title:c.pageName,workspace:mode.value})),review:computed(()=>mode.value==='review'),inquiry:computed(()=>mode.value==='query'),route:c.route,registrationRoot:'/inspection/entrust/registration',currentActor:computed(()=>c.session),operationError:error,
 commissionColumns,sampleColumns,availableSampleColumns:sampleColumns,commissionSearchFields,sampleSearchFields,inquirySampleSearchFields:sampleSearchFields,registrationDataStatusOptions:computed(()=>[{value:'',label:'全部状态'},...(c.samplesOnly?handlingStates('register'):reportDataStatusChoices(allSamples.value)).map(s=>({value:s,label:s}))]),
 columnKeys:columns,sampleColumnKeys:sColumns,visibleColumns:computed(()=>commissionColumns.filter(x=>columns.value.includes(x.key))),visibleSampleColumns:computed(()=>sampleColumns.filter(x=>sColumns.value.includes(x.key))),
 commissions:computed(()=>c.serverPaging?{items:rows.value,total:c.commissionPage.total,page:q.c.page,pageSize:q.c.pageSize}:page(filtered.value,q.c)),samples:computed(()=>c.serverPaging?{items:allSamples.value,total:c.registrationSamplePage.total,page:q.s.page,pageSize:q.s.pageSize}:page(filteredSamples.value,q.s)),commissionQuery:q.c,basicCommissionQuery:q.c,sampleQuery:q.s,basicSampleQuery:q.s,selectedCommissions:selected,selectedSamples:samplesSelected,
 scope,sampleReady:computed(()=>scope.value==='all'||selected.value.length>0),current:computed(()=>rows.value.find(r=>r.id===selected.value[0])),currentCaption:computed(()=>rows.value.filter(r=>selected.value.includes(r.id)).map(r=>r.code).join('、')),collapsed:false,
 cLoading:computed(()=>c.entrustPresentationLoading||busy.value),sLoading:computed(()=>(c.entrustSamplesLoading??c.entrustPresentationLoading)||busy.value),cError:computed(()=>c.entrustPresentationError||''),sError:computed(()=>c.entrustSamplesError||''),currentError:'',actionLoading:busy,exporting:false,notice:computed(()=>mode.value==='review'&&['合同评审中',PENDING_STATUS].includes(q.s.dataStatus)?'当前仅在待合同评审的记录里搜索。选择“全部状态”可查询其他阶段。':''),pushBusy:false,
 registrationCanWrite:(_:unknown,kind:string)=>c.session.canCorrectBusinessData?true:mode.value==='review'?c.session.can('entrust.contract_review.view'):c.session.can(kind==='commissions'?'entrust.registration.view':'entrust.sample_register.view'),canReadSamples:computed(()=>c.session.canCorrectBusinessData||c.session.can('entrust.sample_register.view')||c.session.can('entrust.query.view')||c.session.can('entrust.contract_review.view')),
 registrationCanLink:()=>c.session.can('entrust.sample_register.view'),registrationCanAddSample:(_:unknown,status:string)=>status==='委托完成'&&c.session.can('entrust.sample_register.view'),
 canAddSample:computed(()=>c.samplesOnly?c.session.can('entrust.sample_register.view'):selected.value.length===1&&rows.value.find(r=>r.id===selected.value[0])?.status==='委托完成'&&c.session.can('entrust.sample_register.view')),
 workspaceCanEdit:(_:unknown,kind:string,row:Row)=>c.session.canCorrectBusinessData&&!c.session.businessReadOnly?true:mode.value==='review'?false:kind==='commissions'?row.status!=='委托完成'&&c.session.can('entrust.registration.view'):row.source?.sampleRegState==='登记中'&&!row.source?.voided&&c.session.can('entrust.sample_register.view'),
 workspaceActions:(_:unknown,kind:string,row:Row)=>kind==='commissions'?(mode.value==='registration'?registrationActions(row,c):[]):sampleActions(row),sampleReadOnlyReason:(status:string)=>['作废','voided'].includes(status)?'已作废样品只读':undefined,
 selectCommissions:select,selectCommissionRow:(id:string)=>select(selected.value.includes(id)?selected.value.filter(s=>s!==id):[id]),showSamples:(id:string)=>{scope.value='current';select([id])},changeScope:(s:string)=>{scope.value=s;q.s.page=1},
 search:(prefix:string,query:Row)=>Object.assign(q[prefix],query,{page:1}),sort:(prefix:string,key:string)=>{const v=q[prefix];v.direction=v.sort===key&&v.direction==='asc'?'desc':'asc';v.sort=key;v.page=1},patch:(changes:Row)=>{for(const [k,v]of Object.entries(changes)){if(k==='collapsed')m.collapsed=!!v;else if(k==='cPage'||k==='sPage')q[k[0]!].page=Number(v)||1;else if(k==='cSize'||k==='sSize')q[k[0]!].pageSize=Number(v)||10}},
 toggleColumn:(key:string,checked:boolean)=>columns.value=checked?[...new Set([...columns.value,key])]:columns.value.filter(k=>k!==key),resetColumns:()=>columns.value=commissionColumns.filter(x=>x.default).map(x=>x.key),
 toggleSampleColumn:(key:string,checked:boolean)=>sColumns.value=checked?[...new Set([...sColumns.value,key])]:sColumns.value.filter(k=>k!==key),resetSampleColumns:()=>sColumns.value=sampleColumns.filter(x=>x.default).map(x=>x.key),
 loadCommissions:reload,loadSamples:reload,loadCurrent:reload,refresh:reload,navigate,router:{push:navigate},link:(kind:string,id:string,edit=false)=>({kind,id,edit}),addSampleLink:(id:string)=>({kind:'samples',id:'new',parentId:id}),openActions:action,
 openAttachments:(kind:string,id:string)=>{if(kind==='samples'){const row=allSamples.value.find(r=>r.id===id);if(row){choose(row);c.openQueryAttachments()}}else unsupported('现平台委托附件归属样品，请在下方样品行打开附件管理')},
 reviewDataStatusOptions:computed(()=>[{value:'',label:'全部状态'},...handlingStates('contract_review').map(v=>({value:v,label:v}))]),inquirySampleDataStatusOptions:computed(()=>[{value:'',label:'全部状态'},...reportDataStatusChoices(allSamples.value).map(v=>({value:v,label:v}))]),
 canQuickReview:computed(()=>mode.value==='review'&&samplesSelected.value.length===1&&allSamples.value.some(r=>r.id===samplesSelected.value[0]&&!sampleActions(r)[0]?.disabled)),quickReviewLoading:false,openQuickReview:()=>{const r=allSamples.value.find(r=>r.id===samplesSelected.value[0]);if(r)c.reviewSample?.(r.source)},
 advancedCommissionDraft:{fields:{},status:'',useDate:false,from:'',to:''},advancedSampleDraft:{fields:{},dataStatus:'',sampleType:'',conclusion:'',useDate:false,from:'',to:'',workflowDates:Object.fromEntries(sampleWorkflowDateFields.map(f=>[f.key,{enabled:false,from:'',to:''}]))},advancedBusy:false,advancedError:'',usingAdvancedCommission:false,usingAdvancedSample:false,closeAdvanced:()=>{m.advancedSearchKind=undefined},
 searchAdvancedCommission:(v:Row)=>{Object.assign(q.c,{...v,from:v.useDate?v.from:'',to:v.useDate?v.to:'',page:1});m.advancedCommissionDraft=v;m.usingAdvancedCommission=true;m.advancedSearchKind=undefined},
 searchAdvancedSample:(v:Row)=>{Object.assign(q.s,{...v,commissionFrom:'',commissionTo:'',from:v.useDate?v.from:'',to:v.useDate?v.to:'',page:1});m.advancedSampleDraft=v;m.usingAdvancedSample=true;m.advancedSearchKind=undefined},
 sampleToolbarActions:[{id:'bulk',label:'批量修改',icon:'ti ti-edit',disabled:true}],exportData:async(kind:string,onlySelected:boolean)=>{const exported=c.serverPaging?await c.exportRegistrationRows(kind==='commissions'?'c':'s'):null;const data=exported?(kind==='commissions'?registrationRows(exported.map((r:Row)=>({...r,no:r.entrustNo}))):reviewSampleRows(c.backendEntrust,exported)):kind==='commissions'?filtered.value:filteredSamples.value,ids=kind==='commissions'?selected.value:samplesSelected.value,cols=kind==='commissions'?commissionColumns:sampleColumns;await exportRowsXlsx(kind==='commissions'?'委托清单':'样品清单',cols.map(x=>({label:x.label,key:x.key,width:20})),onlySelected?data.filter(r=>ids.includes(r.id)):data)},
 });watch(()=>JSON.stringify([q.c,mode.value]),()=>{if(c.serverPaging)c.setRegistrationQuery('c',{...q.c})},{immediate:true});watch(()=>JSON.stringify([q.s,scope.value,selected.value,mode.value]),()=>{if(c.serverPaging)c.setRegistrationQuery('s',{...handlingQuery(q.s,'dataStatus'),...(scope.value==='all'?{}:{commissionIds:selected.value})})},{immediate:true});watch(()=>mode.value,()=>{selected.value=[];samplesSelected.value=[];Object.assign(q.c,{page:1});Object.assign(q.s,{page:1})});return m as any
}
