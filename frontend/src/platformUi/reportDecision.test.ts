import {describe,it,expect,vi,beforeAll,afterEach} from 'vitest'
import {mount} from '@vue/test-utils'
import {defineComponent,h} from 'vue'
import ReportDecisionWorkbench from '@/components/report/ReportDecisionWorkbench.vue'

beforeAll(()=>{
 Object.defineProperty(document,'fonts',{configurable:true,value:{ready:Promise.resolve()}})
 vi.stubGlobal('requestAnimationFrame',(callback:FrameRequestCallback)=>setTimeout(()=>callback(0),0))
 vi.stubGlobal('cancelAnimationFrame',clearTimeout)
 vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
})
const wrappers:ReturnType<typeof mount>[]=[]
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount())})
const button=defineComponent({props:['disabled'],emits:['click'],setup(props,{slots,emit}){return()=>h('button',{disabled:props.disabled,onClick:()=>{if(!props.disabled)emit('click')}},slots.default?.())}})
function render(extra:Record<string,unknown>={}){
 const wrapper=mount(ReportDecisionWorkbench,{props:{nodeKey:'review',report:{reportNo:'R-1',client:'客户',project:'检测',status:'待审核'},summary:[{title:'业务信息',fields:[['样品编号','S-1']]}],checks:[{group:'标准',status:'通过',type:'success',items:[['范围','符合']]}],attachments:[{id:81,name:'记录.pdf',type:'PDF',source:'原始记录',status:'有效'}],signatures:{主检:'A',审核:'B',批准:'C'},documentPdfUrl:'blob:test',documentReady:true,opinion:'原意见',currentUser:'审核员',canAct:true,canPass:true,...extra},global:{stubs:{ElButton:button}}})
 wrappers.push(wrapper);return wrapper
}
async function confirmAll(wrapper:ReturnType<typeof mount>){for(const checkbox of wrapper.findAll('input[type=checkbox]'))await checkbox.setValue(true)}
describe('Existing report decision controls with complete template components',()=>{
 it('retains manual checklist before pass and emits the existing pass event',async()=>{
  const wrapper=render(),pass=wrapper.findAll('button').find(b=>b.text().includes('审核通过，提交批准'))!
  expect((pass.element as HTMLButtonElement).disabled).toBe(true)
  await confirmAll(wrapper);expect((pass.element as HTMLButtonElement).disabled).toBe(false)
  await pass.trigger('click');expect(wrapper.emitted('pass')).toHaveLength(1)
 })
 it('cannot override the backend canPass guard by checking all items',async()=>{
  const wrapper=render({canPass:false});await confirmAll(wrapper)
  const pass=wrapper.findAll('button').find(b=>b.text().includes('审核通过，提交批准'))!
  expect((pass.element as HTMLButtonElement).disabled).toBe(true);await pass.trigger('click');expect(wrapper.emitted('pass')).toBeUndefined()
 })
 it('blocks read-only opinion and checklist updates and removes decision actions',async()=>{
  const wrapper=render({readOnly:true})
  await wrapper.get('#decision-opinion').setValue('不可写');expect(wrapper.emitted('update:opinion')).toBeUndefined()
  expect(wrapper.findAll('input[type=checkbox]').every(input=>(input.element as HTMLInputElement).disabled)).toBe(true)
  expect(wrapper.findAll('button').some(b=>b.text().includes('审核通过，提交批准'))).toBe(false)
 })
 it('forwards editable opinions and original attachment identity to the owner',async()=>{
  const wrapper=render();await wrapper.get('#decision-opinion').setValue('需补充记录');expect(wrapper.emitted('update:opinion')?.[0]).toEqual(['需补充记录'])
  const file=wrapper.findAll('button').find(b=>b.text()==='查看附件')!;await file.trigger('click')
  expect(wrapper.emitted('open-attachment')?.[0]?.[0]).toMatchObject({id:81,source:'原始记录'})
 })
 it('keeps approval forwarding and readonly summary fields',async()=>{
  const wrapper=render({nodeKey:'approval'});expect(wrapper.text()).toContain('批准通过，提交打印')
  expect((wrapper.get('#decision-summary-0-0').element as HTMLInputElement).readOnly).toBe(true)
 })
})
