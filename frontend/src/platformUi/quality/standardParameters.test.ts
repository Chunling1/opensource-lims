import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import {defineComponent} from 'vue'
import Manager from '@/components/StandardParameterManager.vue'
import {loadStandardParameters,searchParameterStandards,saveStandardParameter,type ParameterRow} from '@/services/standardParameters'
vi.mock('@/services/standardParameters',()=>({loadStandardParameters:vi.fn(),searchParameterStandards:vi.fn(),saveStandardParameter:vi.fn()}))
const grants=vi.hoisted(()=>new Set(['quality.standard.create','quality.standard.update','quality.standard.authorize']))
vi.mock('@/stores/session',()=>({useSessionStore:()=>({canAction:(action:string)=>grants.has(action)})}))
const row:ParameterRow={id:7,itemName:'气密性能',objectName:'外窗',capabilityType:'检测',site:'示例站点B',address:'示例站点B完整地址',methodClause:'4.1',restriction:'',departments:['检测部'],active:true,accreditation:'CMA',internal:false,sourceFile:'授权原文.pdf',sourcePage:3,sourceRow:4,certificateNo:'SOURCE',version:'original',standardCode:'GB-OLD',superseded:false}
const page={rows:[row],total:21,departments:['检测部'],sharedSource:false}
const wrappers:ReturnType<typeof mount>[]=[]
function setup(){const w=mount(Manager,{props:{modelValue:true,standard:{id:1,code:'GB-ONE',name:'当前标准'}},global:{stubs:{teleport:true,ElDialog:defineComponent({props:['modelValue'],template:'<div v-if="modelValue"><slot/><slot name="footer"/></div>'})}}});wrappers.push(w);return w}
function button(w:ReturnType<typeof mount>,text:string){return w.findAll('button').find(b=>b.text()===text)!}
beforeEach(()=>{vi.useFakeTimers();grants.clear();['create','update','authorize'].forEach(x=>grants.add('quality.standard.'+x));vi.mocked(loadStandardParameters).mockResolvedValue(page);vi.mocked(searchParameterStandards).mockResolvedValue({rows:[{id:2,code:'GB-OLD',name:'旧标准'}],total:1});vi.mocked(saveStandardParameter).mockResolvedValue(row)})
afterEach(async()=>{await vi.runOnlyPendingTimersAsync();wrappers.splice(0).forEach(w=>w.unmount());vi.clearAllTimers();vi.useRealTimers();vi.resetAllMocks()})
it('edits old parameters with version and reason without sending qualification/source fields',async()=>{
 const w=setup();await flushPromises();await button(w,'修改').trigger('click')
 expect(w.get('#parameter-type').attributes('disabled')).toBeDefined()
 await w.get('#parameter-site').setValue('示例站点I');await w.get('#parameter-address').setValue('示例站点I完整地址');await w.get('#parameter-reason').setValue('地点修订')
 await w.get('form').trigger('submit');await flushPromises()
 expect(saveStandardParameter).toHaveBeenCalledWith(1,expect.objectContaining({site:'示例站点I',address:'示例站点I完整地址',version:'original',reason:'地点修订'}),7)
 const payload=vi.mocked(saveStandardParameter).mock.calls[0][1]
 expect(payload).not.toHaveProperty('departments');expect(payload).not.toHaveProperty('accreditation');expect(payload).not.toHaveProperty('sourceFile');expect(payload).not.toHaveProperty('certificateNo')
 expect(w.text()).toContain('参数已保存')
})
it('adds a parameter to a new standard with no source or accreditation copied',async()=>{
 vi.mocked(loadStandardParameters).mockResolvedValue({...page,rows:[],total:0})
 const w=setup();await flushPromises();await button(w,'新增参数').trigger('click')
 for(const [id,value] of [['itemName','新参数'],['objectName','新对象'],['site','示例站点B'],['address','完整地址'],['reason','新增检测需求']])await w.get('#parameter-'+id).setValue(value)
 await w.get('form').trigger('submit');await flushPromises()
 expect(saveStandardParameter).toHaveBeenCalledWith(1,expect.objectContaining({itemName:'新参数',reason:'新增检测需求'}),undefined)
 expect(vi.mocked(saveStandardParameter).mock.calls[0][1]).not.toHaveProperty('copyFromId')
})
it('searches another standard and copies a parameter into the current standard as a new record',async()=>{
 const w=setup();await flushPromises();await button(w,'从其他标准复制').trigger('click');await flushPromises()
 await w.get('input[aria-label="复制来源标准搜索"]').setValue('GB-OLD');await w.get('form').trigger('submit');await flushPromises()
 expect(searchParameterStandards).toHaveBeenLastCalledWith('GB-OLD',1)
 await button(w,'选择').trigger('click');await flushPromises();expect(loadStandardParameters).toHaveBeenLastCalledWith(2,'',1)
 await button(w,'复制').trigger('click');await w.get('#parameter-reason').setValue('复制后维护');await w.get('form').trigger('submit');await flushPromises()
 const [target,payload,entry]=vi.mocked(saveStandardParameter).mock.calls[0]
 expect(target).toBe(1);expect(entry).toBeUndefined();expect(payload.copyFromId).toBe(7);expect(payload).not.toHaveProperty('version');expect(payload).not.toHaveProperty('accreditation')
})
it('uses live search, button search, bounded paging and ignores old responses',async()=>{
 vi.useFakeTimers();const pending:((value:any)=>void)[]=[]
 vi.mocked(loadStandardParameters).mockImplementation(()=>new Promise(resolve=>pending.push(resolve)))
 const w=setup();await w.get('input[aria-label="参数搜索"]').setValue('新词');await vi.advanceTimersByTimeAsync(251)
 expect(loadStandardParameters).toHaveBeenLastCalledWith(1,'新词',1)
 pending[1]({...page,rows:[{...row,itemName:'新词参数'}]});await flushPromises();pending[0](page);await flushPromises()
 expect(w.text()).toContain('新词参数');expect(w.text()).not.toContain('气密性能')
 await button(w,'下一页').trigger('click');expect(loadStandardParameters).toHaveBeenLastCalledWith(1,'新词',2)
 pending[2](page);await flushPromises();await w.get('form').trigger('submit');expect(loadStandardParameters).toHaveBeenLastCalledWith(1,'新词',1)
})
it('hides write controls without maintenance actions and allows copying historical rows only',async()=>{
 grants.clear();const w=setup();await flushPromises()
 expect(button(w,'新增参数')).toBeUndefined();expect(button(w,'修改')).toBeUndefined();expect(button(w,'复制')).toBeUndefined()
 grants.add('quality.standard.create');grants.add('quality.standard.update');grants.add('quality.standard.authorize')
 vi.mocked(loadStandardParameters).mockResolvedValue({...page,rows:[{...row,active:false,superseded:true}]})
 const other=setup();await flushPromises();expect(button(other,'修改')).toBeUndefined();expect(button(other,'复制')).toBeDefined();expect(other.text()).toContain('历史修订')
})
it('keeps the draft after a failed save so the user can correct it',async()=>{
 vi.mocked(saveStandardParameter).mockRejectedValue(new Error('参数已被其他人修改'))
 const w=setup();await flushPromises();await button(w,'修改').trigger('click');await w.get('#parameter-reason').setValue('修改原因');await w.get('form').trigger('submit');await flushPromises()
 expect(w.get('[role="alert"]').text()).toContain('参数已被其他人修改');expect((w.get('#parameter-reason').element as HTMLTextAreaElement).value).toBe('修改原因')
})
