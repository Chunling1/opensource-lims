import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ authedFetch: vi.fn(), request: vi.fn() }))
vi.mock('@/services/http', () => api)
import { artifactObjectUrl } from '@/services/reportAssurance'

const state = (status: string, sourceHash = 'rev-2') => ({
  ok: true, status: 202, headers: new Headers({'content-type': 'application/json'}),
  json: async () => ({data: {status, sourceHash, message: status}}),
})
const pdf = () => ({ok: true, status: 200, headers: new Headers({'content-type': 'application/pdf'}), blob: async () => new Blob(['latest'])})

describe('current report preview', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks(); URL.createObjectURL = vi.fn(() => 'blob:latest') })
  afterEach(() => vi.useRealTimers())
  it('reuses ready bytes without requesting generation', async () => {
    api.authedFetch.mockResolvedValueOnce(pdf())
    expect(await artifactObjectUrl('R1', 'query', false, true)).toBe('blob:latest')
    expect(api.request).not.toHaveBeenCalled()
  })
  it('prepares once, waits and reads latest PDF without falling back', async () => {
    api.authedFetch.mockResolvedValueOnce(state('missing')).mockResolvedValueOnce(state('running')).mockResolvedValueOnce(pdf())
    api.request.mockResolvedValue({status: 'queued'})
    const result = artifactObjectUrl('R1', 'query', false, true)
    await vi.advanceTimersByTimeAsync(3500)
    expect(await result).toBe('blob:latest')
    expect(api.request).toHaveBeenCalledTimes(1)
    expect(api.request.mock.calls[0][0]).toContain('original=1&file=1&download=0')
  })
  it('new source during generation prepares the new revision', async () => {
    api.authedFetch.mockResolvedValueOnce(state('missing','rev-1')).mockResolvedValueOnce(state('missing','rev-2')).mockResolvedValueOnce(pdf())
    const result = artifactObjectUrl('R1', 'query', true, true)
    await vi.advanceTimersByTimeAsync(3500)
    expect(await result).toBe('blob:latest')
    expect(api.request).toHaveBeenCalledTimes(2)
    expect(api.request.mock.calls[1][0]).toContain('download=1')
  })
  it('a failed new generation is surfaced rather than displaying old bytes', async () => {
    api.authedFetch.mockResolvedValueOnce(state('missing')).mockResolvedValueOnce(state('failed'))
    const result = expect(artifactObjectUrl('R1', 'query')).rejects.toThrow('failed')
    await vi.advanceTimersByTimeAsync(2000)
    await result
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
