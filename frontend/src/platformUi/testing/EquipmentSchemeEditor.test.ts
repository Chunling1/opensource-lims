import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import EquipmentSchemeEditor from './EquipmentSchemeEditor.vue'
import EquipmentSchemeManager from './EquipmentSchemeManager.vue'
import { equipmentSchemes } from './equipmentSchemes'
import { PlatformError } from '../../services/platform/http'
vi.mock('./equipmentSchemes', () => ({ equipmentSchemes: { catalogue: vi.fn(), save: vi.fn() } }))
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.resetAllMocks() })
const catalogue: any = { departmentId: 1, department: '检测部', canManage: true, departments: [{ id: 1, name: '检测部' }], projectId: 2,
  projects: [{ id: 2, code: 'HR', name: '热回收' }], equipment: [{ id: 1, archiveNo: 'EQ1', name: '仪器', status: '停用' }], schemes: [] }
const global = { stubs: { RouterLink: true, BootstrapModal: { template: '<section><slot /><slot name="footer" /></section>' } } }
it('saves a named department combination and project association independently of current validity', async () => {
  vi.mocked(equipmentSchemes.save).mockResolvedValue({} as any)
  const wrapper = mount(EquipmentSchemeEditor, { props: { catalogue, initialIds: ['1'] }, global }); wrappers.push(wrapper)
  await wrapper.get('#instrument-scheme-name').setValue('HR组合')
  await wrapper.findAll('button').find(b => b.text() === '保存方案')!.trigger('click'); await flushPromises()
  expect(equipmentSchemes.save).toHaveBeenCalledWith(expect.objectContaining({ name: 'HR组合', departmentId: 1, equipmentIds: [1], projectIds: [2] }))
  expect(wrapper.emitted('saved')).toHaveLength(1)
})
it('keeps missing instruments visible for explicit removal and reports stale edits without closing', async () => {
  vi.mocked(equipmentSchemes.save).mockRejectedValue(new PlatformError(409, '方案已被修改，请刷新后重新编辑', null))
  const scheme: any = { id: 4, name: '旧组合', version: 3, enabled: true, departmentId: 1, equipmentIds: [1, 99], projectIds: [] }
  const wrapper = mount(EquipmentSchemeEditor, { props: { catalogue, scheme }, global }); wrappers.push(wrapper)
  expect(wrapper.text()).toContain('仪器 ID 99')
  await wrapper.findAll('button').find(b => b.text() === '保存方案')!.trigger('click'); await flushPromises()
  expect(equipmentSchemes.save).toHaveBeenCalledWith(expect.objectContaining({ id: 4, version: 3, equipmentIds: [1, 99] }))
  expect(wrapper.text()).toContain('方案已被修改')
  expect(wrapper.emitted('saved')).toBeUndefined()
})
it('maintenance catalogue loads without opening or modifying a report', async () => {
  vi.mocked(equipmentSchemes.catalogue).mockResolvedValue(catalogue)
  const wrapper = mount(EquipmentSchemeManager, { global }); wrappers.push(wrapper); await flushPromises()
  expect(equipmentSchemes.catalogue).toHaveBeenCalledWith(undefined, undefined)
  expect(wrapper.text()).toContain('新增仪器方案')
  expect(equipmentSchemes.save).not.toHaveBeenCalled()
})
