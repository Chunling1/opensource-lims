import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Page from '@/pages/UserAdminPage.vue'

const api = vi.hoisted(() => ({ user: {} as any, update: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ path: '/system/user', meta: {} }) }))
vi.mock('@/services/admin', () => ({
  ADMIN_AVAILABLE: true,
  listUsers: async () => [api.user], getUser: async () => structuredClone(api.user),
  getCatalog: async () => ({ permissions: [], actions: [], sites: [], projects: [], stepColumns: [],
    departments: [{ id: 1, name: '虚拟办公室' }, { id: 2, name: '虚拟检测部' }],
    scopeTypes: [{ value: 'department_project', label: '本部门＋授权部门＋授权项目' }] }),
  updateUser: (...args: any[]) => api.update(...args),
  createUser: vi.fn(), resetUserPassword: vi.fn(), getDepartmentStandardCatalog: vi.fn(),
}))

beforeEach(() => {
  api.user = { id: 1, account: 'qa', name: '虚拟人员', departmentId: 1,
    dataScope: { scopeType: 'department_project', description: '', department: '虚拟办公室' },
    permissions: [], actionPermissions: [], projectStepIds: [], dataDepartmentIds: [2], dataSites: [],
    standardAuthorization: { items: [], authorizedItemIds: [], department: '' }, enabled: true }
  api.update.mockReset().mockImplementation(async (_id, body) => ({ ...api.user, ...body }))
})

async function render() {
  const slot = { template: '<div><slot name="header"/><slot/><slot name="footer"/></div>' }
  const wrapper = mount(Page, { global: { stubs: {
    ModuleWorkspace: { template: '<main><slot name="header-actions"/><slot/></main>' },
    ElCard: slot, ElTabs: slot, ElTabPane: slot, ElForm: slot, ElFormItem: slot,
    ElDialog: true, ElSelect: true, ElOption: true, ElInput: true, ElSwitch: true, ElTag: slot,
    ElButton: { template: '<button><slot/></button>' },
    ElAlert: { props: ['title'], template: '<p>{{ title }}</p>' },
    ElCheckbox: { props: ['modelValue', 'label'], emits: ['update:modelValue'],
      template: '<label><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)"/>{{ label }}<slot/></label>' },
  } } })
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text().includes('虚拟人员'))!.trigger('click')
  await flushPromises()
  return wrapper
}

describe('department grants in roster scope', () => {
  it('shows existing grants and saves a changed selection without changing scope or project rights', async () => {
    const wrapper = await render()
    expect(wrapper.text()).toContain('部门数据授权不增加项目办理权限')
    const lab = wrapper.findAll('label').find(n => n.text() === '虚拟检测部')!
    expect((lab.get('input').element as HTMLInputElement).checked).toBe(true)
    await lab.get('input').setValue(false)
    await wrapper.findAll('button').find(b => b.text() === '保存授权')!.trigger('click')
    await flushPromises()
    expect(api.update).toHaveBeenCalledWith(1, expect.objectContaining({
      dataDepartmentIds: [], dataScopeType: 'department_project', projectStepIds: [],
    }))
    wrapper.unmount()
  })
  it('keeps self scope explicit and hides inapplicable department choices', async () => {
    api.user.dataScope.scopeType = 'self'
    const wrapper = await render()
    expect(wrapper.text()).toContain('仅本人')
    expect(wrapper.text()).not.toContain('授权部门（可跨部门')
    expect(api.update).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
