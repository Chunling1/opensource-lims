import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LoginView from '../views/auth/LoginView.vue'
import { PlatformError } from '../services/platform/http'
const api = vi.hoisted(() => ({ query: vi.fn(), login: vi.fn(), change: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('../services/auth/authApi', () => ({ AuthRequestError: class extends Error {}, queryLoginState: api.query, signIn: api.login, rememberedAccount: () => '', changeAccountPassword: api.change }))
const stubs = { AuthLayout: { template: '<main><slot /></main>' }, BootstrapModal: { props: ['open'], template: '<section v-if="open"><slot /></section>' }, AjCaptcha: { name: 'AjCaptcha', emits: ['verified'], template: '<div data-testid="fixture-captcha" />' }, RouterLink: true }
beforeEach(() => { vi.clearAllMocks(); api.query.mockResolvedValue({ captchaRequired: false }); api.login.mockRejectedValue(new PlatformError(3, '首次登录需修改密码', null)); api.change.mockResolvedValue(undefined) })
afterEach(() => { document.body.innerHTML = '' })
async function firstLogin() {
  const wrapper = mount(LoginView, { attachTo: document.body, global: { stubs } })
  await wrapper.get('#login-account').setValue('fixture')
  await wrapper.get('#login-password').setValue('fixture54321')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.find('#new-password').exists()).toBe(true)
  return wrapper
}
describe('first-login password feedback', () => {
  it('shows missing requirements under the new password, before CAPTCHA or network requests', async () => {
    const wrapper = await firstLogin()
    api.query.mockClear()
    await wrapper.get('#new-password').setValue('Abcdef12')
    await wrapper.get('#confirm-password').setValue('Abcdef12')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('#new-password-error').text()).toContain('特殊字符')
    expect(wrapper.get('#new-password').attributes('aria-invalid')).toBe('true')
    expect(document.activeElement?.id).toBe('new-password')
    expect(wrapper.find('#login-password-error').exists()).toBe(false)
    expect(wrapper.find('[data-testid="fixture-captcha"]').exists()).toBe(false)
    expect(api.query).not.toHaveBeenCalled(); expect(api.change).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('shows mismatches under confirmation', async () => {
    const wrapper = await firstLogin()
    await wrapper.get('#new-password').setValue('Abcdef12!')
    await wrapper.get('#confirm-password').setValue('Abcdef12?')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('#confirm-password-error').text()).toContain('不一致')
    expect(document.activeElement?.id).toBe('confirm-password')
    expect(wrapper.find('#login-password-error').exists()).toBe(false)
    wrapper.unmount()
  })
  it('accepts an exclamation mark and a temporary old password, and still requires CAPTCHA', async () => {
    const wrapper = await firstLogin()
    await wrapper.get('#new-password').setValue('Abcdef12!')
    await wrapper.get('#confirm-password').setValue('Abcdef12!')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.find('#new-password-error').exists()).toBe(false)
    expect(wrapper.find('[data-testid="fixture-captcha"]').exists()).toBe(true)
    expect(api.change).not.toHaveBeenCalled()
    wrapper.findComponent({ name: 'AjCaptcha' }).vm.$emit('verified', 'fixture-proof', Date.now() + 60000)
    await flushPromises()
    expect(api.change).toHaveBeenCalledWith('fixture', 'fixture54321', 'Abcdef12!', 'Abcdef12!', 'fixture-proof')
    expect(wrapper.text()).toContain('密码已修改，请使用新密码登录')
    wrapper.unmount()
  })
})
