import {describe,it,expect,vi,beforeEach} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import * as controls from '../controls'
import ReleasedDepartmentReports from '@/components/ReleasedDepartmentReports.vue'
import ReportArtifactPanel from '@/components/ReportArtifactPanel.vue'
const api=vi.hoisted(()=>({request:vi.fn(),artifactObjectUrl:vi.fn(),fetchReportArtifact:vi.fn(),fetchSignedReportArtifact:vi.fn(),signedReportObjectUrl:vi.fn()}))
vi.mock('@/services/http',()=>({request:api.request}))
vi.mock('@/services/reportAssurance',()=>api)
vi.mock('../../components/testing/DataEntryPreview.vue',()=>({default:{template:'<div />'}}))
vi.mock('../../components/common/BootstrapModal.vue',()=>({default:{props:['open'],template:'<div v-if="open"><slot /></div>'}}))
const global={components:controls}
const button=(w:any,label:string)=>w.findAll('button').find((x:any)=>x.text()===label)!
describe('report file entry boundaries',()=>{
 beforeEach(()=>{vi.clearAllMocks();api.fetchReportArtifact.mockResolvedValue({kind:'controlled',canPreview:true,canDownload:true});api.fetchSignedReportArtifact.mockResolvedValue({kind:'signed',canDownload:true});vi.stubGlobal('URL', {...URL, revokeObjectURL:vi.fn()})})
 it('opens department released report detail before downloading',async()=>{
  api.request.mockResolvedValue({rows:[{reportNo:'QA-001',sampleNo:'S1'}],total:1})
  const w=mount(ReleasedDepartmentReports,{global});await flushPromises()
  expect(w.text()).toContain('QA-001');expect(button(w,'下载')).toBeUndefined()
  await button(w,'查看').trigger('click');await flushPromises()
  expect(w.findComponent(ReportArtifactPanel).props()).toEqual({reportNo:'QA-001',view:'release'})
  expect(api.signedReportObjectUrl).not.toHaveBeenCalled();w.unmount()
 })
 it('uses bounded paging and entered report keyword',async()=>{
  api.request.mockResolvedValue({rows:[],total:41})
  const w=mount(ReleasedDepartmentReports,{global});await flushPromises()
  await button(w,'下一页').trigger('click');await flushPromises()
  expect(api.request).toHaveBeenLastCalledWith(expect.stringContaining('page=2'))
  await w.find('input').setValue('QA-001');await w.find('form').trigger('submit');await flushPromises()
  expect(api.request).toHaveBeenLastCalledWith('/api/report-assurance/released?page=1&keyword=QA-001');w.unmount()
 })
 it.each(['query','release','print'])('shows four simple actions for %s',async(view)=>{
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view},global});await flushPromises()
  expect(w.findAll('button').map(x=>x.text())).toEqual(['刷新','预览当前报告','下载原件','下载签字盖章版'])
  expect(api.fetchReportArtifact).toHaveBeenCalledWith('QA-001',view,true)
  expect(api.fetchSignedReportArtifact).toHaveBeenCalledWith('QA-001',view)
  expect(w.text()).not.toMatch(/SHA|受控版本|完成时间|高级|二维码|签署历史/);w.unmount()
 })
 it.each(['archive','review','approval','data_entry'])('has only unsigned actions in %s',async(view)=>{
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view},global});await flushPromises()
  expect(button(w,'下载签字盖章版')).toBeUndefined();expect(api.fetchSignedReportArtifact).not.toHaveBeenCalled();w.unmount()
 })
 it('signed denial leaves unsigned preview and download available',async()=>{
  api.fetchSignedReportArtifact.mockRejectedValue(new Error('需要盖章报告下载权限'))
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view:'print'},global});await flushPromises()
  expect(button(w,'下载签字盖章版').attributes('disabled')).toBeDefined()
  expect(button(w,'下载原件').attributes('disabled')).toBeUndefined()
  expect(button(w,'预览当前报告').attributes('disabled')).toBeUndefined()
  expect(w.text()).toContain('需要盖章报告下载权限');w.unmount()
 })
 it('disables signed download when metadata denies permission',async()=>{
  api.fetchSignedReportArtifact.mockResolvedValue({kind:'signed',canDownload:false})
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view:'query'},global});await flushPromises()
  expect(button(w,'下载签字盖章版').attributes('disabled')).toBeDefined()
  await button(w,'下载签字盖章版').trigger('click');await flushPromises()
  expect(api.signedReportObjectUrl).not.toHaveBeenCalled();w.unmount()
 })
 it('uses separate exact endpoints for unsigned and signed downloads',async()=>{
  api.artifactObjectUrl.mockResolvedValue('blob:unsigned');api.signedReportObjectUrl.mockResolvedValue('blob:signed')
  const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view:'query'},global});await flushPromises()
  await button(w,'预览当前报告').trigger('click');await flushPromises()
  expect(api.artifactObjectUrl).toHaveBeenLastCalledWith('QA-001','query',false,true)
  await button(w,'下载原件').trigger('click');await flushPromises()
  expect(api.artifactObjectUrl).toHaveBeenLastCalledWith('QA-001','query',true,true)
  await button(w,'下载签字盖章版').trigger('click');await flushPromises()
  expect(api.signedReportObjectUrl).toHaveBeenCalledWith('QA-001','query')
  expect(click).toHaveBeenCalledTimes(2);click.mockRestore();w.unmount()
 })
 it('ignores stale metadata after switching report',async()=>{
  let resolve:any;api.fetchSignedReportArtifact.mockImplementationOnce(()=>new Promise(r=>resolve=r))
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-old',view:'query'},global})
  await w.setProps({reportNo:'QA-new'});await flushPromises()
  resolve({canDownload:false});await flushPromises()
  expect(button(w,'下载签字盖章版').attributes('disabled')).toBeUndefined();w.unmount()
 })
 it('refreshes the persistent warning after first asynchronous preview',async()=>{
  api.fetchReportArtifact.mockResolvedValueOnce({kind:'preview',canPreview:true,canDownload:true})
    .mockResolvedValue({kind:'preview',canPreview:true,canDownload:true,preview:{notices:['检测地点超出模板容量，已截断，请核对']}})
  api.artifactObjectUrl.mockResolvedValue('blob:ready')
  const w=mount(ReportArtifactPanel,{props:{reportNo:'QA-001',view:'query'},global});await flushPromises()
  expect(w.find('.alert-warning').exists()).toBe(false)
  await button(w,'预览当前报告').trigger('click');await flushPromises()
  expect(w.find('.alert-warning').text()).toBe('检测地点超出模板容量，已截断，请核对')
  expect(w.findAll('.alert-warning').length).toBe(2)
  expect(button(w,'下载原件').attributes('disabled')).toBeUndefined();w.unmount()
 })
})
