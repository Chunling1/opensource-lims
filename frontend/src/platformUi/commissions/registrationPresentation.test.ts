import {describe,it,expect,vi} from 'vitest'
import {reactive,nextTick,defineComponent} from 'vue'
import {mount} from '@vue/test-utils'
import RegistrationFilters from '../../components/commissions/RegistrationFilters.vue'
import {handlingStates} from '../handlingStatus'
import {filterRegistration,registrationActions,registrationRows,useRegistrationPresentation} from './registrationPresentation'
describe('Complete commission workspace adapter',()=>{
 const source=()=>[{id:81,no:'WT-81',status:'委托完成',projectName:'项目甲',client:'客户甲',date:'2026-10-01',linkedSamples:[{sampleNo:'S-1',reportNo:'R-1',client:'客户甲'}]},{id:82,no:'WT-82',status:'委托中',projectName:'项目乙',client:'客户乙',date:'2026-10-02',linkedSamples:[]}];
 const controller=()=>reactive<any>({backendEntrust:source(),session:{can:()=>true,canAction:()=>true,account:'admin',roleKey:'admin'},route:{path:'/inspection/entrust/registration'},pageName:'委托登记',onWorkbenchSelectionChange:vi.fn(),addSampleFor:vi.fn(),openWizard:vi.fn(),viewEntrust:vi.fn(),editEntrust:vi.fn(),viewSample:vi.fn(),editSample:vi.fn(),completeSelectedEntrust:vi.fn(),uncompleteSelectedEntrust:vi.fn(),loadEntrust:vi.fn(),openQueryAttachments:vi.fn()});
 it('shows commissions while linked samples are still loading or fail',()=>{const c=controller();c.entrustPresentationLoading=false;c.entrustSamplesLoading=true;const m=useRegistrationPresentation(c);expect(m.cLoading).toBe(false);expect(m.sLoading).toBe(true);expect(m.commissions.total).toBe(2);c.entrustSamplesLoading=false;c.entrustSamplesError='样品读取失败';expect(m.cError).toBe('');expect(m.sError).toBe('样品读取失败');expect(m.commissions.total).toBe(2)});
 it('preserves real IDs and field meanings; dates and status filters do not silently ignore input',()=>{const rows=registrationRows(source());expect(rows[0]!.id).toBe('81');expect(rows[0]!.customer).toBe('客户甲');expect(filterRegistration(rows,{status:'未完成'}).map(r=>r.id)).toEqual(['82']);expect(filterRegistration(rows,{from:'2026-10-02',to:'2026-10-02'}).map(r=>r.id)).toEqual(['82']);expect(filterRegistration(rows,{searchField:'customer',contains:'甲'})).toHaveLength(1)});
 it('keeps template link creation pure and enforces the platform completed-before-sample rule',()=>{const c=controller(),m=useRegistrationPresentation(c);const link=m.addSampleLink('81');expect(m.selectedCommissions).toEqual([]);expect(c.addSampleFor).not.toHaveBeenCalled();m.navigate(link);expect(c.addSampleFor).toHaveBeenCalledWith(c.backendEntrust[0]);m.navigate(m.addSampleLink('82'));expect(c.addSampleFor).toHaveBeenCalledTimes(1)});
 it('selects a commission without expanding every row and separates all/current samples',()=>{const m=useRegistrationPresentation(controller());expect(m.sampleReady).toBe(false);m.selectCommissions(['81']);expect(m.samples.total).toBe(1);m.selectCommissions(['82']);expect(m.samples.total).toBe(0);m.changeScope('all');expect(m.samples.total).toBe(1)});
 it('keeps permission and completion-account guards on undo',()=>{const c=controller();c.session.account='someone';c.session.roleKey='user';expect(registrationActions({status:'委托完成',completionAccount:'author'},c)[0]!.disabled).toBe(true);c.session.account='author';expect(registrationActions({status:'委托完成',completionAccount:'author'},c)[0]!.disabled).toBe(false)});
 it('adapts decimal money for template formatting without changing the backend payload',()=>{const row={id:1,no:'WT1',amount:'1234.50'};expect(registrationRows([row])[0]!.receivableAmount).toBe(1234.5);expect(row.amount).toBe('1234.50');expect(registrationRows([{id:2,amount:''}])[0]!.receivableAmount).toBeNull();expect(registrationRows([{id:3,amount:'0'}])[0]!.receivableAmount).toBe(0)});
 it('passes source records to retained controllers instead of template payloads',()=>{const c=controller(),m=useRegistrationPresentation(c);m.navigate(m.link('commissions','81'));expect(c.viewEntrust).toHaveBeenCalledWith(c.backendEntrust[0]);expect(c.selectedRow.id).toBe(81)});
 it.each(['query','review'])('prints the exact sample in the %s workspace and asks for a choice when ambiguous',(mode)=>{const c=controller();c.mode=mode;c.printSample=vi.fn();c.openSelectedEntrustPrint=vi.fn();const m=useRegistrationPresentation(c);m.navigate({path:'/inspection/entrust/registration/commissions/81/print'});expect(c.printSample).toHaveBeenCalledWith(c.backendEntrust[0].linkedSamples[0]);c.backendEntrust[0].linkedSamples.push({sampleNo:'S-2',reportNo:'R-2'});m.navigate({path:'/inspection/entrust/registration/commissions/81/print'});expect(c.printSample).toHaveBeenCalledTimes(1);expect(c.openSelectedEntrustPrint).not.toHaveBeenCalled();expect(m.selectedCommissions).toEqual(['81']);expect(m.operationError.message).toContain('多个样品');m.navigate({path:'/inspection/entrust/registration/samples/R-2/print'});expect(c.printSample).toHaveBeenLastCalledWith(c.backendEntrust[0].linkedSamples[1])});
 it('review all samples includes later stages and older dates without granting re-review',()=>{const c=controller();c.mode='review';c.backendEntrust[0].date='2020-01-01';c.backendEntrust[0].linkedSamples[0].status='待打印';const m=useRegistrationPresentation(c);m.changeScope('all');m.search('s',{dataStatus:''});expect(m.samples.total).toBe(1);expect(m.workspaceActions(c.session,'samples',m.samples.items[0])[0].disabled).toBe(true);expect(m.sampleQuery.commissionFrom).toBe('')});

 it('keeps incomplete registration visible but disables reviewing it',()=>{const c=controller();c.mode='review';Object.assign(c.backendEntrust[0].linkedSamples[0],{status:'待合同评审',sampleRegState:'登记中'});const m=useRegistrationPresentation(c);m.changeScope('all');m.search('s',{dataStatus:''});expect(m.samples.total).toBe(1);expect(m.workspaceActions(c.session,'samples',m.samples.items[0])[0].disabled).toBe(true)});

 it('keeps complete status choices for ordinary accounts, empty data and refreshes',()=>{
  const c=controller();c.mode='review';c.session.account='reviewer';c.session.roleKey='user';
  c.backendEntrust=[];const m=useRegistrationPresentation(c);
  const expected=[{value:'',label:'全部状态'},...handlingStates('contract_review').map(value=>({value,label:value}))];
  expect(m.reviewDataStatusOptions).toEqual(expected);
  expect(m.reviewDataStatusOptions.slice(1).map((option:any)=>option.value)).toEqual(handlingStates('contract_review'));
  c.backendEntrust=source();c.backendEntrust[0].linkedSamples[0].dataStatus='报告盖章中';
  expect(m.reviewDataStatusOptions).toEqual(expected);
  expect(m.registrationDataStatusOptions).toContainEqual({value:'合同评审中',label:'合同评审中'});
  expect(m.inquirySampleDataStatusOptions).toContainEqual({value:'报告签发中',label:'报告签发中'});
 });
 it('retains authorized review samples without exposing their out-of-scope parent',()=>{
  const c=controller();c.mode='review';c.session.roleKey='user';c.session.account='reviewer';
  const missing={reportNo:'R-2(E)',sampleNo:'S-2',entrustNo:'WT-HIDDEN',status:'待合同评审',sampleRegState:'登记完成',dataStatus:'合同评审中',entrustDate:'2020-01-01'};
  const known={...missing,reportNo:'R-1',entrustNo:'WT-81'};
  c.reviewSamples=[known,missing];const m=useRegistrationPresentation(c);m.changeScope('all');
  expect(m.samples.items.map((r:any)=>r.id)).toEqual(['R-1','R-2(E)']);
  expect(m.commissions.items.some((r:any)=>r.code==='WT-HIDDEN')).toBe(false);
  m.search('s',{dataStatus:'合同评审中'});expect(m.samples.total).toBe(2);
  expect(m.workspaceActions(c.session,'samples',m.samples.items[1])[0].disabled).toBe(false);
  c.session.can=()=>false;
  expect(m.workspaceActions(c.session,'samples',m.samples.items[1])[0].disabled).toBe(true);
  m.selectCommissions(['81']);m.changeScope('current');expect(m.samples.items.map((r:any)=>r.id)).toEqual(['R-1']);
  m.changeScope('all');c.reviewSamples=[known];expect(m.samples.total).toBe(1);
 });
 it('uses the same status fallback for rendering and filtering without changing action state',()=>{
  const c=controller();c.mode='review';Object.assign(c.backendEntrust[0].linkedSamples[0],{status:'待打印',dataStatus:'报告盖章中'});
  const m=useRegistrationPresentation(c);m.changeScope('all');m.search('s',{dataStatus:'报告盖章中'});
  expect(m.samples.items[0]).toMatchObject({dataStatus:'报告盖章中',status:'待打印'});
  expect(m.workspaceActions(c.session,'samples',m.samples.items[0])[0].disabled).toBe(true);
  delete c.backendEntrust[0].linkedSamples[0].dataStatus;
  m.search('s',{dataStatus:'待打印'});expect(m.samples.total).toBe(1);
 });
});

describe('v195 contract review default filter',()=>{
 const setup=()=>{const c=reactive<any>({mode:'review',backendEntrust:[],reviewSamples:[
  {reportNo:'PENDING',sampleNo:'YP-1',status:'待合同评审',dataStatus:'合同评审中',sampleRegState:'登记完成'},
  {reportNo:'LAB-2026GX1-0255',sampleNo:'YP-2',status:'待发放',dataStatus:'报告已盖章，归档中，未发放',sampleRegState:'登记完成'}],
  session:{can:()=>true,canAction:()=>true},route:{},onWorkbenchSelectionChange:vi.fn()});
  const m=useRegistrationPresentation(c);m.changeScope('all');return m};
 it('starts in pending review and applies the same status constraint to all-field search',()=>{
  const m=setup();expect(m.sampleQuery.dataStatus).toBe('合同评审中');
  expect(m.samples.items.map((r:any)=>r.id)).toEqual(['PENDING']);
  m.search('s',{searchField:'all',contains:'YP'});
  expect(m.samples.items.map((r:any)=>r.id)).toEqual(['PENDING']);
  expect(m.notice).toContain('待合同评审');
  m.search('s',{dataStatus:''});
  expect(m.samples.items.map((r:any)=>r.id)).toEqual(['PENDING','LAB-2026GX1-0255']);
  expect(m.notice).toBe('');
  expect(m.workspaceActions({},'samples',m.samples.items[1]).every((a:any)=>a.disabled)).toBe(true);
 });
 it('does not restore the default after the user selects all and reloads rows',()=>{
  const m=setup();m.search('s',{dataStatus:''});m.changeScope('current');m.changeScope('all');
  expect(m.sampleQuery.dataStatus).toBe('');expect(m.samples.total).toBe(2);
 });
});

it('sends the review default on the first server request and retains all status on later search',async()=>{
 const setRegistrationQuery=vi.fn();
 const m=useRegistrationPresentation(reactive<any>({mode:'review',serverPaging:true,backendEntrust:[],registrationPageSamples:[],commissionPage:{total:0},registrationSamplePage:{total:0},session:{can:()=>true},route:{},setRegistrationQuery,onWorkbenchSelectionChange:vi.fn()}));
 expect(setRegistrationQuery.mock.calls.find(c=>c[0]==='s')?.[1]).toMatchObject({dataStatus:'',rowProjection:'active'});
 m.changeScope('all');m.search('s',{dataStatus:'',searchField:'all',contains:'LAB-2026GX1-0255'});await nextTick();
 expect(setRegistrationQuery.mock.calls.filter(c=>c[0]==='s').at(-1)?.[1]).toMatchObject({dataStatus:'',contains:'LAB-2026GX1-0255'});
});

// The actual select must keep lifecycle choices when a role has no matching row.
it.each(['admin','operator','reviewer','corrector'])('contract review select remains usable for %s',async role=>{
 const c:any=reactive({mode:'review',serverPaging:true,backendEntrust:[],registrationPageSamples:[],commissionPage:{total:0},registrationSamplePage:{total:0},setRegistrationQuery:vi.fn(),session:{account:role,roleKey:role,can:()=>true,canAction:()=>role==='admin',canCorrectBusinessData:role==='corrector'}})
 const m=useRegistrationPresentation(c)
 const w=mount(RegistrationFilters,{props:{kind:'samples',query:m.basicSampleQuery,dataStatusOptions:m.reviewDataStatusOptions},global:{stubs:{TemplateDateRange:defineComponent({setup(_, {expose}){expose({validate:()=>true});return{}},template:'<span />'})}}})
 const select=w.get('#sample-filter-data-status')
 expect(select.findAll('option').map(o=>o.element.value)).toContain('合同评审中')
 await select.setValue('合同评审中');await w.get('form').trigger('submit')
 m.search('s',w.emitted('search')![0]![0]);await nextTick()
 expect(c.setRegistrationQuery).toHaveBeenLastCalledWith('s',expect.objectContaining({dataStatus:'合同评审中',rowProjection:''}))
 w.unmount()
})
