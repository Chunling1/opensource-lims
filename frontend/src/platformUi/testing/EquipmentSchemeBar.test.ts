import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EquipmentSchemeBar from './EquipmentSchemeBar.vue'
import { equipmentSchemes } from './equipmentSchemes'
vi.mock('./equipmentSchemes', () => ({ equipmentSchemes: { catalogue: vi.fn(), resolve: vi.fn(), save: vi.fn() } }))
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.resetAllMocks() })
async function setup(manage = false) {
  vi.mocked(equipmentSchemes.catalogue).mockResolvedValue({ departmentId: 1, department: '检测部', departments: [], canManage: manage, projectId: 2, projects: [], equipment: [], schemes: [
    { id: 1, name: '常用组合', departmentId: 1, department: '检测部', version: 1, enabled: true, equipmentIds: [1, 2], projectIds: [2], recommended: true },
  ] })
  const wrapper = mount(EquipmentSchemeBar, { props: { reportNo: 'QA-1', dates: [{ kind: 'range', from: '2026-10-01', to: '2026-10-02' }], selected: ['1'] }, global: { stubs: { EquipmentSchemeEditor: true, RouterLink: true } } })
  wrappers.push(wrapper); await flushPromises()
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  return { wrapper, button }
}
describe('department instrument combinations', () => {
  it('automatically passes usable instruments and explicitly lists skipped instruments', async () => {
    const { wrapper, button } = await setup()
    vi.mocked(equipmentSchemes.resolve).mockResolvedValue({ schemeId: 1, version: 2, rows: [{ id: 1 }, { id: 3 }] as any, skipped: [{ id: '2', code: 'EQ2', name: '温度仪', reason: '校准有效期不足' }] })
    expect(wrapper.text()).toContain('当前项目推荐')
    await button('套用方案').trigger('click'); await flushPromises()
    expect(equipmentSchemes.resolve).toHaveBeenCalledWith(1, 'QA-1', [{ start: '2026-10-01', end: '2026-10-02' }])
    expect(wrapper.emitted('applied')![0][0]).toMatchObject({ version: 2, rows: [{ id: 1 }, { id: 3 }] })
    expect(wrapper.text()).toContain('已加入 1 台，已选中 1 台；跳过 1 台')
    expect(wrapper.text()).toContain('EQ2 温度仪：校准有效期不足，未带入')
    expect(wrapper.text()).not.toContain('维护方案')
  })
  it('all invalid still shows every reason and does not save or rewrite a scheme', async () => {
    const { wrapper, button } = await setup(true)
    vi.mocked(equipmentSchemes.resolve).mockResolvedValue({ schemeId: 1, version: 1, rows: [], skipped: [{ id: '1', code: '1', name: '仪器', reason: '维修中' }] })
    await button('套用方案').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('已加入 0 台')
    expect(wrapper.text()).toContain('维修中')
    expect(equipmentSchemes.save).not.toHaveBeenCalled()
    expect(button('维护方案').exists()).toBe(true)
  })
  it('requires complete dates and ignores in-flight results when dates change', async () => {
    const { wrapper, button } = await setup()
    let finish!: (v: any) => void
    vi.mocked(equipmentSchemes.resolve).mockImplementation(() => new Promise(r => { finish = r }))
    await button('套用方案').trigger('click')
    await wrapper.setProps({ dates: [{ kind: 'range', from: '', to: '' }] })
    finish({ rows: [{ id: 1 }], skipped: [] }); await flushPromises()
    expect(wrapper.emitted('applied')).toBeUndefined()
    expect(button('套用方案').attributes('disabled')).toBeDefined()
  })
  it('request failure adds nothing and allows explicit retry', async () => {
    const { wrapper, button } = await setup()
    vi.mocked(equipmentSchemes.resolve).mockRejectedValue(new Error('方案已停用'))
    await button('套用方案').trigger('click'); await flushPromises()
    expect(wrapper.emitted('applied')).toBeUndefined()
    expect(button('套用方案').attributes('disabled')).toBeUndefined()
  })
})
