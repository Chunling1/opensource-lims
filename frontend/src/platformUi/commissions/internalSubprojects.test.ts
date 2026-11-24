import {afterEach, expect, it, vi} from 'vitest'
import {flushPromises, shallowMount, type VueWrapper} from '@vue/test-utils'
import Editor from '@/components/SampleSubprojectEditor.vue'
const api = vi.hoisted(() => ({local:vi.fn().mockResolvedValue([]),erp:vi.fn().mockResolvedValue({rows:[],receivedAt:''})}))
vi.mock('@/services/businessSupplement',()=>({fetchSubprojects:api.local,fetchErpSubprojects:api.erp}))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({roleKey:'admin'})}))
let wrapper:VueWrapper
const start = async(internalContract:boolean) => {
 wrapper=shallowMount(Editor,{props:{modelValue:[],entrustNo:'TEST-WT',contractNo:'TEST-LOCAL',internalContract},global:{stubs:{ElTable:{template:'<div></div>'},ElTableColumn:{template:'<div></div>'},ElButton:{template:'<button><slot/></button>'},ElAlert:{template:'<div></div>'}},config:{warnHandler:()=>undefined}}})
 await flushPromises()
}
afterEach(()=>{wrapper?.unmount();vi.clearAllMocks()})
it('internal contract shows optional guidance without querying the Erp receiver',async()=>{
 await start(true)
 expect(api.erp).not.toHaveBeenCalled()
 expect(wrapper.text()).toContain('不回传外部ERP合同可不填写子项目')
 expect(wrapper.text()).not.toContain('外部ERP子项目读取失败')
 await wrapper.setProps({internalContract:false,contractNo:'TEST-ERP'});await flushPromises()
 expect(api.erp).toHaveBeenCalledWith('TEST-WT','TEST-ERP',undefined)
 expect(wrapper.text()).not.toContain('不回传外部ERP合同可不填写子项目')
})
it('switching to internal invalidates in-flight external results',async()=>{
 let resolve!:(x:unknown)=>void
 api.erp.mockImplementationOnce(()=>new Promise(r=>{resolve=r}))
 await start(false)
 await wrapper.setProps({internalContract:true});await flushPromises()
 resolve({rows:[{name:'旧合同子项目'}],receivedAt:'old'});await flushPromises()
 const state=(wrapper.vm as any).$.setupState
 expect(state.erpOptions).toEqual([])
 expect(state.erpReceivedAt).toBe('')
 expect(state.catalogLoading).toBe(false)
})
