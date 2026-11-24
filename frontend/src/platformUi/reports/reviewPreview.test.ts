import {afterEach,describe,it,expect,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {reactive,defineComponent,h,provide} from 'vue'
import Preview from './ReviewReportPreview.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
afterEach(()=>vi.unstubAllGlobals())
describe('real report preview download',()=>{
 it('provides actual preview bytes to the supplied download button',async()=>{
  const blob=new Blob(['%PDF-real'],{type:'application/pdf'})
  vi.stubGlobal('fetch',vi.fn(async()=>({blob:async()=>blob})))
  const c=reactive({documentPdfUrl:'blob:report-1',decisionPreviewLoading:false,session:{canAction:()=>true}})
  const wrapper=mount(defineComponent({setup(){provide('platform-review-controller',c);return()=>h(Preview,{active:true,detail:{sample:{reportCode:'R1'},reportStatus:'ready'} as any})}}),{global:{stubs:{DataEntryPreview:true}}})
  await flushPromises()
  expect(wrapper.findComponent(DataEntryPreview).props('blob')).toBe(blob)
  expect(wrapper.findComponent(DataEntryPreview).props('name')).toBe('R1-报告.pdf')
  c.documentPdfUrl='';await flushPromises();expect(wrapper.findComponent(DataEntryPreview).props('blob')).toBeUndefined()
  wrapper.unmount()
 })
 it('hides downloading when the current account lacks download permission',async()=>{
  const wrapper=mount(Preview,{props:{active:true,detail:{sample:{reportCode:'R1'}} as any},global:{provide:{'platform-review-controller':{documentPdfUrl:'',session:{canAction:()=>false}}},stubs:{DataEntryPreview:true}}})
  expect(wrapper.findComponent(DataEntryPreview).props('hideDownload')).toBe(true);wrapper.unmount()
 })
 it('signing page shows unsigned original with preview/download only',()=>{
  const wrapper=mount(Preview,{props:{active:true,detail:{sample:{reportCode:'R1'}} as any},global:{provide:{'platform-review-controller':{pageKey:'print',documentPdfUrl:'',session:{canAction:()=>true}}},stubs:{DataEntryPreview:true}}})
  const preview=wrapper.findComponent(DataEntryPreview)
  expect(preview.props('hidePrint')).toBe(true)
  expect(preview.props('title')).toBe('报告原件（未签字、未盖章）')
  expect(preview.props('name')).toBe('R1-未签章原件.pdf')
  wrapper.unmount()
 })

})
