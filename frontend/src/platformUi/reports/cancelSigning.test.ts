import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Panel from '@/components/EsignFlowPanel.vue'
import { cancelEsignFlow, fetchReportEsignFlow, dispatchEsignFlow } from '@/services/esign'
import { ElMessage, ElMessageBox } from 'element-plus'

vi.mock('@/services/esign', () => ({cancelEsignFlow:vi.fn(), fetchReportEsignFlow:vi.fn(),startOrganizationSeal:vi.fn(),dispatchEsignFlow:vi.fn(),downloadEsignSignedPdf:vi.fn(),getEsignPositioningUrl:vi.fn(),prepareReportEsignFlow:vi.fn()}))
vi.mock('element-plus', () => ({ElMessage:{success:vi.fn(),error:vi.fn()},ElMessageBox:{prompt:vi.fn(),confirm:vi.fn()}}))
const data = (status='signing', canCancel=true, id=12) => ({id,reportNo:'R-0036',status,canCancel,flowKind:'person_signing',organizationSeal:{included:false},signers:[{id:1,roleName:'主检',userName:'检测员',status:status==='ready'?'pending':'signed'}]})
const mountPanel = (readOnly=false) => mount(Panel,{props:{reportNo:'R-0036',readOnly},global:{stubs:{SchemaForm:{template:'<div><slot name="flow"/><slot name="actions"/></div>'},SigningFlowSteps:{props:['steps'],template:'<div>{{steps}}</div>'},LoadState:true,FeedbackNotice:{props:['message'],template:'<p>{{message}}</p>'},ElButton:{props:['loading','disabled'],template:'<button :disabled="loading || disabled"><slot/></button>'}}}})
const cancelButton = (v:ReturnType<typeof mountPanel>) => v.findAll('button').find(b=>b.text()==='撤销签署流程')!
beforeEach(()=>{vi.resetAllMocks();vi.mocked(fetchReportEsignFlow).mockResolvedValue(data() as any);vi.mocked(ElMessageBox.prompt).mockResolvedValue({value:'重新签署',action:'confirm'})})

describe('administrator signing cancellation',()=>{
  it('stays on the report with a new all-pending task and no automatic dispatch',async()=>{
    const v=mountPanel();await flushPromises()
    vi.mocked(cancelEsignFlow).mockResolvedValue(data('ready',false,13) as any)
    vi.mocked(fetchReportEsignFlow).mockResolvedValue(data('ready',false,13) as any)
    await cancelButton(v).trigger('click');await flushPromises()
    expect(cancelEsignFlow).toHaveBeenCalledExactlyOnceWith(12,'重新签署')
    expect(v.text()).toContain('待签');expect(v.text()).not.toContain('已签');expect(v.text()).not.toContain('尚未建立')
    expect(v.text()).toContain('发起人员电子签署');expect(dispatchEsignFlow).not.toHaveBeenCalled();v.unmount()
  })
  it.each(['ready','signing','completed','cancelled','cancelling'])('does not show no-task notice for %s',async status=>{
    vi.mocked(fetchReportEsignFlow).mockResolvedValue(data(status) as any)
    const v=mountPanel();await flushPromises();expect(v.text()).not.toContain('尚未建立电子签发任务');v.unmount()
  })
  it('shows a true empty state, and distinguishes a load failure',async()=>{
    vi.mocked(fetchReportEsignFlow).mockResolvedValue(null)
    const v=mountPanel();await flushPromises();expect(v.text()).toContain('尚未建立');v.unmount()
    vi.mocked(fetchReportEsignFlow).mockRejectedValue(new Error('服务暂不可用'))
    const e=mountPanel();await flushPromises();expect(e.text()).toContain('服务暂不可用');expect(e.text()).not.toContain('尚未建立');e.unmount()
  })
  it('hides cancellation without server permission and in readonly mode',async()=>{
    for(const readOnly of [false,true]){
      vi.mocked(fetchReportEsignFlow).mockResolvedValue(data('signing',readOnly) as any)
      const v=mountPanel(readOnly);await flushPromises();expect(cancelButton(v)).toBeUndefined();v.unmount()
    }
  })
  it('does not submit when the administrator closes the dialog',async()=>{
    const v=mountPanel();await flushPromises();vi.mocked(ElMessageBox.prompt).mockRejectedValue('cancel')
    await cancelButton(v).trigger('click');await flushPromises();expect(cancelEsignFlow).not.toHaveBeenCalled();v.unmount()
  })
  it('keeps signatures and exposes retry when provider outcome is uncertain',async()=>{
    const v=mountPanel();await flushPromises()
    vi.mocked(cancelEsignFlow).mockRejectedValue(new Error('尚未确认旧流程停止'))
    vi.mocked(fetchReportEsignFlow).mockResolvedValue(data('cancelling') as any)
    await cancelButton(v).trigger('click');await flushPromises()
    expect(v.text()).toContain('已签');expect(v.text()).toContain('继续核实撤销');expect(ElMessage.success).not.toHaveBeenCalled();v.unmount()
  })
  it('ignores duplicate clicks and a late result after switching reports',async()=>{
    let resolve!:(x:any)=>void
    const v=mountPanel();await flushPromises()
    vi.mocked(cancelEsignFlow).mockReturnValue(new Promise(r=>{resolve=r}))
    await cancelButton(v).trigger('click');await flushPromises();await cancelButton(v).trigger('click')
    await v.setProps({reportNo:'R-0037'});await flushPromises();resolve(data('ready',false,13));await flushPromises()
    expect(cancelEsignFlow).toHaveBeenCalledTimes(1);expect(ElMessage.success).not.toHaveBeenCalled();expect(v.text()).not.toContain('发起人员电子签署');v.unmount()
  })
})
