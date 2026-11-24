import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {shallowMount,flushPromises} from '@vue/test-utils'
import Page from '@/pages/SampleOutboundPage.vue'
import Dialog from './OutboundPickupDialog.vue'
import {fetchListPage} from '../lists/serverPage'
import {fetchSamples,submitSamplePickup} from '@/services/pipeline'
vi.mock('../lists/serverPage',async()=>({...await vi.importActual('../lists/serverPage'),fetchListPage:vi.fn()}))
const state=vi.hoisted(()=>({allowed:true}))
vi.mock('vue-router',()=>({useRoute:()=>({meta:{}})}))
vi.mock('@/services/pipeline',()=>({PIPELINE_AVAILABLE:true,fetchSamples:vi.fn(),submitSamplePickup:vi.fn(),submitSampleReturnStock:vi.fn()}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({account:'qa',userName:'测试管理员',dataScope:{department:'QA'},canAction:()=>state.allowed,canOverrideWorkflowDate:false})}))
vi.mock('@/components/PipelineWizard.vue',()=>({default:{template:'<div/>'}}))
const row:any={reportNo:'R1',sampleNo:'S1',sampleStatus:'已入库',status:'待样品领取',dataStatus:'样品出库领取中',workflowDates:{sampleInboundAt:'2026-10-22',sampleAvailableAt:'2026-10-27',sampleReturnedAt:'2026-10-27'}}
let w:any
beforeEach(()=>{vi.clearAllMocks();state.allowed=true;vi.mocked(fetchListPage).mockResolvedValue({rows:[row],total:1,page:1,pageSize:10});vi.mocked(submitSamplePickup).mockResolvedValue({} as any)})
afterEach(()=>w?.unmount())
async function setup(){w=shallowMount(Page);await flushPromises();const c=w.vm.$.setupState;c.openForm(row);await flushPromises();return c}
it('opens presentation without writing, keeps date boundary and sync, forwards sign fields',async()=>{
 const c=await setup(),d=w.findComponent(Dialog);expect(submitSamplePickup).not.toHaveBeenCalled();expect(d.props('previousDate')).toBe('2026-10-22')
 c.form.outTime='2026-10-21';c.form.receiverName='测试领样人';await flushPromises();expect(d.props('canSign')).toBe(false)
 c.form.outTime='2026-10-22';await flushPromises();expect(c.form.pickupTime).toBe('2026-10-22');expect(d.props('canSign')).toBe(true)
 d.vm.$emit('submit','sign');await flushPromises();expect(submitSamplePickup).toHaveBeenCalledWith('R1',expect.objectContaining({action:'sign',managerId:'qa',managerName:'测试管理员',outTime:'2026-10-22',pickupTime:'2026-10-22',receiverName:'测试领样人'}));expect(c.formOpen).toBe(false)
})
it('keeps return reason requirement and closes without writing',async()=>{
 const c=await setup(),d=w.findComponent(Dialog);d.vm.$emit('submit','return');await flushPromises();expect(submitSamplePickup).not.toHaveBeenCalled()
 c.form.returnNote='委托信息需更正';d.vm.$emit('submit','return');await flushPromises();expect(submitSamplePickup).toHaveBeenCalledWith('R1',expect.objectContaining({action:'return',returnNote:'委托信息需更正'}))
 vi.mocked(submitSamplePickup).mockClear();c.openForm(row);d.vm.$emit('close');await flushPromises();expect(c.formOpen).toBe(false);expect(submitSamplePickup).not.toHaveBeenCalled()
})
it('passes existing action permissions to the presentation',async()=>{
 state.allowed=false;await setup();const d=w.findComponent(Dialog);expect(d.props('allowSign')).toBe(false);expect(d.props('allowReturn')).toBe(false)
})
