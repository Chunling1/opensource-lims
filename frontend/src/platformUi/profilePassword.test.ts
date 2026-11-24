import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ProfileSettingsView from '../views/workspace/ProfileSettingsView.vue'
import UserMenu from '../components/layout/UserMenu.vue'
import { currentActor } from '../stores/session'

const api = vi.hoisted(() => ({ change: vi.fn(), signOut: vi.fn(), replace: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: { tab: 'password' } }), useRouter: () => ({ replace: api.replace }) }))
vi.mock('../services/auth/authApi', () => ({ changeAccountPassword: api.change, signOut: api.signOut }))
vi.mock('../stores/session', async importOriginal => ({ ...await importOriginal<object>(), refreshIdentity: vi.fn() }))
vi.mock('../components/common/useFormLeaveGuard', () => ({ useFormLeaveGuard: () => ({ commit: vi.fn() }) }))
const stubs = { RouterLink: true, BootstrapModal: true, FormLeaveConfirmation: true, TemplateToast: true }
beforeEach(() => {
  vi.clearAllMocks()
  currentActor.value = { id: 'fixture', name: '测试人员', roles: [], departmentId: '', scope: 'department', avatar: '' }
})

describe('profile defaults and signed-in password form', () => {
  for (const sidebar of [false, true]) it(`uses the gray placeholder in the ${sidebar ? 'sidebar' : 'topbar'}`, async () => {
    const wrapper = mount(UserMenu, { props: { sidebar }, global: { stubs } })
    expect(wrapper.get('img').attributes('src')).toContain('/users/user-dummy-img.jpg')
    currentActor.value = { ...currentActor.value, avatar: 'data:image/png;base64,fixture' }
    await flushPromises()
    expect(wrapper.get('img').attributes('src')).toBe('data:image/png;base64,fixture')
    await wrapper.get('img').trigger('error')
    expect(wrapper.get('img').attributes('src')).toContain('/users/user-dummy-img.jpg')
    wrapper.unmount()
  })

  it('submits the password form without a CAPTCHA and returns to login', async () => {
    const wrapper = mount(ProfileSettingsView, { global: { stubs } })
    await flushPromises()
    const form = wrapper.get('#profile-password-form')
    expect(form.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'AjCaptcha' }).exists()).toBe(false)
    const inputs = form.findAll('input')
    expect(inputs).toHaveLength(3)
    await inputs[0]!.setValue('OldSecret123!')
    await inputs[1]!.setValue('NewSecret123!')
    await inputs[2]!.setValue('NewSecret123!')
    await form.trigger('submit')
    await flushPromises()
    expect(api.change).toHaveBeenCalledWith('fixture', 'OldSecret123!', 'NewSecret123!', 'NewSecret123!')
    expect(api.signOut).toHaveBeenCalledOnce()
    expect(api.replace).toHaveBeenCalledWith({ path: '/login', query: { changed: '1' } })
    wrapper.unmount()
  })
})
