import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { router } from '../router'
import { PlatformSession } from '../platformSession'
import { profile, refreshProfile, logout, type Profile } from '../services/platform/auth'
import { refreshIdentity } from '../stores/session'
import { platformRequest, setToken, getSessionToken } from '../services/platform/http'
import { request, authedFetch, setAccessToken } from '@/services/http'

const route = reactive({ path: '/login', fullPath: '/dashboard' })
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('../router', () => ({ router: { replace: vi.fn() } }))
vi.mock('../stores/session', () => ({ refreshIdentity: vi.fn().mockResolvedValue(undefined) }))
vi.mock('../views/auth/LoginView.vue', () => ({ default: {
  name: 'FixtureLogin', props: ['sessionExpired'], data: () => ({ account: '' }),
  template: '<input aria-label="账号" v-model="account" /><div v-if="sessionExpired">登录已失效</div>',
} }))
vi.mock('../App.vue', () => ({ default: { template: '<main>Workspace</main>' } }))
const user = (account: string) => ({ account, userName: account, roleKey:'tester', roleName:'检测',
  homePath:'/dashboard', permissions:[], actionPermissions:[],
  dataScope:{department:'测试部门',scopeType:'self',description:'本人'} }) as Profile
const response = (code: number, status = 200, data: unknown = null) => new Response(
  JSON.stringify({code, message:'fixture response', data}),
  {status,headers:{'content-type':'application/json'}},
)
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(r => { resolve = r })
  return { promise, resolve }
}
beforeEach(() => { vi.mocked(router.replace).mockClear(); setAccessToken(''); profile.value=undefined; route.path='/login'; vi.mocked(refreshIdentity).mockResolvedValue(undefined) })
afterEach(() => vi.restoreAllMocks())

it('keeps the submitting login form mounted until navigation actually leaves login', async () => {
  const wrapper=mount(PlatformSession)
  try {
    await wrapper.get('input').setValue('in-flight-login')
    const originalInput=wrapper.get('input').element
    // Login has returned credentials; identity loading/navigation are still pending.
    setToken('new-session'); profile.value=user('new-user')
    await nextTick()
    expect(wrapper.find('main').exists()).toBe(false)
    expect(wrapper.get('input').element).toBe(originalInput)
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('in-flight-login')
    route.path='/dashboard'; await nextTick()
    expect(wrapper.get('main').text()).toBe('Workspace')
    expect(wrapper.find('input').exists()).toBe(false)
  } finally { wrapper.unmount() }
})

it.each([200,401])('ignores an old platform request 401 after a new login (HTTP %i)', async status => {
  const pending=deferred<Response>(); vi.spyOn(globalThis,'fetch').mockReturnValue(pending.promise)
  const event=vi.spyOn(window,'dispatchEvent')
  setToken('old-session')
  const result=platformRequest('/api/auth/profile').catch(e=>e)
  setToken('new-session'); pending.resolve(response(401,status))
  expect(await result).toMatchObject({code:'UNAUTHORIZED'})
  expect(getSessionToken()).toBe('new-session'); expect(event).not.toHaveBeenCalled()
})

it('does not invalidate a session because an anonymous login request failed', async () => {
  vi.spyOn(globalThis,'fetch').mockResolvedValue(response(401,401)); setToken('new-session')
  await expect(platformRequest('/api/auth/login',{anonymous:true})).rejects.toMatchObject({code:'UNAUTHORIZED'})
  expect(getSessionToken()).toBe('new-session')
})

it.each(['json','blob'] as const)('ignores an old business %s request 401 after new login', async kind => {
  const pending=deferred<Response>(); vi.spyOn(globalThis,'fetch').mockReturnValue(pending.promise)
  const event=vi.spyOn(window,'dispatchEvent')
  setAccessToken('old-session')
  const result=(kind==='json'?request('/api/samples/query'):authedFetch('/api/reports/R/pdf')).catch(e=>e)
  setAccessToken('new-session'); pending.resolve(response(401,401)); await result
  expect(getSessionToken()).toBe('new-session'); expect(event).not.toHaveBeenCalled()
})

it.each(['platform','business','blob'] as const)('still invalidates the current expired %s session', async kind => {
  vi.spyOn(globalThis,'fetch').mockResolvedValue(response(401,401))
  const event=vi.spyOn(window,'dispatchEvent'); setAccessToken('current-session')
  await (kind==='platform'?platformRequest('/api/auth/profile'):kind==='business'?request('/api/samples/query'):authedFetch('/api/reports/R/pdf')).catch(()=>{})
  expect(getSessionToken()).toBe('')
  expect(event.mock.calls.some(([e])=>e.type==='lims-next:unauthorized')).toBe(true)
})

it('does not replace the new profile when an old profile refresh succeeds late', async () => {
  const pending=deferred<Response>(); vi.spyOn(globalThis,'fetch').mockReturnValue(pending.promise)
  setToken('old-session'); const result=refreshProfile().catch(e=>e)
  setToken('new-session'); profile.value=user('new-user')
  pending.resolve(response(0,200,user('old-user'))); await result
  expect(profile.value?.account).toBe('new-user')
})

it('does not restore a logged-out profile from a late successful response', async () => {
  const pending=deferred<Response>(); vi.spyOn(globalThis,'fetch').mockReturnValue(pending.promise)
  setToken('old-session'); profile.value=user('old-user')
  const result=refreshProfile().catch(e=>e)
  logout(); pending.resolve(response(0,200,user('old-user'))); await result
  expect(profile.value).toBeUndefined(); expect(getSessionToken()).toBe('')
})

it('does not log out a new session when startup restoration of an old session fails', async () => {
  const pending=deferred<void>(); vi.mocked(refreshIdentity).mockImplementationOnce(async()=>{await pending.promise;throw Error('old restoration failed')})
  setToken('old-session'); const wrapper=mount(PlatformSession)
  try {
    setToken('new-session'); profile.value=user('new-user'); route.path='/dashboard'
    pending.resolve(); await flushPromises()
    expect(getSessionToken()).toBe('new-session'); expect(profile.value?.account).toBe('new-user')
    expect(wrapper.get('main').text()).toBe('Workspace')
  } finally { wrapper.unmount() }
})


it.each(['network', 500, 502, 503, 504] as const)('retains the session after %s during restoration and retries only the profile', async failure => {
  const fetch=vi.spyOn(globalThis, 'fetch')
  if (failure === 'network') fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  if (failure !== 'network') fetch.mockResolvedValueOnce(response(1, failure))
  fetch.mockResolvedValue(response(0, 200, user('current-user')))
  vi.mocked(refreshIdentity).mockImplementation(async () => { await refreshProfile() })
  setToken('current-session'); route.path='/dashboard'
  const wrapper=mount(PlatformSession, {global:{stubs:{RouterLink:true}}})
  try {
    await flushPromises()
    expect(getSessionToken()).toBe('current-session')
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.findComponent({name:'ErrorPage'}).exists()).toBe(true)
    expect(vi.mocked(router.replace)).not.toHaveBeenCalled()
    expect(fetch).toHaveBeenCalledTimes(1)
    await wrapper.findAll('button').find(button => button.text() === '重试')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('main').text()).toBe('Workspace')
    expect(profile.value?.account).toBe('current-user')
    expect(getSessionToken()).toBe('current-session')
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls.every(([url]) => url === '/api/auth/profile')).toBe(true)
  } finally { wrapper.unmount() }
})

it('clears an expired session during restoration and requests login', async () => {
  vi.spyOn(globalThis,'fetch').mockResolvedValue(response(401,401))
  vi.mocked(refreshIdentity).mockImplementation(async () => { await refreshProfile() })
  setToken('expired-session'); route.path='/dashboard'
  const wrapper=mount(PlatformSession)
  try {
    await flushPromises()
    expect(getSessionToken()).toBe('')
    expect(vi.mocked(router.replace)).toHaveBeenCalledWith({path:'/login', query:{redirect:'/dashboard'}})
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.findComponent({name:'ErrorPage'}).exists()).toBe(false)
  } finally { wrapper.unmount() }
})

it('keeps the open workspace mounted during an outage and checks only the profile on reconnect', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch')
  vi.mocked(refreshIdentity).mockImplementation(async () => { await refreshProfile() })
  fetch.mockImplementation(async () => response(0, 200, user('tester')))
  setToken('current-session'); route.path = '/dashboard'
  const wrapper = mount(PlatformSession)
  try {
    await flushPromises()
    const workspace = wrapper.get('main').element
    window.dispatchEvent(new Event('offline'))
    await nextTick()
    expect(wrapper.text()).toContain('网络已断开')
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(wrapper.text()).toContain('连接中断或超时')
    expect(wrapper.get('main').element).toBe(workspace)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.get('main').element).toBe(workspace)
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(Array(3).fill('/api/auth/profile'))
    expect(router.replace).not.toHaveBeenCalled()
  } finally { wrapper.unmount() }
})

it('sets a deadline on JSON reads, releases a hung request and keeps the session', async () => {
  const deadline = new AbortController()
  const timeout = vi.spyOn(AbortSignal, 'timeout').mockReturnValue(deadline.signal)
  vi.spyOn(globalThis, 'fetch').mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(options.signal?.reason))
  }))
  const event = vi.spyOn(window, 'dispatchEvent')
  setToken('current-session')
  const pending = request('/api/reports/R1/complete-preview-state')
  deadline.abort(new DOMException('timeout', 'TimeoutError'))
  await expect(pending).rejects.toMatchObject({code:'NETWORK'})
  expect(timeout).toHaveBeenCalledWith(30_000)
  expect(event.mock.calls.some(([value]) => value.type === 'lims:connection-interrupted')).toBe(true)
  expect(getSessionToken()).toBe('current-session')
})

it('identifies expiration when the existing workspace reconnects', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(0, 200, user('tester')))
  vi.mocked(refreshIdentity).mockImplementation(async () => { await refreshProfile() })
  setToken('active-session'); route.path = '/dashboard'
  const wrapper = mount(PlatformSession)
  try {
    await flushPromises()
    expect(wrapper.get('main').text()).toBe('Workspace')
    fetch.mockResolvedValueOnce(response(401,401))
    window.dispatchEvent(new Event('online'))
    await flushPromises()
    expect(wrapper.text()).toContain('登录已失效')
    expect(router.replace).toHaveBeenCalledExactlyOnceWith({path:'/login',query:{redirect:'/dashboard'}})
    expect(fetch).toHaveBeenCalledTimes(2)
  } finally { wrapper.unmount() }
})
