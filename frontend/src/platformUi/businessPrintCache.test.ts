import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchEntrustPrint, fetchSamplePrint, previewSampleEntrust, type BusinessFormPrint, type BusinessFormTemplateKind } from '@/services/pipeline'
import { authedFetch } from '@/services/http'

vi.mock('@/services/http', () => ({ authedFetch: vi.fn(), request: vi.fn() }))
vi.mock('@/services/auth', () => ({ USE_BACKEND: true }))

const cached: BusinessFormPrint = { type: 'pdf', url: 'blob:product', name: 'sample.pdf',
  sourceHash: 'source', engine: 'wps', expectedPages: 3, etag: '"pdf-v1"' }

afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals() })

describe('authorized business PDF reuse', () => {
  it.each(['sample', 'entrust'])('rechecks %s on the server and reuses the Blob only for matching 304', async kind => {
    vi.mocked(authedFetch).mockResolvedValue(new Response(null, { status: 304, headers: { ETag: '"pdf-v1"' } }))
    const result = kind === 'sample'
      ? await fetchSamplePrint('SAMPLE', 'pdf', 'product', [], cached)
      : await fetchEntrustPrint(1, 'pdf', 'product', cached)
    expect(result).toBe(cached)
    expect(authedFetch).toHaveBeenCalledTimes(1)
    expect(vi.mocked(authedFetch).mock.calls[0]![1]?.headers).toEqual({ 'If-None-Match': '"pdf-v1"' })
  })
  it('never falls back to stale PDFs after a permission error', async () => {
    vi.mocked(authedFetch).mockResolvedValue(new Response(JSON.stringify({ code: 403, message: '无权限' }),
      { headers: { 'Content-Type': 'application/json' } }))
    await expect(fetchSamplePrint('SAMPLE', 'pdf', 'product', [], cached)).rejects.toThrow('无权限')
  })
  it('rejects a mismatched 304 validator', async () => {
    vi.mocked(authedFetch).mockResolvedValue(new Response(null, { status: 304, headers: { ETag: '"other"' } }))
    await expect(fetchSamplePrint('SAMPLE', 'pdf', 'product', [], cached)).rejects.toThrow('缓存校验失败')
  })
  it('replaces the PDF when the server returns modified content', async () => {
    const create = vi.fn(() => 'blob:modified')
    vi.stubGlobal('URL', { createObjectURL: create })
    vi.mocked(authedFetch).mockResolvedValue(new Response('%PDF-modified', {
      headers: { 'Content-Type': 'application/pdf', ETag: '"pdf-v2"' },
    }))
    const result = await fetchSamplePrint('SAMPLE', 'pdf', 'product', [], cached)
    expect(result.url).toBe('blob:modified')
    expect(result).toMatchObject({ etag: '"pdf-v2"' })
    expect(create).toHaveBeenCalledTimes(1)
  })
})

describe('sample form preview and download reuse', () => {
  it.each<BusinessFormTemplateKind>(['product', 'engineering', 'product-extended', 'engineering-extended'])('reuses one PDF across refresh and download checks for %s', async template => {
    const create = vi.fn(() => 'blob:unchanged')
    vi.stubGlobal('URL', { createObjectURL: create })
    vi.mocked(authedFetch).mockImplementation(async (_url, init) => {
      if (new Headers(init?.headers).get('If-None-Match') === '"pdf-v1"') {
        return new Response(null, { status: 304, headers: { ETag: '"pdf-v1"' } })
      }
      return new Response('%PDF-same', { headers: {
        'Content-Type': 'application/pdf', ETag: '"pdf-v1"',
        'X-Source-Document-SHA256': 'source-v1', 'X-Expected-Pages': '4',
      } })
    })
    const payload = { sampleNo: 'QA-ONLY', detail: { rawSample: { sampleName: '同一份样品' } } }
    const first = await previewSampleEntrust(payload, template)
    for (let check = 0; check < 3; check++) {
      expect(await previewSampleEntrust(payload, template, () => true, () => {}, first)).toBe(first)
    }
    expect(create).toHaveBeenCalledTimes(1)
    for (const [url, init] of vi.mocked(authedFetch).mock.calls.slice(1)) {
      expect(url).toBe('/api/samples/entrust-preview')
      expect(new Headers(init?.headers).get('If-None-Match')).toBe('"pdf-v1"')
      expect(JSON.parse(String(init?.body))).toMatchObject({ ...payload, templateKind: template })
    }
  })
  it('keeps the same validator and Blob when the server must poll', async () => {
    const create = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create })
    vi.mocked(authedFetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: 0, data: { status: 'ready', pollUrl: '/api/samples/entrust-preview-jobs/qa' } }), { status: 202 }))
      .mockResolvedValueOnce(new Response(null, { status: 304, headers: { ETag: cached.etag! } }))
    expect(await previewSampleEntrust({ sampleNo: 'QA' }, 'product', () => true, () => {}, cached as Extract<BusinessFormPrint, {type:'pdf'}>)).toBe(cached)
    expect(authedFetch).toHaveBeenCalledTimes(2)
    for (const [, init] of vi.mocked(authedFetch).mock.calls) expect(new Headers(init?.headers).get('If-None-Match')).toBe(cached.etag)
    expect(create).not.toHaveBeenCalled()
  })
  it('receives a new PDF only for changed content and never reuses it after permission denial', async () => {
    const create = vi.fn(() => 'blob:changed')
    vi.stubGlobal('URL', { createObjectURL: create })
    vi.mocked(authedFetch).mockResolvedValueOnce(new Response('%PDF-new', { headers: { 'Content-Type': 'application/pdf', ETag: '"pdf-v2"' } }))
    const result = await previewSampleEntrust({ sampleNo: 'QA' }, 'product', () => true, () => {}, cached as Extract<BusinessFormPrint, {type:'pdf'}>)
    expect(result).toMatchObject({ url: 'blob:changed', etag: '"pdf-v2"' })
    vi.mocked(authedFetch).mockResolvedValueOnce(new Response(JSON.stringify({ code: 403, message: '无预览权限' }), { headers: { 'Content-Type': 'application/json' } }))
    await expect(previewSampleEntrust({ sampleNo: 'QA' }, 'product', () => true, () => {}, result)).rejects.toThrow('无预览权限')
    expect(create).toHaveBeenCalledTimes(1)
  })
  it('rejects a nonmatching conditional response without making another file', async () => {
    const create = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create })
    vi.mocked(authedFetch).mockResolvedValue(new Response(null, { status: 304, headers: { ETag: '"other"' } }))
    await expect(previewSampleEntrust({}, 'product', () => true, () => {}, cached as Extract<BusinessFormPrint, {type:'pdf'}>)).rejects.toThrow('缓存校验失败')
    expect(create).not.toHaveBeenCalled()
  })
})
