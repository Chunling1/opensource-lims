import {it,expect,vi} from 'vitest'
import {reactive,nextTick} from 'vue'
import {createReportStagePresentation} from './reports/reportStagePresentation'
import {useRegistrationPresentation} from './commissions/registrationPresentation'
import {useListPresentation} from './lists/listPresentation'

it.each(['review','approval','print','archive','release'])('server %s defaults active and sends off-page status before paging',async(pageKey)=>{
 const setReportQuery=vi.fn();const c=reactive<any>({pageKey,pageName:pageKey,route:{},session:{canAction:()=>true},workRows:[],serverPaging:true,reportPageState:{total:0},setReportQuery,undoReport:vi.fn()});
 const m=createReportStagePresentation(c);expect(setReportQuery.mock.calls[0][0].rowProjection).toBe('active');
 expect(m.reportCheckStates).toContain('待处理');
 const status=({review:'报告批准中',approval:'报告签发中',print:'报告发放完成',archive:'报告批准中',release:'报告已归档，发放中'} as any)[pageKey];
 expect(m.reportCheckStates).toContain(status);m.patch({page:2});m.draft.status=status;m.draft.contains='needle';m.search();await nextTick();
 expect(setReportQuery.mock.calls.at(-1)?.[0]).toMatchObject({status,rowProjection:'',page:1,contains:'needle'});
 m.draft.status='';m.search();await nextTick();expect(setReportQuery.mock.calls.at(-1)?.[0].rowProjection).toBe('');
});
it.each(['inbound','outbound'])('%s sends pending/all and an off-page state to server',async(kind)=>{
 const setListQuery=vi.fn();const m=useListPresentation(reactive<any>({serverPaging:true,listPage:{total:0},setListQuery,rows:[],session:{canAction:()=>true}}),kind);
 expect(setListQuery.mock.calls[0][0].rowProjection).toBe('active');expect(m.states).toContain('待处理');
 const status=kind==='inbound'?'样品出库领取中':'样品出库领取完成';expect(m.states).toContain(status);m.patch({page:2});m.draft.status=status;m.draft.contains='needle';m.search();await nextTick();
 expect(setListQuery.mock.calls.at(-1)?.[0]).toMatchObject({status,contains:'needle',page:1,rowProjection:''});
 m.draft.status='';m.search();await nextTick();expect(setListQuery.mock.calls.at(-1)?.[0].rowProjection).toBe('');
});
it.each(['review','registration'])('%s sample filter sends active then all without touching permissions',async(mode)=>{
 const setRegistrationQuery=vi.fn();const m=useRegistrationPresentation(reactive<any>({mode,samplesOnly:mode==='registration',serverPaging:true,commissionPage:{total:0},registrationSamplePage:{total:0},registrationPageSamples:[],backendEntrust:[],setRegistrationQuery,session:{can:()=>true},onWorkbenchSelectionChange:vi.fn()}));
 expect(setRegistrationQuery.mock.calls.find(x=>x[0]==='s')?.[1].rowProjection).toBe('active');
 const status='报告已盖章，归档中，未发放';const options=mode==='review'?m.reviewDataStatusOptions:m.registrationDataStatusOptions;expect(options.map((x:any)=>x.value)).toContain(status);m.patch({sPage:2});m.search('s',{dataStatus:status,contains:'needle'});await nextTick();
 expect(setRegistrationQuery.mock.calls.filter(x=>x[0]==='s').at(-1)?.[1]).toMatchObject({dataStatus:status,contains:'needle',page:1,rowProjection:''});
 m.search('s',{dataStatus:''});await nextTick();expect(setRegistrationQuery.mock.calls.filter(x=>x[0]==='s').at(-1)?.[1].rowProjection).toBe('');
});
it('query page keeps all statuses by default',()=>{
 const setReportQuery=vi.fn();createReportStagePresentation(reactive<any>({pageKey:'query',route:{},workRows:[],serverPaging:true,reportPageState:{total:0},setReportQuery,session:{canAction:()=>true},undoReport:vi.fn()}));
 expect(setReportQuery.mock.calls[0][0].rowProjection||'').toBe('');
});

it('preserves query page historical status options',()=>{
 const m=createReportStagePresentation(reactive<any>({pageKey:'query',route:{},workRows:[{reportNo:'OLD',dataStatus:'历史状态'}],serverPaging:true,reportPageState:{total:1},setReportQuery:vi.fn(),session:{canAction:()=>true},undoReport:vi.fn()}));
 expect(m.reportCheckStates).toContain('历史状态');expect(m.draft.status).toBe('');
});

it('retains legal historical states in fixed lifecycle dropdowns',async()=>{
 const {handlingStates}=await import('./handlingStatus');
 for(const view of ['register','contract_review','archive']){
  expect(handlingStates(view)).toContain('已归档');expect(handlingStates(view)).toContain('样品入库中（历史数据）');
  expect(handlingStates(view)).not.toContain('样品单已作废');
 }
});
