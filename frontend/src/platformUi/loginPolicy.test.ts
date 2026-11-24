import {describe,it,expect,vi,beforeEach} from 'vitest'
import {mount,flushPromises} from '@vue/test-utils'
import LoginView from '../views/auth/LoginView.vue'
const api=vi.hoisted(()=>({query:vi.fn(),login:vi.fn(),replace:vi.fn()}))
vi.mock('vue-router',()=>({useRoute:()=>({query:{}}),useRouter:()=>({replace:api.replace})}))
vi.mock('../services/auth/authApi',()=>({AuthRequestError:class extends Error{},queryLoginState:api.query,signIn:api.login,rememberedAccount:()=>'',changeAccountPassword:vi.fn()}))
beforeEach(()=>vi.clearAllMocks())
const stubs={AuthLayout:{template:'<main><slot /></main>'},PasswordField:{props:['modelValue'],emits:['update:modelValue'],template:'<input id="fixture-password" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'},BootstrapModal:{props:['open'],template:'<section v-if="open"><slot /></section>'},AjCaptcha:{template:'<div data-testid="fixture-captcha" />'},RouterLink:true}
describe('login challenge visibility',()=>{
 for(const required of [false,true])it(required?'opens challenge only after submit when last login failed':'logs in without challenge when last login succeeded',async()=>{
  api.query.mockResolvedValue({captchaRequired:required});api.login.mockResolvedValue(undefined)
  const wrapper=mount(LoginView,{global:{stubs}})
  expect(wrapper.find('[data-testid="fixture-captcha"]').exists()).toBe(false)
  expect(wrapper.find('[data-testid="captcha-entry"]').exists()).toBe(false)
  expect(api.query).not.toHaveBeenCalled()
  await wrapper.find('#login-account').setValue('fixture')
  await wrapper.find('#login-password').setValue('Fixture123!')
  await wrapper.find('form').trigger('submit');await flushPromises()
  expect(api.query).toHaveBeenCalledOnce()
  expect(wrapper.find('[data-testid="fixture-captcha"]').exists()).toBe(required)
  expect(api.login.mock.calls.length).toBe(required?0:1)
  if(!required)expect(api.query.mock.invocationCallOrder[0]).toBeLessThan(api.login.mock.invocationCallOrder[0]!)
  wrapper.unmount()
 })
})
