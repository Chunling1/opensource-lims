import { beforeEach, describe, expect, it, vi } from 'vitest'
import { changeAccountPassword } from '../services/auth/authApi'
import { setToken } from '../services/platform/http'

beforeEach(() => { vi.restoreAllMocks(); setToken('fixture-session') })
describe('password punctuation and validation fields', () => {
  const punctuation = Array.from({ length: 94 }, (_, i) => String.fromCharCode(33 + i)).filter(c => !/[A-Za-z0-9]/.test(c))
  it.each(punctuation)('accepts ASCII punctuation %s without relying on another character', async symbol => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ code: 0, data: null }), { headers: { 'content-type': 'application/json' } }))
    const password = `Abcdef12${symbol}`
    await changeAccountPassword('fixture', 'fixture54321', password, password)
    expect(fetcher).toHaveBeenCalledOnce()
  })
  it.each(['Abcdef12', 'Abcdef12 ', 'Abcdef12中', 'abcdef12!', 'ABCDEF12!', 'Abcdefgh!', 'Ab1!', `Aa1!${'x'.repeat(125)}`])('rejects an unmet requirement on the new password field: %s', async password => {
    const fetcher = vi.spyOn(globalThis, 'fetch')
    await expect(changeAccountPassword('fixture', 'fixture54321', password, password)).rejects.toMatchObject({ fieldErrors: { newPassword: expect.any(String) } })
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('places a mismatch on confirmation', async () => {
    await expect(changeAccountPassword('fixture', 'fixture54321', 'Abcdef12!', 'different')).rejects.toMatchObject({ fieldErrors: { confirmation: expect.any(String) } })
  })
  it.each([['原密码错误', 'oldPassword'], ['新密码不能与原密码相同', 'newPassword']])('places server error %s on %s', async (message, field) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ code: 1, message, data: null }), { headers: { 'content-type': 'application/json' } }))
    await expect(changeAccountPassword('fixture', 'fixture54321', 'Abcdef12!', 'Abcdef12!')).rejects.toMatchObject({ fieldErrors: { [field!]: message } })
    expect((await import('../services/platform/http')).getSessionToken()).toBe('fixture-session')
  })
})
