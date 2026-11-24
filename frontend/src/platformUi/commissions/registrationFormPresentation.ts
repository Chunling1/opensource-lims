import { sampleQuantityText, setSampleQuantity } from '@/composables/sampleQuantity'
import { computed, defineComponent, h, inject, provide, reactive, ref, watch } from 'vue'
import { emptySampleDetails } from '../../types/commissions/sampleForm'
import { emptySampleCommission } from '../../types/commissions/sampleCommission'
import { sampleFormTabs } from '../../views/commissions/forms/sampleSchema'
import { fetchCustomerPage } from '@/services/customerDirectory'
import { fetchSchemes } from '@/services/pipeline'
import { searchStdLib, searchStdLibPage } from '@/services/quality'
import { platformError } from '../apiErrors'
import { registrationSubprojects } from './registrationSubprojects'
import { listTechnicalSubprojects, type TechnicalSubproject } from '@/services/technicalSubprojects'
import type { FormSchema } from '../../types/forms'

export const commissionBindings: Record<string,string> = {code:'entrustNo',name:'projectName',contact:'consignor',phone:'consignorPhone',commissionDate:'entrustDate',contractId:'contractNo',contract:'erpProjectNo',erpContract:'erpContractNo',erpProjectType:'erpType',contractParty:'contractPartyA',payer:'otherPartyA',customer:'client',customerAddress:'clientAddr',customerLegalRepresentative:'clientLegal',customerPhone:'clientPhone',customerPostcode:'clientZip',projectRegistrationCode:'projectRecordNo',projectTradingCode:'projectTradeCode',projectAddress:'projectAddr',handlingDepartmentId:'handleDept',owner:'handler',handlerPhone:'handlerPhone',invoiceType:'invoiceType',taxpayerNumber:'taxNo',invoiceCompany:'companyName',invoiceAddress:'bizAddr',bankName:'bank',bankAccount:'account'}
export const sampleBindings: Record<string,string> = {testPlan:'schemeName',testPlanId:'schemeCode',testPlanCode:'schemeCode',testBasis:'testBasis',assessmentStandard:'standardJudge',testingDepartment:'testDept',testingLocation:'testLocation',nameplate:'nameplate',deliveryDate:'sendDate',appearance:'appearance',trademark:'trademark',productCode:'factoryNo',manufacturer:'manufacturer',productionDate:'produceDate',specification:'spec',internalNotes:'innerRemark',samplingOrganization:'sampleUnit',samplingLocation:'samplingLocation',sampler:'sampler',samplingTime:'sampleTime',samplingQuantity:'sampleQty',samplingBase:'entrustQty',inspectedOrganization:'inspectedUnit',taskSource:'taskSource',standardPrice:'stdPrice',paymentMethod:'payWay',paymentStatus:'payStatus',paidAmount:'paid',feeNotes:'otherSettle',externalDueDate:'sendOutTime',internalDueDate:'sendInTime',disposalMethod:'sampleHandle',reportDelivery:'deliverWay',mailingAddress:'mailAddr',reportCopies:'deliverStd',reportForm:'reportForm',onsiteArrangement:'fieldAgreement',appointmentDate:'innerStdDate'}
export const ControllerReturnLink = defineComponent({inheritAttrs:false,props:['to'],setup(_,{attrs,slots}){const c=inject<any>('platform-registration-context')!;return()=>h('a',{...attrs,href:'#',onClick:(e:Event)=>{e.preventDefault();c.requestClose()}},slots.default?.())}})
export function createRegistrationFormPresentation(c:any) {
 const isCommission=computed(()=>c.mode==='entrust'), editing=computed(()=>!c.readOnly&&!c.legacyMigrationHold), busy=computed(()=>c.submitting), loading=computed(()=>c.sampleFormLoading)
 const pickerOpen=ref(false),testPlanOpen=ref(false),testBasisOpen=ref(false),sampleTab=ref<'order'|'sample'>('sample'), sampleUploadPending=ref(false),testBasisPending=ref(false),error=ref<any>('')
 const subprojects=registrationSubprojects(c,e=>{error.value=platformError(e)})
 const technicalCatalog=ref<TechnicalSubproject[]>([]),technicalLoading=ref(false),technicalError=ref('')
 const technicalRows=computed<TechnicalSubproject[]>(()=>[...new Map([...technicalCatalog.value,...(c.s.detectionSubprojects||[])].map(r=>[r.id,r])).values()])
 const technicalLabel=(r:TechnicalSubproject)=>`#${r.id} ${r.projectName} / ${r.name}（${r.code}）`
 const technicalLabels=computed(()=>technicalRows.value.map(technicalLabel))
 const technicalText=computed(()=>(c.s.detectionSubprojects||[]).map(technicalLabel).join('；'))
 async function loadTechnical(){if(technicalLoading.value)return;technicalLoading.value=true;technicalError.value='';try{technicalCatalog.value=await listTechnicalSubprojects()}catch(e){technicalError.value=e instanceof Error?e.message:'读取失败'}finally{technicalLoading.value=false}}
 function chooseTechnical(value:string){if(!editing.value||busy.value)return;const labels=value.split('；').map(x=>x.trim()).filter(Boolean),rows=labels.map(label=>technicalRows.value.find(r=>technicalLabel(r)===label));if(rows.some(r=>!r)){error.value=platformError(Error('请从检测技术子项目选项中选择'));return}c.s.detectionSubprojects=JSON.parse(JSON.stringify(rows))}
 watch(isCommission,value=>{if(!value)void loadTechnical()},{immediate:true})
 const source=()=>isCommission.value?c.f:c.sampleEntrust
 const commission=reactive(new Proxy(emptySampleCommission(),{get(t,k:string){return commissionBindings[k]?source()[commissionBindings[k]]??'':(t as any)[k]},set(t,k:string,v){if(!editing.value||busy.value)return true;if(k==='contractId'){source().contractNo=v;if(isCommission.value)c.onPickContract(v);return true}if(k==='contractParty'&&(isCommission.value?c.contractPartyALocked:c.sampleContractPartyALocked))return true;if(commissionBindings[k])source()[commissionBindings[k]]=v;else(t as any)[k]=v;return true}}))
 const details=reactive(new Proxy(emptySampleDetails(),{get(t,k:string){
  if(sampleBindings[k])return c.s[sampleBindings[k]]??''
  if(k==='urgent')return c.s.urgent==='是'
  if(k==='testBasisIds')return c.selectedBasisIds()
  if(k==='assessmentStandardIds')return c.splitBasisValues(c.s.standardJudge)
  if(k==='testBasisSeparators')return (t as any)[k]?.length===Math.max(0,c.selectedBasisCodes().length-1)?(t as any)[k]:c.selectedBasisCodes().slice(1).map(()=> '；')
  if(k==='useAssessmentStandard')return (t as any)[k]||!!c.s.standardJudge
  if(k==='trademarkImage')return c.s.trademarkImage?{name:'商标',dataUrl:c.s.trademarkImage}:null
  const toggle:Record<string,string>={hasExternalDueDate:'sendOutTime',hasInternalDueDate:'sendInTime',hasAppointment:'innerStdDate'}
  if(toggle[k])return !!c.s[toggle[k]]
  if(k==='subprojects')return subprojects.get()
  if(k==='reportSettings')return settings
  return(t as any)[k]
 },set(t,k:string,v){if(!editing.value||busy.value)return true;
  if(sampleBindings[k])c.s[sampleBindings[k]]=v
  else if(k==='urgent')c.s.urgent=v?'是':'否'
  else if(k==='trademarkImage')c.s.trademarkImage=v?.dataUrl||''
  else if(k==='testBasisIds'){void c.onBasisIdsChange([...v])}
  else if(k==='useAssessmentStandard'){(t as any)[k]=v;if(!v)c.s.standardJudge=''}
  else if(k==='subprojects')subprojects.set(v)
  else if(k==='reportSettings')Object.assign(settings,v)
  else if(['hasExternalDueDate','hasInternalDueDate','hasAppointment'].includes(k)){if(!v)c.s[({hasExternalDueDate:'sendOutTime',hasInternalDueDate:'sendInTime',hasAppointment:'innerStdDate'} as any)[k]]=''}
  else(t as any)[k]=v;return true
 }}))
 const settings=reactive(new Proxy({formatId:'',titleId:'',languageId:'',layoutId:''},{get(_t,k:string){return c.s[({formatId:'reportType',titleId:'centerPrefix',languageId:'reportLanguage',layoutId:'reportTemplateVariant'} as any)[k]]||''},set(_t,k:string,v){if(editing.value&&!busy.value){const field=({formatId:'reportType',titleId:'centerPrefix',languageId:'reportLanguage',layoutId:'reportTemplateVariant'} as any)[k];if(k==='titleId'&&c.s.centerPrefix!==v)c.s.seal=v==='LAB'?'CNAS':'CMA + CNAS';c.s[field]=v}return true}}))
 const sample=reactive(new Proxy({details,commissionInfo:commission} as any,{get(t,k:string){if(k==='quantity')return sampleQuantityText(c.s.sampleAmount,c.s.unit);const map:Record<string,string>={name:'sampleName',notes:'remark',quantity:'sampleAmount',category:'testCategory',unit:'unit',projects:'projectList'};return map[k]?c.s[map[k]]:t[k]},set(t,k:string,v){if(!editing.value||busy.value)return true;if(k==='quantity'){setSampleQuantity(c.s,String(v));return true}const map:Record<string,string>={name:'sampleName',notes:'remark',quantity:'sampleAmount',category:'testCategory',unit:'unit',projects:'projectList'};if(map[k]){c.s[map[k]]=v;if(k==='projects')c.s.project=v.join('；')}else t[k]=v;return true}}))
 const paginate=(rows:any[],q:any)=>{const page=Math.max(1,q.page||1),pageSize=q.pageSize||10;return{items:rows.slice((page-1)*pageSize,page*pageSize),page,pageSize,total:rows.length}}
 let schemeRows:any[]=[];const organizationsByName=new Map<string,any>()
 const basis=(r:any)=>({id:String(r.id),controlNumber:r.controlledNo||'',qualification:[r.cma?'CMA':'',r.cnas?'CNAS':''].filter(Boolean).join('、'),code:r.code,name:r.name||'',category:r.category||'',location:[r.location?`维护地点：${r.location}`:'',(r.sites||[]).length?`授权场所：${r.sites.join('；')}`:''].filter(Boolean).join('；'),implementedDate:r.implementedDate||'',revokedDate:r.revokedDate||'',extensionDays:null,replacementCode:r.replacementCode||'',notes:r.notes||''})
 const services={
  async contracts(q:any){let rows=c.visibleClaimedContracts.map((r:any)=>({id:r.agreementNo,code:r.projectCode||r.erpProjectNo||'',name:r.projectName,customer:r.client,departmentId:r.department||r.dept||'',erpContract:r.agreementNo,erpProjectType:r.erpType,signedDate:r.registrationDate||r.startDate||'',projectName:r.projectName,projectAddress:r.projectAddr||'',constructionCompany:'',registrationStatus:r.registrationStatus||''}));if(q.ownDepartment)rows=rows.filter((r:any)=>r.departmentId===c.session.dataScope.department);if(q.keyword)rows=rows.filter((r:any)=>String(q.searchField&&q.searchField!=='all'?r[q.searchField]:Object.values(r).join(' ')).toLowerCase().includes(q.keyword.toLowerCase()));if(q.from)rows=rows.filter((r:any)=>r.signedDate>=q.from);if(q.to)rows=rows.filter((r:any)=>r.signedDate.slice(0,10)<=q.to);return paginate(rows,q)},
  async organizations(q:any,signal?:AbortSignal){const r=await fetchCustomerPage(q.keyword||'',q.page||1,q.pageSize||10,false,signal);r.rows.forEach((x:any)=>organizationsByName.set(x.name,x));return{items:r.rows.map((x:any)=>({id:String(x.code),name:x.name})),total:r.total,page:r.page,pageSize:r.size}},
  async manufacturers(){return{items:[],types:[],total:0,page:1,pageSize:10}},
  async commissions(q:any){return paginate(c.entrustOptions.filter((r:any)=>!q.keyword||JSON.stringify(r).includes(q.keyword)).map((r:any)=>({id:r.entrustNo,code:r.entrustNo,name:r.projectName,customer:r.client,status:r.status||''})),q)},
  async testPlans(q:any){const groups=await fetchSchemes(q.keyword||'');schemeRows=groups.flatMap((g:any)=>g.schemes);const rows=q.keyword?schemeRows.map(r=>({id:String(r.id||r.code),name:r.name,kind:'plan',code:r.numberCode||r.code,groupName:r.dept||''})):q.parentId?(groups.find((g:any)=>g.dept===q.parentId)?.schemes||[]).map((r:any)=>({id:String(r.id||r.code),name:r.name,kind:'plan',code:r.numberCode||r.code,groupName:q.parentId})):groups.map((g:any)=>({id:g.dept,name:g.dept,kind:'group',code:'',groupName:g.dept}));return paginate(rows,q)},
  async testBases(q:any){
   if(q.ids){const rows=[];for(const id of q.ids){const found=c.stdOptions.find((r:any)=>String(r.id)===id)||(await searchStdLib('',c.s.testDept,{ids:[Number(id)],date:c.s.sendDate||undefined})).find(r=>String(r.id)===id);if(found)rows.push(found)}c.mergeStandardOptions(rows);return{...paginate(rows.map(basis),q),departmentCategories:[],qualifications:['CMA','CNAS']}}
   const page=await searchStdLibPage(q.code||q.name||q.controlNumber||'',q.ownDepartment?c.s.testDept:'',{date:c.s.sendDate||undefined,page:q.page||1,size:q.pageSize||10,scopeFilter:q.qualification==='CMA'?'cma':q.qualification==='CNAS'?'cnas':'all'});
   c.mergeStandardOptions(page.rows);return{items:page.rows.map(basis),total:page.total,page:page.page,pageSize:page.size,departmentCategories:[],qualifications:['CMA','CNAS']}
  },
  async resolveTestBases(plan:string,ids:string[],english:boolean,_signal:any,separators:string[]){const r=await services.testBases({planId:plan,ids,pageSize:50});if(r.total!==ids.length)throw Error('部分标准不可用，请重新选择');if(new Set(ids).size!==ids.length)throw Error('同一标准记录不能重复选择');return{ids,text:r.items.map((row:any)=>row.code).join('；'),englishBookMarks:english,separators}},
 }
 const ui=reactive({manualParties:computed(()=>(isCommission.value?(c.selectedContractType||c.f.erpType):(c.sampleContractType||c.sampleEntrust.erpType))==='不回传外部ERP合同'),departments:computed(()=>c.handleDepts.map((r:any)=>({id:r.value||r.code||r.name,name:r.fullName||r.label||r.displayName||r.name}))),contractPartyLocked:computed(()=>isCommission.value?c.contractPartyALocked:c.sampleContractPartyALocked),sampleImageBlocked:computed(()=>c.sampleImageBlocked),testCategories:computed(()=>c.SAMPLE_OPTS.testCategory||[]),requestClose:()=>c.requestClose(),organizationPicked:(key:string,name:string)=>{if(key==='customer'){const rows=name.split(/[、；;\n]+/).map(n=>organizationsByName.get(n)).filter(Boolean);if(rows.length===1)(isCommission.value?c.onPickClient:c.onPickSampleClient)(rows)}}})
 provide('platform-registration-subprojects',subprojects);provide('platform-registration-services',services);provide('platform-registration-context',ui)
 provide('platform-production-dates', c)
 const backendSchema=computed<FormSchema<any>>(()=>({sections:[{id:'platform-sample-fields',title:'样品及检测要求',fields:[
  ...([{key:'deadline',label:'检测期限',control:'text'},{key:'sampleArrivalDate',label:'样品到达日期',control:'date'},{key:'sampleGrade',label:'样品等级',control:'text'},{key:'sealChecker',label:'检查封样人员',control:'text'}] as const).map(x=>({id:'platform-'+x.key,label:x.label,control:x.control,binding:{get:()=>c.s[x.key]||'',set:(_:any,v:string)=>{if(editing.value&&!busy.value)c.s[x.key]=v}}})),
  {id:'platform-seal',label:'盖章要求',control:['NCSA','NCAS'].includes(c.s.centerPrefix)?'select':'text',disabled:!editing.value||busy.value||!['NCSA','NCAS'].includes(c.s.centerPrefix),options:[{value:'CNAS',label:'不加 CMA（保留 CNAS）'},{value:'CMA + CNAS',label:'加 CMA + CNAS'}],binding:{get:()=>c.s.seal||'',set:(_:any,v:string)=>{if(editing.value&&!busy.value&&['NCSA','NCAS'].includes(c.s.centerPrefix)&&['CNAS','CMA + CNAS'].includes(v))c.s.seal=v}}},
  {id:'platform-technical',label:'检测技术子项目',control:'custom',slot:'technical'},
 ]},{id:'platform-required-fields',title:'报告及现场检测设置',fields:[
  ...([{key:'isOnsiteTesting',label:'是否现场检测',control:'checkbox'},{key:'onsiteTestLocation',label:'现场检测地点',control:'text'},{key:'homepageRemark',label:'报告首页备注',control:'textarea'},{key:'manualCapabilityReason',label:'库外使用说明（选填）',control:'textarea'},{key:'manualTestLocation',label:'库外检测地点',control:'text'},{key:'subSuffix',label:'分项报告后缀',control:'text'}] as const).map(x=>({id:'platform-'+x.key,label:x.label,control:x.control,binding:{get:()=>c.s[x.key],set:(_:any,v:any)=>{c.s[x.key]=v;if(x.key==='isOnsiteTesting')void c.onOnsiteTestingChange();else if(x.key==='onsiteTestLocation')c.syncParameterLocations();else if(x.key==='manualTestLocation')c.onManualCapabilityChange()}}})),
  {id:'platform-report-category',label:'报告类别',control:'select',disabled:c.schemeLocked,options:['普通','补充','英文','分项'].map(value=>({value,label:value})),binding:{get:()=>c.s.reportCategory,set:(_:any,v:any)=>{c.s.reportCategory=v}}},
  {id:'platform-base-report',label:'原样品 / 报告',control:'custom',slot:'baseReport'},
  {id:'platform-manual-items',label:'库外项目',control:'textarea',binding:{get:()=>c.s.manualCapabilityItems.join('；'),set:(_:any,v:string)=>{c.s.manualCapabilityItems=c.splitBasisValues(v);c.onManualCapabilityChange()}}},
  {id:'platform-capability',label:'资质参数',control:'custom',slot:'capability'},
  {id:'platform-layout',label:'首页版式',control:'select',options:(['产品报告','抽样报告'].includes(c.s.reportType)?['Standard','Extended']:['Standard']).map(value=>({value,label:value==='Standard'?'标准版':'扩展版'})),binding:{get:()=>c.s.reportTemplateVariant,set:(_:any,v:string)=>{c.s.reportTemplateVariant=v}}},
 ]}]}))
 const reportConfig=computed(()=>{const formats=[...new Set(c.centers.flatMap((r:any)=>r.types))].map(id=>({id,label:id})),titles=c.centers.map((r:any)=>({id:r.prefix,label:r.name})),languages=[{id:'CN',label:'中文'},{id:'EN',label:'英文'}],layouts=[{id:'Standard',label:'标准版'},{id:'Extended',label:'扩展版'}];return{version:'platform',options:{formatId:formats,titleId:titles,languageId:languages,layoutId:layouts},defaults:{...settings},combinations:c.centers.flatMap((t:any)=>t.types.flatMap((f:string)=>(f.includes('校准')?['CN']:c.s.reportCategory==='英文'?['EN']:['CN','EN']).flatMap((l:string)=>(['产品报告','抽样报告'].includes(f)?['Standard','Extended']:['Standard']).map(a=>({formatId:f,titleId:t.prefix,languageId:l,layoutId:a})))))} })
 async function save(event:Event){if(!editing.value||busy.value||loading.value||c.sampleFormError)return;error.value='';const close=(event as SubmitEvent).submitter?.getAttribute('value')==='return';try{const saved=isCommission.value?await c.saveEntrust():await c.saveSampleDraft();if(saved===true&&close&&!c.hasUnsavedChanges)c.requestClose()}catch(e){error.value=platformError(e)}}
 const capabilityLabel=(r:any)=>`#${r.id} ${r.standardCode} · ${r.objectName}/${r.itemName} · ${r.site}`
 const capabilityRows=computed(()=>[...new Map([...c.s.capabilitySnapshots,...c.capabilityOptions].map((r:any)=>[r.id,r])).values()] as any[])
 const capabilityLabels=computed(()=>capabilityRows.value.map(capabilityLabel)),capabilityText=computed(()=>capabilityRows.value.filter((r:any)=>c.s.capabilityEntryIds.includes(r.id)).map(capabilityLabel).join('；'))
 function chooseCapabilities(value:string){const labels=value.split('；').map(x=>x.trim()).filter(Boolean);const selected=labels.map(label=>capabilityRows.value.find((r:any)=>capabilityLabel(r)===label));if(selected.some(r=>!r)){error.value=platformError(Error('请从资质参数选项中选择'));return}c.confirmCapabilitySelection(selected.map(r=>r.id))}
 const state=reactive({isCommission,editing,busy,loading,loadError:computed(()=>c.sampleFormError?platformError(Error(c.sampleFormError)):''),error,title:computed(()=>c.dialogTitle),returnTo:c.route.path,context:{root:c.route.path,title:isCommission.value?'委托登记':'样品登记'},kind:computed(()=>isCommission.value?'commissions':'samples'),id:computed(()=>c.effectiveReportNo||c.activeEntrustId||''),creating:computed(()=>isCommission.value?!c.isEntrustEdit:!c.effectiveReportNo),
 form:computed(()=>isCommission.value?commission:sample),commissionRecord:computed(()=>({...commission,code:source().entrustNo,owner:source().handler})),sampleRecord:computed(()=>({code:c.sampleAutoNo,reportCode:c.sampleReportNo})),
 load:()=>c.retryLoad(),showBusyIndicator:busy,submitCommission:save,submitSample:save,sampleFormElement:ref(),clearSampleFieldError:()=>{},testPlanError:computed(()=>c.sampleConfigErrors?.join('；')||''),testPlanOpen,testBasisOpen,testBasisPending,sampleFormTabs,sampleTab,sampleUploadPending,fixedCommission:computed(()=>!!c.presetEntrustNo),registrationCanLink:()=>editing.value,currentActor:{name:c.session.userName},sampleFieldErrors:{},sampleOptions:{choices:{testingDepartment:computed(()=>c.sampleDepartmentOptions),nameplate:c.SAMPLE_OPTS.nameplate,appearance:c.SAMPLE_OPTS.appearance,taskSource:c.SAMPLE_OPTS.taskSource,disposalMethod:c.SAMPLE_OPTS.sampleHandle,reportDelivery:c.SAMPLE_OPTS.deliverWay,reportForm:c.SAMPLE_OPTS.reportForm,onsiteArrangement:c.SAMPLE_OPTS.fieldAgreement,paymentStatus:c.SAMPLE_OPTS.payStatus},subprojectOptions:subprojects.options},projectChoices:computed(()=>c.s.projectList),reportConfig,reportConfigLoading:false,reportConfigError:'',loadReportConfig:()=>{},reviewing:false,reviewActions:[],reviewRecord:undefined,reviewSaved:()=>{},success:'',successToast:ref(),errorToast:ref(),validationError:false,pickerOpen,candidateCommissions:computed(()=>c.entrustOptions.map((r:any)=>r.entrustNo)),confirmLeave:false,leave:()=>{},backendSchema,controller:c,capabilityLabels,capabilityText,chooseCapabilities,
 chooseOrder:(id:string)=>{c.sampleEntrustNo=id;c.onSampleEntrustChange(id);pickerOpen.value=false},
 chooseTestPlan:async(node:any)=>{if(!node){if(!c.schemeLocked){c.s.schemeName='';c.s.schemeCode=''}return;}if(c.schemeLocked)return;const source=schemeRows.find(r=>String(r.id||r.code)===node.id);if(!source)throw Error('方案已变化，请重选');await c.pickScheme(source);testPlanOpen.value=false},
 chooseTestBasis:async(selection:any)=>{await c.onBasisIdsChange(selection.ids);testBasisOpen.value=false},clearTestBasis:()=>c.onBasesChange([]),
 })
 Object.assign(state,{technicalLabels,technicalText,technicalLoading,technicalError,loadTechnical,chooseTechnical})
 watch(()=>c.sampleImageError,value=>{if(value)error.value=platformError(Error(value))})
 watch(error,()=>{if(error.value)state.errorToast?.show?.();else state.errorToast?.hide?.()},{flush:'post'})
 return state as any
}
