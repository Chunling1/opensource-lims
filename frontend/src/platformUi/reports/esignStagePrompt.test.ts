import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Prompt from '@/components/StageSigningPrompt.vue'
import { useSessionStore } from '@/stores/session'
import { fetchPendingStages, resumeEsignStage, getEsignSignUrl, refreshMyEsignTask } from '@/services/esign'
vi.mock('@/services/esign', () => ({ fetchPendingStages: vi.fn(), resumeEsignStage: vi.fn(), getEsignSignUrl: vi.fn(), refreshMyEsignTask: vi.fn() }))
const task = { id: 4, reportNo: 'LOCAL-0337', documentVersionId: 1, attemptNo: 1, provider: 'esign', providerFlowId: 'LOCAL', status: 'signing', sourceSha256: 'source', signedSha256: '', errorCode: '', errorMessage: '', dispatchedAt: '', completedAt: '', createdAt: '', signers: [], myRole: '主检' as const, myStatus: 'pending', canSign: true, positioning: { businessStages: { mode: 'business_stages_v1' } } }
const render = () => mount(Prompt, { global: { stubs: { BootstrapModal: { props: ['open'], template: '<section v-if="open"><slot/><slot name="footer"/></section>' } } } })
beforeEach(() => { vi.clearAllMocks(); setActivePinia(createPinia()); useSessionStore().account = 'LOCAL'; useSessionStore().stageSigning = true; vi.mocked(fetchPendingStages).mockResolvedValue([task]) })
describe('stage prompt', () => {
  it('prepares a new link for every role in one account and flow without reloading', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(resumeEsignStage).mockResolvedValue({})
    for (const myRole of ['主检', '审核', '批准']) {
      vi.mocked(fetchPendingStages).mockResolvedValue([{ ...task, myRole }])
      window.dispatchEvent(new Event('esign-stage-confirmed')); await flushPromises()
      expect(wrapper.find('a').exists()).toBe(false)
      const url = 'https://t.esign.cn/' + encodeURIComponent(myRole)
      vi.mocked(getEsignSignUrl).mockResolvedValue({ url, shortUrl: '' })
      await wrapper.findAll('button').find(b => b.text() === '准备本人签署入口')!.trigger('click'); await flushPromises()
      expect(wrapper.get('a').attributes('href')).toBe(url)
    }
    expect(resumeEsignStage).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })
  it('discards a signing link returned after account switching', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(resumeEsignStage).mockResolvedValue({})
    vi.mocked(getEsignSignUrl).mockImplementation(async () => {
      useSessionStore().account = 'OTHER'
      return { url: 'https://t.esign.cn/OLD', shortUrl: '' }
    })
    await wrapper.findAll('button').find(b => b.text() === '准备本人签署入口')!.trigger('click'); await flushPromises()
    window.dispatchEvent(new Event('esign-stage-confirmed')); await flushPromises()
    expect(wrapper.find('a').exists()).toBe(false)
    wrapper.unmount()
  })
  it('does not request a signing URL until explicitly clicked', async () => {
    const wrapper = render(); await flushPromises()
    expect(wrapper.text()).toContain('LOCAL-0337'); expect(getEsignSignUrl).not.toHaveBeenCalled()
    vi.mocked(resumeEsignStage).mockResolvedValue({}); vi.mocked(getEsignSignUrl).mockResolvedValue({ url: 'https://t.esign.cn/LOCAL', shortUrl: '' })
    await wrapper.findAll('button').find(b => b.text() === '准备本人签署入口')!.trigger('click'); await flushPromises()
    expect(wrapper.get('a').attributes('href')).toBe('https://t.esign.cn/LOCAL')
    expect(wrapper.get('a').attributes('rel')).toBe('noopener noreferrer')
    wrapper.unmount()
  })
  it('leaves provider failure visible and never requests sign URL after failed preparation', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(resumeEsignStage).mockResolvedValue({ esignPrepareError: '准备结果待核实' })
    await wrapper.findAll('button').find(b => b.text() === '准备本人签署入口')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('准备结果待核实'); expect(getEsignSignUrl).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('does not display old flow as a new workflow prompt', async () => {
    useSessionStore().stageSigning = false
    const wrapper = render(); await flushPromises(); expect(wrapper.find('section').exists()).toBe(false); expect(fetchPendingStages).not.toHaveBeenCalled(); wrapper.unmount()
  })
  it('refreshes provider result and closes completed tasks', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(refreshMyEsignTask).mockResolvedValue(task); vi.mocked(fetchPendingStages).mockResolvedValue([])
    await wrapper.findAll('button').find(b => b.text() === '我已签署，核对状态')!.trigger('click'); await flushPromises()
    expect(refreshMyEsignTask).toHaveBeenCalledExactlyOnceWith(4)
    expect(wrapper.find('section').exists()).toBe(false); expect(fetchPendingStages).toHaveBeenCalledTimes(2); wrapper.unmount()
  })
})
