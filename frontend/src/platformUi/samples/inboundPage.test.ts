import {afterEach,beforeEach,it,expect,vi} from 'vitest'
import {shallowMount,flushPromises} from '@vue/test-utils'
import Page from '@/pages/SampleInboundPage.vue'
import {ElMessageBox} from 'element-plus'
import Dialog from './InboundDateDialog.vue'
import {fetchListPage} from '../lists/serverPage'
import {fetchSamples,submitSampleInbound,undoSampleInbound} from '@/services/pipeline'
vi.mock('../lists/serverPage',async()=>({...await vi.importActual('../lists/serverPage'),fetchListPage:vi.fn()}))
const state=vi.hoisted(()=>({allowed:true}))
vi.mock('vue-router',()=>({useRoute:()=>({meta:{}})}))
vi.mock('@/services/pipeline',()=>({PIPELINE_AVAILABLE:true,fetchSamples:vi.fn(),submitSampleInbound:vi.fn(),undoSampleInbound:vi.fn(),submitSampleDispose:vi.fn(),voidSample:vi.fn(),changeResubmit:vi.fn()}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({dataScope:{department:'QA'},canAction:()=>state.allowed})}))
vi.mock('@/components/PipelineWizard.vue',()=>({default:{template:'<div/>'}}))
const row:any={reportNo:'R1',sampleNo:'S1',sampleStatus:'待入库',sendDate:'2026-10-12',entrustDate:'2026-10-10'}
let w:any
beforeEach(()=>{vi.clearAllMocks();state.allowed=true;vi.mocked(fetchListPage).mockResolvedValue({rows:[row],total:1,page:1,pageSize:10})})
afterEach(()=>w?.unmount())
it('actual inbound page opens date selection before API submission, then refreshes on completion',async()=>{
 w=shallowMount(Page);await flushPromises();const c=w.vm.$.setupState, r=c.stockList.rows.items[0]
 await c.stockList.openOperation(r,'receive');expect(w.findComponent(Dialog).props('row')).toEqual(row)
 expect(submitSampleInbound).not.toHaveBeenCalled()
 w.findComponent(Dialog).vm.$emit('completed');await flushPromises()
 expect(w.findComponent(Dialog).props('row')).toBeUndefined();expect(fetchListPage).toHaveBeenCalledTimes(2)
})
it('already stocked or unauthorized rows cannot open a receipt',async()=>{
 w=shallowMount(Page);await flushPromises();const c=w.vm.$.setupState
 c.doInbound({...row,sampleStatus:'已入库'});expect(c.inboundRow).toBeUndefined()
 state.allowed=false;c.doInbound(row);expect(c.inboundRow).toBeUndefined()
 expect(c.stockList.canOperate(c.stockList.rows.items[0],'receive')).toBe(false)
})

it('undo confirms, submits the actual report and reloads only when eligible',async()=>{
 const confirm=vi.spyOn(ElMessageBox,'confirm').mockResolvedValue(undefined as any)
 vi.mocked(undoSampleInbound).mockResolvedValue({})
 vi.mocked(fetchListPage).mockResolvedValue({rows:[{...row,status:'待样品领取',sampleStatus:'已入库',canUndoSampleInbound:true}],total:1,page:1,pageSize:10})
 w=shallowMount(Page);await flushPromises();const c=w.vm.$.setupState,r=c.stockList.rows.items[0]
 expect(c.stockList.canOperate(r,'undo')).toBe(true)
 await c.stockList.openOperation(r,'undo');await flushPromises()
 expect(confirm).toHaveBeenCalled();expect(undoSampleInbound).toHaveBeenCalledWith('R1');expect(fetchListPage).toHaveBeenCalledTimes(2)
 state.allowed=false;expect(c.stockList.canOperate(r,'undo')).toBe(false)
 confirm.mockRestore()
})
it('cancel and ineligible rows never submit undo',async()=>{
 const confirm=vi.spyOn(ElMessageBox,'confirm').mockRejectedValue('cancel')
 w=shallowMount(Page);await flushPromises();const c=w.vm.$.setupState,r=c.stockList.rows.items[0]
 expect(c.stockList.canOperate(r,'undo')).toBe(false)
 await c.stockList.openOperation(r,'undo');expect(undoSampleInbound).not.toHaveBeenCalled()
 await c.doUndoInbound({...row,canUndoSampleInbound:true});expect(undoSampleInbound).not.toHaveBeenCalled()
 confirm.mockRestore()
})
