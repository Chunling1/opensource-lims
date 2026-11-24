import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Panel from '@/components/EsignFlowPanel.vue'
import { fetchReportEsignFlow, startOrganizationSeal, refreshEsignFlow } from '@/services/esign'
import { ElMessageBox } from 'element-plus'

vi.mock('@/services/esign', () => ({refreshEsignFlow:vi.fn(),fetchReportEsignFlow:vi.fn(),startOrganizationSeal:vi.fn(),dispatchEsignFlow:vi.fn(),downloadEsignSignedPdf:vi.fn(),getEsignPositioningUrl:vi.fn(),prepareReportEsignFlow:vi.fn()}))
vi.mock('element-plus',()=>({ElMessage:{success:vi.fn(),error:vi.fn(),warning:vi.fn()},ElMessageBox:{confirm:vi.fn()}}))
const flow=(canConfirmSeal=false,included=false,canDownloadSealed=false)=>({canDownloadSealed,id:12,reportNo:'R-0036',documentVersionId:54,status:'completed',flowKind:'person_signing',hasSignedFile:true,signedSha256:'a'.repeat(64),canConfirmSeal,organizationSeal:{included,status:included?'completed':'awaiting_confirmation'},signers:[{id:1,roleName:'主检',userName:'检测员',status:'signed'}]})
async function render(canConfirm=false,included=false,canDownloadSealed=false){
 vi.mocked(fetchReportEsignFlow).mockResolvedValue(flow(canConfirm,included,canDownloadSealed) as any)
 const wrapper=mount(Panel,{props:{reportNo:'R-0036',readOnly:true,allowSealConfirmation:true},global:{stubs:{SchemaForm:{template:'<div><slot name="flow"/><slot name="actions"/></div>'},SigningFlowSteps:true,LoadState:true,FeedbackNotice:{props:['message'],template:'<p>{{message}}</p>'},ElButton:{props:['loading'],template:'<button :disabled="loading"><slot/></button>'}}}})
 await flushPromises();return wrapper
}
beforeEach(()=>{vi.clearAllMocks();vi.mocked(ElMessageBox.confirm).mockResolvedValue('confirm')})
describe('seal confirmation',()=>{
 it('confirms the open unified flow using its immutable source and does not offer download or notifications',async()=>{
  const v=await render(true)
  const current={...flow(true),status:'signing',signingMode:'single_flow_confirmation_v1',sourceSha256:'b'.repeat(64),signedSha256:'',hasSignedFile:false}
  vi.mocked(fetchReportEsignFlow).mockResolvedValue(current as any)
  await v.findAll('button').find(b=>b.text()==='刷新状态')!.trigger('click');await flushPromises()
  expect(v.text()).toContain('签章确认');expect(v.text()).not.toContain('下载已签章');expect(v.text()).not.toContain('通知/重发')
  vi.mocked(startOrganizationSeal).mockResolvedValue(current as any)
  await v.findAll('button').find(b=>b.text()==='签章确认')!.trigger('click');await flushPromises()
  expect(startOrganizationSeal).toHaveBeenCalledExactlyOnceWith('R-0036',12,'b'.repeat(64))
  await v.findAll('button').find(b=>b.text()==='刷新状态')!.trigger('click');await flushPromises()
  expect(refreshEsignFlow).toHaveBeenCalledWith(12);v.unmount()
 })
 it('waits without exposing seal action or final download to unappointed users',async()=>{const v=await render();expect(v.text()).toContain('等待获授权');expect(v.findAll('button').map(b=>b.text())).not.toContain('签章确认');expect(v.text()).not.toContain('下载已签章');v.unmount()})
 it('allows appointed sealer independent of ordinary workflow edit controls',async()=>{const v=await render(true);vi.mocked(startOrganizationSeal).mockResolvedValue(flow(true) as any);await v.findAll('button').find(b=>b.text()==='签章确认')!.trigger('click');await flushPromises();expect(startOrganizationSeal).toHaveBeenCalledExactlyOnceWith('R-0036',12,'a'.repeat(64));v.unmount()})
 it('cancel never requests a seal',async()=>{vi.mocked(ElMessageBox.confirm).mockRejectedValue('cancel');const v=await render(true);await v.findAll('button').find(b=>b.text()==='签章确认')!.trigger('click');await flushPromises();expect(startOrganizationSeal).not.toHaveBeenCalled();v.unmount()})
 it.each([false,true])('keeps retired panel download absent with canDownloadSealed=%s',async(canDownloadSealed)=>{const v=await render(false,true,canDownloadSealed);expect(v.text()).not.toContain('下载已签章 PDF');expect(v.findAll('button').map(b=>b.text())).not.toContain('签章确认');v.unmount()})
 it('does not confirm a different report when switching during the dialog',async()=>{let resolve!:()=>void;vi.mocked(ElMessageBox.confirm).mockReturnValue(new Promise(r=>{resolve=()=>r('confirm')}) as any);const v=await render(true);await v.findAll('button').find(b=>b.text()==='签章确认')!.trigger('click');await v.setProps({reportNo:'R-OTHER'});resolve();await flushPromises();expect(startOrganizationSeal).not.toHaveBeenCalled();v.unmount()})
})
