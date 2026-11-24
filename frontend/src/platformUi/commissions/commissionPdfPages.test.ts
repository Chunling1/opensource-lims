import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { PDFDocument } from 'pdf-lib'
import { defineComponent, h, nextTick, ref } from 'vue'
import Pages from '@/components/CommissionPdfPages.vue'

let wrapper: VueWrapper | undefined
let bytes: Uint8Array<ArrayBuffer>
let clicked: { href: string; name: string }[]
let blobs: Blob[]
async function pdf(count: number) {
  const doc = await PDFDocument.create()
  for (let i = 1; i <= count; i++) doc.addPage([200 + i, 300])
  return new Uint8Array(await doc.save())
}
async function start(props: Record<string, unknown> = {}) {
  wrapper = mount(Pages, { props: { url: 'blob:preview', filename: '样品-WT.pdf', ...props } })
  await vi.waitFor(() => expect(wrapper!.findAll('input')).toHaveLength(4))
  return wrapper
}
beforeEach(async () => {
  bytes = await pdf(4); clicked = []; blobs = []
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => new Response(bytes)))
  vi.stubGlobal('URL', class extends URL {
    static createObjectURL(blob: Blob) { blobs.push(blob); return 'blob:selected' }
    static revokeObjectURL = vi.fn()
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    clicked.push({ href: this.href, name: this.download })
  })
})
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('commission PDF page selection', () => {
  it('selects all actual pages initially and downloads the unchanged preview directly', async () => {
    const w = await start()
    expect(w.findAll('input').every(input => (input.element as HTMLInputElement).checked)).toBe(true)
    await w.get('button').trigger('click'); await flushPromises()
    expect(clicked).toEqual([{ href: 'blob:preview', name: '样品-WT.pdf' }])
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(blobs).toHaveLength(0)
  })
  it('extracts only checked pages in original page order and labels the download', async () => {
    const w = await start()
    await w.findAll('input')[0].setValue(false)
    await w.findAll('input')[2].setValue(false)
    await w.get('button').trigger('click')
    await vi.waitFor(() => expect(clicked).toHaveLength(1))
    expect(clicked[0]).toEqual({ href: 'blob:selected', name: '样品-WT-第2-4页.pdf' })
    const array = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = reject; reader.readAsArrayBuffer(blobs[0])
    })
    const selected = await PDFDocument.load(new Uint8Array(array))
    expect(selected.getPages().map(page => page.getWidth())).toEqual([202, 204])
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('blocks an empty selection and resets choices when a new template has fewer pages', async () => {
    const w = await start()
    for (const input of w.findAll('input')) await input.setValue(false)
    expect((w.get('button').element as HTMLButtonElement).disabled).toBe(true)
    expect(w.text()).toContain('请至少选择一页')
    vi.mocked(fetch).mockResolvedValueOnce(new Response(await pdf(3)))
    await w.setProps({ url: 'blob:engineering' })
    await vi.waitFor(() => expect(w.findAll('input')).toHaveLength(3))
    expect(w.findAll('input').every(input => (input.element as HTMLInputElement).checked)).toBe(true)
  })
  it('uses actual overflow pages and ignores a late response for a closed preview', async () => {
    const w = await start()
    let resolve!: (response: Response) => void
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(done => { resolve = done }))
    await w.setProps({ url: 'blob:late' })
    await w.setProps({ url: '' })
    resolve(new Response(await pdf(7))); await flushPromises()
    expect(w.findAll('input')).toHaveLength(0)
    vi.mocked(fetch).mockResolvedValueOnce(new Response(await pdf(7)))
    await w.setProps({ url: 'blob:overflow' })
    await vi.waitFor(() => expect(w.findAll('input')).toHaveLength(7))
  })
  it('does not export when draft revalidation fails or replaces the preview', async () => {
    const beforeDownload = vi.fn().mockResolvedValue(false)
    const w = await start({ beforeDownload })
    await w.get('button').trigger('click'); await flushPromises()
    expect(clicked).toHaveLength(0)
    beforeDownload.mockImplementationOnce(async () => { await w.setProps({ url: 'blob:updated' }); return true })
    await w.get('button').trigger('click'); await flushPromises()
    expect(clicked).toHaveLength(0)
  })
  it('downloads after the parent temporarily disables controls for draft revalidation', async () => {
    const Parent = defineComponent({ setup() {
      const busy = ref(false)
      const validate = async () => { busy.value = true; await nextTick(); busy.value = false; return true }
      return () => h(Pages, { url: 'blob:preview', filename: '委托单.pdf', disabled: busy.value, beforeDownload: validate })
    } })
    wrapper = mount(Parent)
    await vi.waitFor(() => expect(wrapper!.findAll('input')).toHaveLength(4))
    await wrapper.get('button').trigger('click'); await flushPromises()
    expect(clicked).toHaveLength(1)
  })
  it('reports a PDF read failure and allows a retry without exporting a stale file', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('PDF 读取失败'))
    wrapper = mount(Pages, { props: { url: 'blob:failed', filename: '委托单.pdf' } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('PDF 读取失败')
    expect((wrapper.get('button').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.findAll('button')[1].trigger('click')
    await vi.waitFor(() => expect(wrapper!.findAll('input')).toHaveLength(4))
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })
  it('keeps selected pages and prevents repeated clicks from downloading twice during validation', async () => {
    let confirm!: (valid: boolean) => void
    const beforeDownload = vi.fn(() => new Promise<boolean>(resolve => { confirm = resolve }))
    const w = await start({ beforeDownload })
    await w.findAll('input')[0].setValue(false)
    await w.findAll('input')[2].setValue(false)
    await w.get('button').trigger('click')
    await w.get('button').trigger('click')
    expect(beforeDownload).toHaveBeenCalledTimes(1)
    confirm(true)
    await vi.waitFor(() => expect(clicked).toHaveLength(1))
    expect(clicked[0].name).toBe('样品-WT-第2-4页.pdf')
    expect(w.findAll('input').map(input => (input.element as HTMLInputElement).checked)).toEqual([false, true, false, true])
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(blobs).toHaveLength(1)
  })
})
