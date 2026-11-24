import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import SourceReportSelect from './SourceReportSelect.vue'
import { fetchDerivableReportPage } from '@/services/pipeline'
vi.mock('@/services/pipeline', () => ({ fetchDerivableReportPage: vi.fn() }))
const fetchPage = vi.mocked(fetchDerivableReportPage)
const response = (no='2026TEST-0001', root='LAB-2026TEST-0001') => ({rows:[{sampleNo:no, reportNo:'LAB-'+no,mainReportNo:root,projectName:'虚拟项目',client:'虚拟客户',project:'TEST',status:'待合同评审'}],total:35,page:1,size:20})
let wrapper: VueWrapper
function setup() {
  wrapper = mount(SourceReportSelect, {props:{modelValue:'',category:'分项'},global:{stubs:{
    BootstrapModal: defineComponent({props:['open'],template:'<section v-if="open"><slot name="toolbar"/><slot/><slot name="footer"/></section>'}),
    TablePagination: defineComponent({emits:['page'],template:'<button class="next" @click="$emit(\'page\',2)">下一页</button>'})
  }}})
  return wrapper
}
async function open() { await wrapper.get('button').trigger('click'); await flushPromises() }
beforeEach(() => {vi.useFakeTimers();fetchPage.mockReset();fetchPage.mockResolvedValue(response())})
afterEach(() => {wrapper?.unmount();vi.useRealTimers()})
describe('original sample source picker', () => {
  it('loads only on opening and searches all pages on the server', async () => {
    setup();expect(fetchPage).not.toHaveBeenCalled();await open()
    expect(fetchPage).toHaveBeenLastCalledWith({category:'分项',keyword:'',page:1,size:20},expect.any(AbortSignal))
    await wrapper.get('.next').trigger('click');await flushPromises()
    expect(fetchPage.mock.calls.at(-1)?.[0].page).toBe(2)
    await wrapper.get('[aria-label="样品编号搜索"]').setValue('0000')
    await vi.advanceTimersByTimeAsync(299);expect(fetchPage).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1);await flushPromises()
    expect(fetchPage.mock.calls.at(-1)?.[0]).toMatchObject({keyword:'0000',page:1})
  })
  it('supports explicit search without duplicate debounce requests', async () => {
    setup();await open();await wrapper.get('input[aria-label="样品编号搜索"]').setValue('0020')
    await wrapper.get('form').trigger('submit');await vi.advanceTimersByTimeAsync(500)
    expect(fetchPage).toHaveBeenCalledTimes(2)
  })
  it('selects by sample number while retaining the canonical numbering root', async () => {
    fetchPage.mockResolvedValue(response('2026TEST-0001-02'));setup();await open()
    expect(wrapper.text()).toContain('2026TEST-0001-02')
    await wrapper.get('.list-group-item').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['LAB-2026TEST-0001']])
    expect(wrapper.emitted('selected')?.[0]?.[0]).toMatchObject({sampleNo:'2026TEST-0001-02',mainReportNo:'LAB-2026TEST-0001'})
    expect(wrapper.find('section').exists()).toBe(false)
  })
  it('displays failure and permits retry', async () => {
    fetchPage.mockRejectedValueOnce(new Error('接口暂不可用'));setup();await open()
    expect(wrapper.get('[role="alert"]').text()).toContain('接口暂不可用')
    await wrapper.get('[role="alert"] button').trigger('click');await flushPromises()
    expect(wrapper.find('.list-group-item').exists()).toBe(true)
  })
  it('ignores stale replies and aborts on closing', async () => {
    let resolveOld!: (value:any)=>void
    fetchPage.mockImplementationOnce(() => new Promise(resolve => {resolveOld=resolve}))
    setup();await open();await wrapper.get('form').trigger('submit');await flushPromises()
    resolveOld(response('OLD'));await flushPromises();expect(wrapper.text()).not.toContain('OLD')
    await wrapper.findAll('button').find(b=>b.text()==='关闭')!.trigger('click')
    expect(fetchPage.mock.calls.at(-1)?.[1]?.aborted).toBe(true)
  })
  it('prevents selection when form becomes read-only and reopens with one request', async () => {
    setup();await open();await wrapper.get('input[aria-label="样品编号搜索"]').setValue('old')
    await wrapper.setProps({disabled:true});expect(wrapper.find('section').exists()).toBe(false)
    await wrapper.setProps({disabled:false});const count=fetchPage.mock.calls.length;await open()
    await vi.advanceTimersByTimeAsync(500);expect(fetchPage).toHaveBeenCalledTimes(count+1)
  })
})


it('English selection explains sample-only eligibility and selects a registration draft', async()=>{
 setup();await wrapper.setProps({category:'英文'});await open()
 expect(wrapper.text()).not.toContain('已录入检测标准')
 expect(wrapper.text()).toContain('各阶段的已有样品')
 expect(fetchPage.mock.calls.at(-1)?.[0].category).toBe('英文')
 await wrapper.get('.list-group-item').trigger('click')
 expect(wrapper.emitted('selected')?.[0]?.[0]).toMatchObject({status:'待合同评审'})
})
