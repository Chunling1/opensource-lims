import {beforeEach,describe,it,expect,vi} from 'vitest'
import {nextTick,reactive} from 'vue'
vi.mock('@/services/http',()=>({request:vi.fn()}))
vi.mock('@/services/pipeline',()=>({submitSampleDispose:vi.fn(),voidSample:vi.fn(),changeResubmit:vi.fn()}))
import {request} from '@/services/http'
import {createServerPage,fetchListPage,fetchListExport} from './serverPage'
import {useListPresentation} from './listPresentation'
import {useRegistrationPresentation} from '../commissions/registrationPresentation'

describe('server owned list pages',()=>{
 beforeEach(()=>vi.clearAllMocks())
 it('requests one page only and keeps server total',async()=>{
  vi.mocked(request).mockResolvedValue({rows:[{id:21}],total:347,page:3,pageSize:10})
  expect(await fetchListPage('/api/reports/query',{page:3,pageSize:10,contains:'YP'})).toMatchObject({total:347,rows:[{id:21}]})
  expect(request).toHaveBeenCalledOnce()
  expect(JSON.parse(vi.mocked(request).mock.calls[0]![1]!.body as string)).toEqual({page:3,pageSize:10,contains:'YP',serverPage:true})
 })
 it('does not slice or locally filter a server page a second time',async()=>{
  const setListQuery=vi.fn(),c=reactive<any>({serverPaging:true,listPage:{total:347},rows:[{reportNo:'R21',sampleNo:'S21'}],session:{can:()=>true,canAction:()=>true},setListQuery})
  const m=useListPresentation(c,'flow');m.patch({page:3});await nextTick()
  expect(m.rows.items.map((r:any)=>r.id)).toEqual(['R21']);expect(m.rows.total).toBe(347)
  expect(setListQuery).toHaveBeenLastCalledWith(expect.objectContaining({page:3,presentation:'flow'}))
  Object.assign(m.draft,{contains:'not on current page'});m.search();await nextTick()
  expect(m.rows.items).toHaveLength(1)
  expect(setListQuery).toHaveBeenLastCalledWith(expect.objectContaining({page:1,contains:'not on current page'}))
 })
 it('keeps commission and sample page totals and independent queries',async()=>{
  const setRegistrationQuery=vi.fn(),c=reactive<any>({serverPaging:true,backendEntrust:[],registrationPageSamples:[{reportNo:'R21',sampleNo:'S21',entrustNo:'WT21'}],commissionPage:{total:80},registrationSamplePage:{total:347},session:{can:()=>true,canAction:()=>true},route:{},setRegistrationQuery,onWorkbenchSelectionChange:vi.fn()})
  const m=useRegistrationPresentation(c);m.changeScope('all');m.patch({sPage:3,cPage:2});await nextTick()
  expect(m.samples.items.map((r:any)=>r.id)).toEqual(['R21']);expect(m.samples.total).toBe(347);expect(m.commissions.total).toBe(80)
  expect(setRegistrationQuery).toHaveBeenCalledWith('c',expect.objectContaining({page:2}))
  expect(setRegistrationQuery).toHaveBeenCalledWith('s',expect.objectContaining({page:3}))
  m.selectCommissions(['21']);m.changeScope('current');await nextTick()
  expect(setRegistrationQuery).toHaveBeenLastCalledWith('s',expect.objectContaining({page:1,commissionIds:['21']}))
 })
 it('only reads subsequent pages when explicit export is invoked',async()=>{
  vi.mocked(request).mockResolvedValueOnce({rows:[{id:1}],total:2,page:1,pageSize:200}).mockResolvedValueOnce({rows:[{id:2}],total:2,page:2,pageSize:200})
  const state=createServerPage();state.setQuery({page:1,pageSize:10});expect(request).not.toHaveBeenCalled()
  expect(await fetchListExport('/api/reports/query',{contains:'YP'})).toEqual([{id:1},{id:2}])
  expect(request).toHaveBeenCalledTimes(2)
 })
 it('does not accept an incomplete export as success',async()=>{
  vi.mocked(request).mockResolvedValue({rows:[],total:2,page:1,pageSize:200})
  await expect(fetchListExport('/api/reports/query',{})).rejects.toThrow('列表已变化')
 })
 it('rejects totals changing or duplicate records during an export',async()=>{
  vi.mocked(request).mockResolvedValueOnce({rows:[{reportNo:'R1'}],total:2}).mockResolvedValueOnce({rows:[{reportNo:'R1'}],total:2})
  await expect(fetchListExport('/api/reports/query',{})).rejects.toThrow('列表已变化')
  vi.mocked(request).mockResolvedValueOnce({rows:[{reportNo:'R1'}],total:2}).mockResolvedValueOnce({rows:[{reportNo:'R2'}],total:3})
  await expect(fetchListExport('/api/reports/query',{})).rejects.toThrow('列表已变化')
 })

})
