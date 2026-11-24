import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'
import Picker from './ContractSelection'
import { fetchContractSelectionPage, type Agreement } from '@/services/pipeline'
vi.mock('@/services/pipeline', () => ({ fetchContractSelectionPage: vi.fn() }))
vi.mock('../controls', () => ({ ElDialog: defineComponent({
  props: ['modelValue'], template: '<div v-if="modelValue"><slot/><slot name="footer"/></div>',
}) }))
const row = (id: number): Agreement => ({ id, agreementNo: `合同-${id}`, client: `客户-${id}`, projectName: '项目',
  erpType: '', contractType: '', projectCode: '', category: '', amount: '', payment: '',
  department: '登记部门', owner: '', info: {} })
const wrappers: ReturnType<typeof mount>[] = []
const setup = () => {
  const w = mount(Picker, { props: { modelValue: '合同-1', selected: row(1) } })
  wrappers.push(w); return w
}
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.useRealTimers(); vi.clearAllMocks() })
describe('contract selection', () => {
  it.each(['all', 'department'] as const)('explains the server-authorized %s scope and preserves selection', async scope => {
    vi.mocked(fetchContractSelectionPage).mockResolvedValue({ rows: [row(2)], total: 1, page: 1, size: 20, scope })
    const w = setup(); await w.get('button').trigger('click'); await flushPromises()
    expect(w.text()).toContain(scope === 'all' ? '全院所有已完成登记' : '项目部门（检测部门）为本人所属部门')
    if (scope === 'all') expect(w.text()).not.toContain('为本人所属部门')
    await w.get('input[type="radio"]').setValue(true)
    await w.findAll('button').find(b => b.text() === '确认选择')!.trigger('click')
    expect(w.emitted('picked')).toEqual([[row(2)]])
  })
  it('loads only when opened, searches automatically and immediately on submit, ignores old requests', async () => {
    vi.useFakeTimers()
    const pending: { resolve: (v: any) => void; signal: AbortSignal }[] = []
    vi.mocked(fetchContractSelectionPage).mockImplementation((_q, _p, signal) => new Promise(resolve => pending.push({ resolve, signal: signal! })))
    const w = setup()
    expect(fetchContractSelectionPage).not.toHaveBeenCalled()
    await w.get('button').trigger('click')
    await w.get('input[aria-label="搜索合同"]').setValue('客户')
    expect(pending[0].signal.aborted).toBe(true)
    await vi.advanceTimersByTimeAsync(260)
    expect(fetchContractSelectionPage).toHaveBeenLastCalledWith('客户', 1, expect.any(AbortSignal))
    await w.get('input[aria-label="搜索合同"]').setValue('新客户')
    await w.get('form').trigger('submit')
    expect(fetchContractSelectionPage).toHaveBeenLastCalledWith('新客户', 1, expect.any(AbortSignal))
    pending[2].resolve({ rows: [row(3)], total: 1, page: 1, size: 20 }); await flushPromises()
    pending[0].resolve({ rows: [row(99)], total: 100, page: 1, size: 20 }); await flushPromises()
    await vi.advanceTimersByTimeAsync(300)
    expect(fetchContractSelectionPage).toHaveBeenCalledTimes(3)
    expect(w.findAll('tbody tr')).toHaveLength(1)
    expect(w.get('tbody').text()).toContain('合同-3')
    expect(w.get('tbody').text()).not.toContain('合同-99')
  })
  it('paginates remotely, retains cross-page selection and emits only when confirmed', async () => {
    vi.mocked(fetchContractSelectionPage).mockResolvedValueOnce({ rows: [row(2)], total: 21, page: 1, size: 20 })
      .mockResolvedValueOnce({ rows: [row(21)], total: 21, page: 2, size: 20 })
    const w = setup(); await w.get('button').trigger('click'); await flushPromises()
    await w.get('input[type="radio"]').setValue(true)
    await w.findAll('button').find(b => b.text() === '下一页')!.trigger('click'); await flushPromises()
    expect(fetchContractSelectionPage).toHaveBeenLastCalledWith('', 2, expect.any(AbortSignal))
    expect(w.emitted('picked')).toBeUndefined()
    await w.findAll('button').find(b => b.text() === '确认选择')!.trigger('click')
    expect(w.emitted('picked')).toEqual([[row(2)]])
  })
  it('cancels without changing the contract and preserves the current label', async () => {
    vi.mocked(fetchContractSelectionPage).mockResolvedValue({ rows: [row(2)], total: 1, page: 1, size: 20 })
    const w = setup(); await w.get('button').trigger('click'); await flushPromises()
    await w.get('input[type="radio"]').setValue(true)
    await w.findAll('button').find(b => b.text() === '取消')!.trigger('click')
    expect(w.emitted('picked')).toBeUndefined()
    expect((w.get('input[aria-label="已关联合同"]').element as HTMLInputElement).value).toContain('合同-1')
  })
  it('allows clearing an existing contract without loading the list', async () => {
    const w = setup()
    await w.findAll('button').find(b => b.text() === '清空')!.trigger('click')
    expect(w.emitted('picked')).toEqual([[undefined]])
    expect(fetchContractSelectionPage).not.toHaveBeenCalled()
  })
  it('shows failed queries and allows retry; disabled forms cannot launch', async () => {
    vi.mocked(fetchContractSelectionPage).mockRejectedValueOnce(new Error('查询失败')).mockResolvedValueOnce({ rows: [], total: 0, page: 1, size: 20 })
    const w = setup(); await w.get('button').trigger('click'); await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('查询失败')
    await w.get('form').trigger('submit'); await flushPromises()
    expect(w.text()).toContain('暂无符合条件')
    await w.setProps({ disabled: true })
    expect(w.find('table').exists()).toBe(false)
    expect(w.get('button').attributes('disabled')).toBeDefined()
  })
})
