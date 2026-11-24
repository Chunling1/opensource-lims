import { standardResolutionForm } from '../standardResolutionForm'
import { computed, nextTick, onBeforeUnmount, provide, reactive, ref, toRefs, watch } from 'vue'
import { createEntryPresentation } from '../testing/entryPresentation'
import { fetchReportDetail, fetchReportRecords } from '@/services/reports'
import { fetchCompliancePreflight, fetchReportDocumentContent, type CompliancePreflight } from '@/services/pipeline'
import { emptyReportCheckRejection, reportStages } from '../../types/reports/reportCheck'
import type { ReviewCheckResult } from '../../types/commissions/contractReview'
import { platformError } from '../apiErrors'
import { AppError, type ErrorValue } from '../../services/common/errors'
import type { FormSchema } from '../../types/forms'

// Presentation-only boundary: read the submitted snapshot, then delegate writes to
// ReportPage's existing permission/version/mutation controller. No preparation or
// PDF generation endpoint is called by this page.
export function createReviewPresentation(c: any) {
  const stage = computed<'review' | 'approval' | 'print'>(() => c.pageKey === 'print' ? 'print' : c.pageKey === 'approval' ? 'approval' : 'review')
  const loading = ref(true), loadError = ref<ErrorValue>(''), snapshot = ref<any>(), content = ref<any>()
  let active = true, loadEpoch = 0, checkEpoch = 0
  const selected = computed(() => c.selectedReport)
  const ci = computed(() => snapshot.value?.checkInput || {})
  const raw = computed(() => snapshot.value?.rawSample || {})
  const people = (key: string) => ci.value.people?.[key] ? [ci.value.people[key]] : []
  const t = computed(() => ({ conclusion:'',remark:'',unqualifiedParams:'',calibrationTime:'',reportDate:'',recordNo:'',result:'', ...ci.value,
    standards: Array.isArray(ci.value.standards) ? ci.value.standards : [ci.value.standard].filter(Boolean),
    testIntervals: ci.value.testIntervals?.length ? ci.value.testIntervals : [{start: ci.value.testStartDate || '', end: ci.value.testDate || ''}],
    equipmentIds: ci.value.equipmentIds || [], equipmentDisplay: {archiveNo: true, spec: true, maker: false, factoryNo: false, ...ci.value.equipmentDisplay},
    calibrationPlace: ci.value.calibrationPlace || raw.value.testLocation || '',
    temperature: ci.value.temperature ?? '', humidity: ci.value.humidity ?? '', pressure: ci.value.pressure ?? '',
    primaryTester1Code: ci.value.people?.primaryTester1?.code || raw.value.primaryTester1Code || raw.value.testerCode || '',
    primaryTester2Code: ci.value.people?.primaryTester2?.code || raw.value.primaryTester2Code || '',
    reviewerCode: ci.value.people?.reviewer?.code || raw.value.reviewerCode || '', approverCode: ci.value.people?.approver?.code || raw.value.approverCode || '',
    resultStatus: ({合格: '判定合格', 不合格: '判定不合格'} as Record<string,string>)[ci.value.resultStatus] || ci.value.resultStatus || '',
  }))
  const facade: any = reactive({
    selected, detail: snapshot, t, documentContent: content, session: c.session, route: c.route,
    pageName: computed(() => c.pageName), formOpen: true, formReadOnly: true,
    reportDetailView: stage, preparationLoading: loading, preparationError: '',
    currentDepartment: computed(() => selected.value?.department || ''), entryStaffDisplay: computed(() => selected.value?.owner || ''),
    isCalibrationReport: computed(() => String(raw.value.reportType || selected.value?.reportCategory || '').includes('校准')),
    isChangePage: false, isChangeRound: false, supportsExtendedTemplate: false,
    testerOptions: computed(() => [...people('primaryTester1'), ...people('primaryTester2')]),
    reviewerOptions: computed(() => people('reviewer')), approverOptions: computed(() => people('approver')),
    equipment: computed(() => ci.value.equipmentSnapshots || []),
    documentPreflight: computed(() => c.documentPreflight), previewReady: computed(() => !!c.documentPdfUrl),
    previewState: {sourceHash: '', status: '', message: ''}, uploaded: [], completedReportAttachments: [], orderedOtherAttachments: [], reportPageAttachments: [], includedOtherAttachmentIds: [],
    rawRecordAttachments: computed(():any[] => facade.uploaded.filter((f:any) => f.source === '原始记录' || /原始记录|raw/i.test(`${f.source} ${f.name}`))),
    elnStatus: {records: [], canLaunch: false}, elnFinalizedCount: 0,
    equipmentCoversIntervals: () => true, equipmentValidityReason: () => '', canRemoveAttachment: () => false,
    elnStatusText: (s:string) => ({FINALIZED:'已定稿',DRAFT:'草稿',PENDING_REVIEW:'待审核',REVIEWING:'审核中',REVIEW_REJECTED:'已退回',CANCELED:'已取消'} as Record<string,string>)[s] || s,
    loadElnStatus: async () => {},
    loadEntryRecords: (_id:string, query:any, signal:AbortSignal) => fetchReportRecords(selected.value.reportNo, stage.value, query, signal),
    nextTick, entryRows: [], statusOptions: [], refreshLinkedData: () => load(), load: () => load(),
  })
  const {record: base} = createEntryPresentation(facade)
  provide('platform-review-controller', c)
  const tab=ref('report-preview'), checkOpen=ref(false), checkStep=ref<'check' | 'reject'>('check')
  const reviewChecking=ref(false), reviewReadConfirmed=ref(false), reviewCheckResult=ref<ReviewCheckResult>()
  const preflight=ref<CompliancePreflight>(), checkError=ref<ErrorValue>(''), reviewCheckError=ref<ErrorValue>('')
  const rejection=reactive(emptyReportCheckRejection())
  const complianceForm=reactive({opinion:''})
  const complianceSchema:FormSchema<typeof complianceForm>={sections:[{id:'review-compliance-opinion',title:'合规确认意见',fields:[{id:'review-compliance-opinion-input',label:'合规确认意见',control:'textarea',required:true,width:'col-12',rows:3,maxlength:2000,binding:{get:m=>m.opinion,set:(m,v)=>{m.opinion=String(v??'')}}}]}]}
  const requiresComplianceOpinion=computed(()=>!!preflight.value?.requiresOpinion)
  const working=computed(() => !!c.mutationPending)
  const canCheck=computed(() => stage.value !== 'print' && !!snapshot.value && !loading.value && !loadError.value && !working.value && !reviewChecking.value && !c.formReadOnly && c.canActOnSelected && (c.session.canAction(c.passAction) || c.session.canAction(c.returnAction)))
  const canApproveCheck=computed(() => canCheck.value && c.session.canAction(c.passAction) && !!preflight.value && (!preflight.value.requiresOpinion || !!complianceForm.opinion.trim()) && reviewReadConfirmed.value)
  function clearReviewCheck() { checkEpoch++; preflight.value=undefined; reviewCheckResult.value=undefined; reviewReadConfirmed.value=false; reviewCheckError.value=''; reviewChecking.value=false;complianceForm.opinion='' }
  async function load() {
    const epoch=++loadEpoch, no=selected.value?.reportNo, view=stage.value
    clearReviewCheck(); loading.value=true; loadError.value=''; snapshot.value=undefined
    const current=()=>active && epoch===loadEpoch && c.formOpen && no===selected.value?.reportNo && view===stage.value
    try {
      const data=await fetchReportDetail(no,view)
      if(!current())return
      if(!data)throw new AppError('NOT_FOUND','报告资料不存在')
      snapshot.value=data; c.setDetail(data)
      // The submitted sample already contains layout/language. Optional report
      // composition metadata must not hold up the readonly form.
      void fetchReportDocumentContent(no,view).then(value=>{if(current())content.value=value}).catch(()=>{})
    } catch(e) {if(current())loadError.value=platformError(e)}
    finally {if(current())loading.value=false}
  }
  async function runReviewCheck() {
    if(!canCheck.value)return
    clearReviewCheck(); const epoch=checkEpoch, no=selected.value.reportNo, view=stage.value
    reviewChecking.value=true
    const current=()=>active && epoch===checkEpoch && checkOpen.value && c.formOpen && selected.value?.reportNo===no && stage.value===view
    try {
      const result=await fetchCompliancePreflight(no, view==='review'?'report_review':'report_approval')
      if(!current())return
      if(result.stage!==(view==='review'?'report_review':'report_approval'))throw new AppError('VERSION_CONFLICT','报告流程已变化，请刷新核对')
      preflight.value=result
      reviewCheckResult.value={id:result.preflightVersion,sampleId:no,sampleVersion:0,checkedAt:new Date().toISOString(),messages:result.issues.map(issue=>({tone:issue.hardBlocker||issue.acknowledgeable?'warning':'info',text:({block:'【阻断】',confirm:'【需确认】',notice:'【提示】'}[issue.level||(issue.hardBlocker?'block':issue.acknowledgeable?'confirm':'notice')])+(issue.message||issue.title)}))}
    } catch(e){if(current())reviewCheckError.value=platformError(e)}
    finally {if(current())reviewChecking.value=false}
  }
  const standardResolution=standardResolutionForm(preflight,()=>selected.value?.reportNo,runReviewCheck)
  async function resolveStandards(){try{await standardResolution.resolve()}catch(e){reviewCheckError.value=platformError(e)}}
  function openCheck(){if(!canCheck.value)return;checkOpen.value=true;checkStep.value='check';checkError.value='';Object.assign(rejection,emptyReportCheckRejection());void runReviewCheck()}
  async function confirmCheck(action:string){
    if(!checkOpen.value || !canCheck.value)return
    checkError.value=''
    try {
      let ok=false
      if(action==='check'){
        if(checkStep.value!=='check' || !canApproveCheck.value || !preflight.value)return
        ok=await c.submitPass({preflightVersion:preflight.value.preflightVersion,acknowledgedIssueIds:preflight.value.issues.filter(i=>i.acknowledgeable).map(i=>i.id),finalSeal:preflight.value.finalSeal,...(preflight.value.requiresOpinion?{complianceOpinion:complianceForm.opinion.trim()}:{})})
      }else if(action==='reject'){
        if(checkStep.value!=='reject'||!c.session.canAction(c.returnAction)||!rejection.reason.trim()||!['commission','testing','both'].includes(rejection.destination))return
        ok=await c.submitReturn(rejection.reason.trim(),({commission:'entrust_only',testing:'data_only',both:'entrust_and_data'} as Record<string,string>)[rejection.destination])
      }else return
      if(!active)return
      if(ok)checkOpen.value=false
      else {clearReviewCheck();checkStep.value='check';checkError.value=new AppError('BUSINESS_RULE','操作未完成，请核对当前状态后重试')}
    }catch(e){if(active){clearReviewCheck();checkError.value=platformError(e)}}
  }
  watch(()=>[c.selectedReport?.reportNo,c.pageKey],()=>{checkOpen.value=false;content.value=undefined;void load()},{immediate:true})
  watch(()=>[c.documentPreflight?.currentVersionId,c.documentPreflight?.sourceHash,c.formReadOnly,c.canActOnSelected],clearReviewCheck)
  watch(checkOpen,open=>{if(!open)clearReviewCheck()})
  onBeforeUnmount(()=>{active=false;loadEpoch++;checkEpoch++})
  return reactive({...toRefs(base),
    reportStage:stage,stageConfig:computed(()=>({...((stage.value === 'print') ? {title:'报告签发',label:'签发',role:'approver'} : reportStages[stage.value]),root:c.route.path})),stageText:(s:string)=>s.replaceAll('校核',stage.value === 'print' ? '签发' : reportStages[stage.value].label),
    reportOnly:false,reportCheckMode:true,checkMode:true,previewLayout:true,editable:false,readonlyMode:true,dirty:false,
    loading,error:loadError,tab,tabs:computed(()=>[...base.tabs,{key:'report-preview',label:'报告预览',tabId:'entry-tab-report-preview',panelId:'entry-panel-report-preview'},...(stage.value === 'print' ? [{key:'signing',label:'签发流程',tabId:'entry-tab-signing',panelId:'entry-panel-signing'}] : [])]),
    standardResolution,resolveStandards,working,checkOpen,checkStep,rejection,reviewReadConfirmed,reviewChecking,reviewCheckResult,reviewCheckError,checkError,complianceForm,complianceSchema,requiresComplianceOpinion,
    canCheck,canApproveCheck,rejectionReady:computed(()=>!!rejection.reason.trim()&&c.session.canAction(c.returnAction)),
    openCheck,runReviewCheck,clearReviewCheck,confirmCheck,rejectCheck:()=>{if(canCheck.value&&c.session.canAction(c.returnAction))checkStep.value='reject'},
    selectTab:(key:string)=>{tab.value=key},load:async()=>{await Promise.all([load(),c.loadDocumentState(),c.loadDecisionReportPreview(true)])},
    back:()=>{if(!working.value)c.formOpen=false},save:()=>{},
  }) as Record<string, any> & {reviewCheckResult: ReviewCheckResult | undefined}
}
