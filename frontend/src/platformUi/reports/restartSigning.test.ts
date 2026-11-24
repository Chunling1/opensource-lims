import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Panel from '@/components/EsignFlowPanel.vue'
import { dispatchEsignFlow, fetchReportEsignFlow, prepareReportEsignFlow } from '@/services/esign'
import { ElMessage } from 'element-plus'

vi.mock('@/services/esign', () => ({fetchReportEsignFlow:vi.fn(),startOrganizationSeal:vi.fn(),dispatchEsignFlow:vi.fn(),downloadEsignSignedPdf:vi.fn(),getEsignPositioningUrl:vi.fn(),prepareReportEsignFlow:vi.fn()}))
vi.mock('element-plus', () => ({ElMessage:{success:vi.fn(),error:vi.fn()},ElMessageBox:{confirm:vi.fn()}}))
const flow = (status='cancelled', id=28, reportNo='R-0036', kind='person_signing') => ({id,reportNo,status,flowKind:kind,organizationSeal:{included:false,status:'awaiting_personal_signatures'},signers:[{id:1,roleName:'主检',userName:'检测员',status:status==='cancelled'?'signed':'pending'}]})
async function render(status='cancelled', readOnly=false, kind='person_signing') {
  vi.mocked(fetchReportEsignFlow).mockResolvedValue(flow(status,28,'R-0036',kind) as any)
  const wrapper=mount(Panel,{props:{reportNo:'R-0036',readOnly},global:{stubs:{SchemaForm:{template:'<div><slot name="flow"/><slot name="actions"/></div>'},SigningFlowSteps:{props:['steps'],template:'<div>{{steps}}</div>'},LoadState:true,FeedbackNotice:{props:['message'],template:'<p>{{message}}</p>'},ElButton:{props:['loading'],template:'<button :disabled="loading"><slot/></button>'}}}})
  await flushPromises();return wrapper
}
beforeEach(() => vi.resetAllMocks())
describe('restart cancelled personal signing', () => {
  it('creates a fresh task, shows pending signers and leaves dispatch explicit', async () => {
    const v=await render();expect(v.text()).toContain('已签（历史记录）')
    vi.mocked(prepareReportEsignFlow).mockResolvedValue(flow('ready',29) as any)
    await v.findAll('button').find(b=>b.text()==='重新建立签发任务')!.trigger('click');await flushPromises()
    expect(prepareReportEsignFlow).toHaveBeenCalledExactlyOnceWith('R-0036')
    expect(v.text()).toContain('待签');expect(v.text()).toContain('发起人员电子签署');expect(v.text()).not.toContain('已签（历史记录）')
    expect(dispatchEsignFlow).not.toHaveBeenCalled();v.unmount()
  })
  it.each(['signing','completed','dispatching','rejected','expired'])('does not offer restart for %s', async status => {
    const v=await render(status);expect(v.text()).not.toContain('重新建立签发任务');v.unmount()
  })
  it('does not offer restart in readonly views or for organization sealing', async () => {
    for (const [readOnly,kind] of [[true,'person_signing'],[false,'organization_seal']] as const) {
      const v=await render('cancelled',readOnly,kind);expect(v.findAll('button').map(b=>b.text())).not.toContain('重新建立签发任务');v.unmount()
    }
  })
  it('keeps the cancelled record and exposes the server error on failure', async () => {
    const v=await render();vi.mocked(prepareReportEsignFlow).mockRejectedValue(new Error('无报告签发任务管理权限'))
    await v.findAll('button').find(b=>b.text()==='重新建立签发任务')!.trigger('click');await flushPromises()
    expect(v.text()).toContain('已签（历史记录）');expect(ElMessage.error).toHaveBeenCalledWith('无报告签发任务管理权限');expect(ElMessage.success).not.toHaveBeenCalled();v.unmount()
  })
  it('ignores a late result when switching reports', async () => {
    let resolve!:(value:any)=>void
    const v=await render();vi.mocked(prepareReportEsignFlow).mockReturnValue(new Promise(r=>{resolve=r}))
    await v.findAll('button').find(b=>b.text()==='重新建立签发任务')!.trigger('click')
    vi.mocked(fetchReportEsignFlow).mockResolvedValue(flow('signing',31,'R-0037') as any)
    await v.setProps({reportNo:'R-0037'});await flushPromises();resolve(flow('ready',29));await flushPromises()
    expect(v.text()).toContain('检测员 · 待签');expect(v.text()).not.toContain('通知/重发');expect(v.text()).not.toContain('发起人员电子签署');expect(ElMessage.success).not.toHaveBeenCalled();v.unmount()
  })
})
