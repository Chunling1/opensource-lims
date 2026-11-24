import {afterEach,describe,it,expect,vi} from 'vitest'
import {reactive,effectScope,ref,shallowRef,computed,nextTick} from 'vue'
import {readFileSync} from 'node:fs'
import {parse} from '@vue/compiler-sfc'
import ts from 'typescript'
import {useLiveSearch,useSearchRequest} from '@/composables/liveSearch'
import {createReportStagePresentation} from './reports/reportStagePresentation'
import RegistrationFilters from '../components/commissions/RegistrationFilters.vue'
import flatpickr from 'flatpickr'
import {Mandarin} from 'flatpickr/dist/l10n/zh'
import {mount} from '@vue/test-utils'
afterEach(()=>vi.useRealTimers())
function extracted(file:string,name:string,context:Record<string,unknown>){
 const script=parse(readFileSync('src/modules/pages/'+file,'utf8')).descriptor.scriptSetup!.content
 const ast=ts.createSourceFile('x.ts',script,ts.ScriptTarget.Latest,true)
 const node=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text===name)!
 const js=ts.transpileModule(node.getText(ast),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 return new Function(...Object.keys(context),js+`;return ${name}`)(...Object.values(context))
}
describe('P1 local list performance preserves behavior',()=>{
 it('coalesces typing at 250ms, clears immediately, and cancels on disposal',()=>{
  vi.useFakeTimers();const scope=effectScope(),q=ref(''),search=vi.fn()
  scope.run(()=>useLiveSearch(q,search));q.value='y';vi.advanceTimersByTime(100);q.value='yp'
  vi.advanceTimersByTime(249);expect(search).not.toHaveBeenCalled();vi.advanceTimersByTime(1);expect(search).toHaveBeenCalledTimes(1)
  q.value='';expect(search).toHaveBeenCalledTimes(2);q.value='x';scope.stop();vi.advanceTimersByTime(300);expect(search).toHaveBeenCalledTimes(2)
 })
 it('manual search cancels the pending filter so later page selection is retained',()=>{
  vi.useFakeTimers();const scope=effectScope()
  const c=reactive<any>({pageKey:'review',pageName:'审核',workRows:[],session:{canAction:()=>true},refreshReportList:vi.fn(),openForm:vi.fn()})
  const m=scope.run(()=>createReportStagePresentation(c))!
  m.draft.contains='yp';m.search();m.patch({page:2});vi.advanceTimersByTime(300)
  expect(m.query.contains).toBe('yp');expect(m.query.page).toBe(2);scope.stop()
 })
 it('invalidates old responses after account change and scope disposal',()=>{
  const scope=effectScope(),account=ref('A');let begin:any
  scope.run(()=>begin=useSearchRequest(()=>account.value));const a=begin();account.value='B';expect(a()).toBe(false)
  const b=begin();expect(b()).toBe(true);scope.stop();expect(b()).toBe(false)
 })
 it('scope updates replace the shallow row and invalidate dependent computed values',async()=>{
  const original={reportNo:'R1',outOfScope:false},workRows=shallowRef([original]),view=computed(()=>workRows.value[0].outOfScope)
  const replaceReportRow=extracted('ReportPage.vue','replaceReportRow',{workRows})
  const refreshReportList=vi.fn(),detailCache=ref({R1:{}})
  const update=extracted('ReportPage.vue','onScopeReviewed',{selectedReport:computed(()=>workRows.value[0]),replaceReportRow,detailCache,refreshReportList})
  expect(view.value).toBe(false);await update({outOfScope:true,note:'reason',state:'checked'})
  expect(view.value).toBe(true);expect(original.outOfScope).toBe(false);expect(workRows.value[0]).not.toBe(original);expect(detailCache.value).toEqual({});expect(refreshReportList).toHaveBeenCalledTimes(1)
 })
 it('registration explicit search runs once and prop synchronization does not trigger requests',async()=>{
  vi.useFakeTimers();(window as any).flatpickr=flatpickr;flatpickr.localize(Mandarin)
  const w=mount(RegistrationFilters,{props:{kind:'samples',query:{contains:'',searchField:'all'}}})
  await w.get('#sample-filter-contains').setValue('yp');await vi.advanceTimersByTimeAsync(300);expect(w.emitted('search')).toBeUndefined()
  await w.get('form').trigger('submit');expect(w.emitted('search')).toHaveLength(1)
  await w.setProps({query:{contains:'external',searchField:'all'}});await vi.advanceTimersByTimeAsync(300);expect(w.emitted('search')).toHaveLength(1);w.unmount()
 })
 it('coalesces only overlapping review loads and forces a fresh post-action load',async()=>{
  const script=parse(readFileSync('src/modules/pages/ContractReviewPage.vue','utf8')).descriptor.scriptSetup!.content
  const start=script.indexOf('let reviewLoad:'),end=script.indexOf('const reviewLinkedParents=',start)
  const js=ts.transpileModule(script.slice(start,end),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
  const scope=effectScope(),session={account:'A',dataScope:'all',userName:'tester'},parents:any[]=[],reports:any[]=[]
  const fetchEntrustList=vi.fn(()=>new Promise(r=>parents.push(r))),fetchReportRows=vi.fn(()=>new Promise(r=>reports.push(r)))
  const ctx={session,commissionPage:{query:{},total:0},registrationSamplePage:{query:{},total:0},fetchListPage:(url:string)=>url.includes('entrust')?fetchEntrustList():fetchReportRows(),reviewListBusy:ref(false),reviewListError:ref(''),reviewParents:shallowRef([]),allRows:shallowRef([]),fetchEntrustList,fetchReportRows,reportWorkRows:[],beginReviewLoad:scope.run(()=>useSearchRequest(()=>[session.account,session.dataScope,session.userName]))}
  const load=new Function(...Object.keys(ctx),js+';return loadReviewLists')(...Object.values(ctx))
  const first=load();expect(load()).toBe(first);expect(fetchReportRows).toHaveBeenCalledTimes(1)
  const forced=load(true);expect(fetchReportRows).toHaveBeenCalledTimes(2)
  parents[1]({rows:[{id:2}],total:1});reports[1]({rows:[{reportNo:'new'}],total:1});await forced
  parents[0]({rows:[{id:1}],total:1});reports[0]({rows:[{reportNo:'old'}],total:1});await first
  expect(ctx.allRows.value).toEqual([{reportNo:'new'}]);expect(ctx.reviewListBusy.value).toBe(false);scope.stop()
 })
})
