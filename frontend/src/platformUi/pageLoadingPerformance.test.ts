import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {parse} from '@vue/compiler-sfc'
import {computed, ref} from 'vue'
import {describe,it,expect,vi,afterEach} from 'vitest'
import {profile,refreshProfile} from '../services/platform/auth'
import {setToken} from '../services/platform/http'

function deferred<T>() {let resolve!:(v:T)=>void, reject!:(e:Error)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function samplePage() {
 const source=parse(readFileSync('src/modules/pages/SampleRegisterPage.vue','utf8')).descriptor.scriptSetup!.content
 const ast=ts.createSourceFile('sample.ts',source,ts.ScriptTarget.Latest,true)
 const statements=ast.statements.filter(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='load'||ts.isVariableStatement(node)&&node.declarationList.declarations.some(d=>['sampleListParents','loadEpoch'].includes(d.name.getText(ast))))
 const js=ts.transpileModule(statements.map(n=>n.getText(ast)).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 const context={computed,available:true,sampleRegisterDemoRows:[],samples:ref<any[]>([]),entrusts:ref<any[]>([]),sampleListLoading:ref(false),sampleListError:ref(''),fetchListPage:vi.fn(),registrationSamplePage:{query:{page:1,pageSize:10},total:0},fetchEntrustList:vi.fn(),ElMessage:{error:vi.fn()}}
 const run=new Function(...Object.keys(context),js+';return {load,sampleListParents}')(...Object.values(context))
 return {...context,...run}
}
afterEach(()=>{vi.restoreAllMocks();setToken('');profile.value=undefined})
describe('sample list loading ownership',()=>{
 it('renders only the requested samples without loading all commissions',async()=>{
  const c=samplePage(),row={reportNo:'R1',sampleNo:'S1',entrustNo:'E1',entrustDate:'2026-10-01'}
  c.fetchListPage.mockResolvedValue({rows:[row],total:347})
  await c.load()
  expect(c.samples.value).toEqual([row]);expect(c.registrationSamplePage.total).toBe(347)
  expect(c.fetchEntrustList).not.toHaveBeenCalled();expect(c.sampleListLoading.value).toBe(false)
 })
 it('keeps errors visible without losing the prior page',async()=>{
  const c=samplePage();c.samples.value=[{reportNo:'R1'}];c.fetchListPage.mockRejectedValue(new Error('样品超时'))
  await c.load();expect(c.samples.value).toHaveLength(1);expect(c.sampleListLoading.value).toBe(false);expect(c.sampleListError.value).toBe('样品超时')
 })
 it('does not let an old refresh overwrite the latest list or its loading state',async()=>{
  const c=samplePage(),old=deferred<any>();c.fetchListPage.mockReturnValueOnce(old.promise).mockResolvedValueOnce({rows:[{reportNo:'NEW'}],total:20})
  const first=c.load();await c.load();old.resolve({rows:[{reportNo:'OLD'}],total:3});await first
  expect(c.samples.value).toEqual([{reportNo:'NEW'}]);expect(c.registrationSamplePage.total).toBe(20);expect(c.sampleListLoading.value).toBe(false)
 })
})
const response=(account:string)=>new Response(JSON.stringify({code:0,data:{account,permissions:[],actionPermissions:[],dataScope:{department:'',scopeType:'all'}}}),{headers:{'content-type':'application/json'}})
describe('startup profile read reuse',()=>{
 it('coalesces concurrent reads but fetches again after completion',async()=>{
  setToken('synthetic');const gate=deferred<Response>(),fetcher=vi.spyOn(globalThis,'fetch').mockReturnValueOnce(gate.promise).mockResolvedValueOnce(response('fresh'))
  const a=refreshProfile(),b=refreshProfile();expect(fetcher).toHaveBeenCalledTimes(1);gate.resolve(response('first'));expect(await a).toEqual(await b)
  await refreshProfile();expect(fetcher).toHaveBeenCalledTimes(2);expect(profile.value?.account).toBe('fresh')
 })
 it('does not reuse or apply a prior session response after changing accounts',async()=>{
  setToken('old');const old=deferred<Response>(),fetcher=vi.spyOn(globalThis,'fetch').mockReturnValueOnce(old.promise).mockResolvedValueOnce(response('new'))
  const pending=refreshProfile().catch(e=>e);setToken('new');await refreshProfile();old.resolve(response('old'));expect((await pending).code).toBe('UNAUTHORIZED')
  expect(fetcher).toHaveBeenCalledTimes(2);expect(profile.value?.account).toBe('new')
 })
 it('allows retry after a failed refresh',async()=>{
  setToken('synthetic');const fetcher=vi.spyOn(globalThis,'fetch').mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(response('retry'))
  await expect(refreshProfile()).rejects.toThrow();await refreshProfile();expect(fetcher).toHaveBeenCalledTimes(2)
 })
})
