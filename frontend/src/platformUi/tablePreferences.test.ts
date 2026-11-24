import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref, toRef, type EffectScope } from 'vue'
const transport = vi.hoisted(() => ({ request: vi.fn(), token: 'token-a' }))
vi.mock('../services/platform/http', () => ({ platformRequest: transport.request, getSessionToken: () => transport.token, setToken: vi.fn() }))
import { profile } from '../services/platform/auth'
import { flushTablePreferences, persistTableSettings, preferenceError } from '../services/platform/tablePreferences'
import { useRegistrationPresentation } from './commissions/registrationPresentation'

const scopes: EffectScope[] = []
function mount<T>(run: () => T): T { const scope = effectScope(); scopes.push(scope); return scope.run(run)! }
function login(account = 'a', preferences = {}) { profile.value = { account, uiPreferences: preferences } as any }
function table(key = ref('review.samples')) {
  return mount(() => {
    const columns = ref(['code', 'name']), query = reactive({ pageSize: 10, sort: 'code', direction: 'asc' })
    persistTableSettings(() => key.value, { columns, pageSize: toRef(query, 'pageSize'), sort: toRef(query, 'sort'), direction: toRef(query, 'direction') })
    return { columns, query, key }
  })
}
beforeEach(() => { profile.value = undefined; transport.token = 'token-a'; transport.request.mockReset().mockResolvedValue({}); login() })
afterEach(async () => { await flushTablePreferences(); scopes.splice(0).forEach(scope => scope.stop()); profile.value = undefined })

describe('Account table display persistence', () => {
  it('introduces a missing column once and preserves subsequent user visibility choices', async () => {
    profile.value = undefined
    login('a', {'list:flow': {columns: ['code'], pageSize: 50}})
    const open = () => mount(() => {
      const columns = ref(['code', 'reportCode']), pageSize = ref(10)
      persistTableSettings(() => 'list:flow', {columns, pageSize}, ['reportCode'])
      return {columns, pageSize}
    })
    const first = open()
    expect(first.columns.value).toEqual(['code', 'reportCode'])
    expect(first.pageSize.value).toBe(50)
    await flushTablePreferences()
    expect(transport.request.mock.lastCall?.[1].body.settings.introducedColumns).toEqual(['reportCode'])
    first.columns.value = ['code']
    await flushTablePreferences()
    expect(open().columns.value).toEqual(['code'])
  })
  it('restores columns, page size and sorting without writing default values on mount', () => {
    login('a', { 'review.samples': { columns: ['code'], pageSize: 50, sort: 'name', direction: 'desc' } })
    // A new login has a new session; background profile refresh must not reset edits.
    profile.value = undefined; login('a', { 'review.samples': { columns: ['code'], pageSize: 50, sort: 'name', direction: 'desc' } })
    const t = table()
    expect(t.columns.value).toEqual(['code']); expect(t.query).toEqual({ pageSize: 50, sort: 'name', direction: 'desc' })
    expect(transport.request).not.toHaveBeenCalled()
  })
  it('saves the last rapid edit and restores it when re-entering the page', async () => {
    const t = table(); t.columns.value = ['code']; t.columns.value = ['code', 'reportCode']; t.query.pageSize = 25
    expect(await flushTablePreferences()).toBe(true)
    expect(transport.request.mock.lastCall?.[1].body.settings).toEqual({ columns: ['code', 'reportCode'], pageSize: 25, sort: 'code', direction: 'asc' })
    expect(table().columns.value).toEqual(['code', 'reportCode'])
  })
  it('separates table scopes and accounts, including two users in the same browser', async () => {
    const t = table(); t.columns.value = ['code']; await flushTablePreferences()
    t.key.value = 'registration.samples'; expect(t.columns.value).toEqual(['code', 'name'])
    t.key.value = 'review.samples'; expect(t.columns.value).toEqual(['code'])
    transport.token = 'token-b'; login('b'); expect(t.columns.value).toEqual(['code', 'name'])
    expect(transport.request).toHaveBeenCalledTimes(1)
  })
  it('keeps failed saves visible and retryable, then clears the error only after success', async () => {
    transport.request.mockRejectedValue(new Error('offline'))
    const t = table(); t.columns.value = ['code']
    expect(await flushTablePreferences()).toBe(false); expect(preferenceError.value).toContain('未保存')
    transport.request.mockResolvedValue({}); expect(await flushTablePreferences()).toBe(true); expect(preferenceError.value).toBe('')
  })
  it('does not let a stale profile refresh replace pending local edits', async () => {
    const t = table(); t.columns.value = ['code']; login('a', {})
    expect(t.columns.value).toEqual(['code']); await flushTablePreferences()
  })
  it('does not send an old account queue under a new login', async () => {
    let finish!: () => void
    transport.request.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve }))
    const t = table(); t.columns.value = ['code']; t.query.pageSize = 25
    transport.token = 'token-b'; login('b'); t.columns.value = ['name']
    finish(); expect(await flushTablePreferences()).toBe(true)
    expect(transport.request.mock.calls.map(call => call[1].body.settings.columns)).toEqual([['code'], ['name']])
    expect(transport.request.mock.lastCall?.[1].body.settings.pageSize).toBe(10)
  })
  it('persists the exact sample-column selector from contract review, including restore defaults', async () => {
    const controller = () => reactive<any>({ mode: 'review', backendEntrust: [], onWorkbenchSelectionChange: vi.fn(), session: { can: () => true, canAction: () => true } })
    const first = mount(() => useRegistrationPresentation(controller()))
    const defaults = [...first.sampleColumnKeys]
    first.toggleSampleColumn('erpProjectNo', true)
    await flushTablePreferences()
    const second = mount(() => useRegistrationPresentation(controller()))
    expect(second.sampleColumnKeys).toContain('erpProjectNo')
    second.resetSampleColumns(); await flushTablePreferences()
    expect(mount(() => useRegistrationPresentation(controller())).sampleColumnKeys).toEqual(defaults)
  })
})
