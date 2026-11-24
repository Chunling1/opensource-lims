import { test, expect, type Page } from '@playwright/test'

const root = '/commissions/registration'
async function themeColor(page: Page, className: string, property = 'background-color') {
  return page.evaluate(({ className, property }) => {
    const probe = document.createElement('span')
    probe.className = className
    document.body.append(probe)
    const color = getComputedStyle(probe).getPropertyValue(property)
    probe.remove()
    return color
  }, { className, property })
}
async function open(page: Page, code = 'WT202609001') {
  await page.getByRole('table', { name: '委托列表', exact: true }).getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
  await page.getByRole('menuitem', { name: '附件管理', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '附件', exact: true })
  await expect(dialog).toBeVisible()
  return dialog
}

for (const width of [1440, 390]) test(`commission list attachments upload, download, delete and preserve query at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 })
  await page.goto(`/#${root}?current=demo-wt-1&cSort=code&cDirection=asc&scope=all`)
  const url = page.url(), dialog = await open(page)
  const rowElement = await page.getByRole('table', { name: '委托列表', exact: true }).getByRole('row').filter({ hasText: 'WT202609001' }).elementHandle()
  const reloads: string[] = []
  page.on('request', request => {
    if (/\/api\/registration\/(commissions\/query|commissions\/[^/]+\/summary|samples\/query)$/.test(request.url())) reloads.push(request.url())
  })
  const upload = dialog.getByLabel('添加附件', { exact: false })
  await dialog.getByRole('button', { name: '关闭', exact: true }).click({ trial: true })
  for (const height of [650, 900, 1200]) {
    await page.setViewportSize({ width, height })
    await expect.poll(() => dialog.locator('[data-attachment-placeholders] li:not([data-placeholder-probe])').count()).toBeGreaterThan(0)
    await expect(dialog.getByText('暂无附件', { exact: true })).toBeVisible()
    await expect.poll(() => dialog.locator('.modal-body').evaluate(body => body.scrollHeight - body.clientHeight)).toBeLessThanOrEqual(1)
    // The remaining space is smaller than another complete placeholder row.
    await expect.poll(() => dialog.locator('[data-attachment-placeholders]').evaluate(list => {
      const body = list.closest('.modal-body')!, row = list.querySelector('li')!
      const remaining = body.getBoundingClientRect().bottom - parseFloat(getComputedStyle(body).paddingBottom) - list.getBoundingClientRect().bottom
      return remaining < row.getBoundingClientRect().height + parseFloat(getComputedStyle(list).rowGap)
    })).toBe(true)
    await dialog.screenshot({ path: testInfo.outputPath(`attachment-placeholders-${width}-${height}.png`) })
  }
  const initialModal = (await dialog.locator('.modal-content').boundingBox())!
  expect(initialModal.height).toBeLessThan(650)
  async function expectStableModal() {
    const current = (await dialog.locator('.modal-content').boundingBox())!
    for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(current[key] - initialModal[key])).toBeLessThan(1)
  }
  const idleArea = dialog.locator('.filepond--drop-label')
  const idleBounds = (await idleArea.boundingBox())!
  // Read both positions in the same frame; the containing modal also animates on opening.
  const listPosition = () => dialog.locator('.filepond--root').evaluate(root => root.closest('section')!.querySelector('h6')!.getBoundingClientRect().top - root.getBoundingClientRect().top)
  const listOffset = await listPosition()
  await expect(idleArea).toHaveCSS('transition-property', 'opacity')
  for (const name of ['附件甲.txt', '附件乙.txt']) {
    const file = { name, mimeType: 'text/plain', buffer: Buffer.from(name) }
    if (name === '附件甲.txt') {
      await dialog.evaluate(element => {
        const frames: { opacity: number; overflow: number; x: number; y: number; width: number; height: number }[] = []
        let handle = 0
        const sample = () => {
          const row = element.querySelector('[data-attachment-file]'), body = element.querySelector('.modal-body')!
          if (row) {
            const { x, y, width, height } = element.querySelector('.modal-content')!.getBoundingClientRect()
            frames.push({ opacity: Number(getComputedStyle(row).opacity), overflow: body.scrollHeight - body.clientHeight, x, y, width, height })
          }
          handle = requestAnimationFrame(sample)
        }
        ;(element as HTMLElement & { stopAttachmentFrames: () => typeof frames }).stopAttachmentFrames = () => { cancelAnimationFrame(handle); return frames }
        sample()
      })
      const chooser = page.waitForEvent('filechooser')
      const action = dialog.getByRole('button', { name: '上传附件', exact: true })
      if (width === 1440) await action.press('Enter')
      else await action.click()
      await (await chooser).setFiles(file)
    } else await upload.setInputFiles(file)
    await expect(dialog.getByRole('button', { name, exact: true })).toBeVisible()
    await expect(dialog.getByText('暂无附件', { exact: true })).toHaveCount(0)
    if (name === '附件甲.txt') {
      await expect.poll(() => dialog.locator('[data-attachment-placeholders] li:not([data-placeholder-probe])').count()).toBeGreaterThan(0)
      await expect.poll(() => dialog.locator('.modal-body').evaluate(body => body.scrollHeight - body.clientHeight)).toBeLessThanOrEqual(1)
      const realBounds = (await dialog.getByRole('button', { name, exact: true }).locator('xpath=ancestor::li[1]').boundingBox())!
      const placeholderBounds = (await dialog.locator('[data-attachment-placeholders] li:not([data-placeholder-probe])').first().boundingBox())!
      expect(Math.abs(placeholderBounds.height - realBounds.height)).toBeLessThan(1)
      expect(Math.abs(placeholderBounds.width - realBounds.width)).toBeLessThan(1)
    }
    await expectStableModal()
    const complete = dialog.locator('.filepond--item[data-filepond-item-state="processing-complete"]')
    await expect(complete.locator('.filepond--file-status-main')).toHaveText('上传成功')
    await expect(dialog.locator('[data-upload-state-icon]')).toHaveClass(/ri-checkbox-circle-line/)
    await expect(complete).toHaveCSS('background-color', await themeColor(page, 'bg-success-subtle'))
    await expect(complete.locator('.filepond--file-status')).toHaveCSS('color', await themeColor(page, 'text-success-emphasis', 'color'))
    await expect(complete.locator('.filepond--file-info')).toHaveCSS('color', await themeColor(page, 'text-body', 'color'))
    await expect(dialog.locator('.filepond--root')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    await expect(dialog.locator('.filepond--root')).toHaveCSS('border-top-width', '0px')
    const itemBounds = (await complete.boundingBox())!
    expect(Math.abs(itemBounds.width - idleBounds.width)).toBeLessThan(1)
    expect(Math.abs(itemBounds.height - idleBounds.height)).toBeLessThan(1)
    expect(Math.abs(await listPosition() - listOffset)).toBeLessThan(1)
    await expect(idleArea).toHaveAttribute('inert', '')
    await expect(dialog.locator('.filepond--list-scroller')).toHaveCSS('transition-property', 'opacity')
    if (name === '附件甲.txt') {
      await dialog.screenshot({ path: testInfo.outputPath(`upload-success-${width}.png`) })
      await page.waitForTimeout(1000)
      await expect(complete).toBeVisible()
      const frames = await dialog.evaluate(element => (element as HTMLElement & { stopAttachmentFrames: () => { opacity: number; overflow: number; x: number; y: number; width: number; height: number }[] }).stopAttachmentFrames())
      expect(frames.some(frame => frame.opacity > 0 && frame.opacity < 1)).toBe(true)
      for (const frame of frames) {
        expect(frame.overflow).toBeLessThanOrEqual(1)
        for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(frame[key] - initialModal[key])).toBeLessThan(1)
      }
      // The next selection must work while the previous success state is still visible.
    }
  }
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
  await expect(idleArea).toHaveCSS('border-top-style', 'dashed')
  await expect(idleArea).toHaveCSS('opacity', '1')
  await expect(idleArea).not.toHaveAttribute('inert', '')
  await dialog.screenshot({ path: testInfo.outputPath(`upload-idle-${width}.png`) })
  const download = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '附件甲.txt', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('附件甲.txt')
  await dialog.getByRole('button', { name: '删除附件 附件甲.txt', exact: true }).click()
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await dialog.screenshot({ path: testInfo.outputPath(`attachment-confirm-${width}-${theme}.png`) })
  }
  await dialog.getByRole('button', { name: '取消删除', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '附件甲.txt', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '删除附件 附件甲.txt', exact: true }).click()
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '附件甲.txt', exact: true })).toHaveCount(0)
  await expectStableModal()
  await expect(dialog.locator('.modal-body')).toHaveCSS('overflow-y', 'auto')
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await expect(upload).toBeInViewport()
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`attachments-${width}-${theme}.png`) })
  }
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(page.url()).toBe(url)
  expect(reloads).toEqual([])
  expect(await rowElement!.evaluate(element => element.isConnected)).toBe(true)
  await expect(page.getByRole('checkbox', { name: '选择委托 WT202609001', exact: true })).toBeChecked()
  await open(page)
  await expect(dialog.getByRole('button', { name: '附件乙.txt', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click({ trial: true })
  await dialog.press('Escape')
  await expect(dialog).toBeHidden()
  await page.goto(`/#${root}/commissions/demo-wt-1/edit`)
  await expect(page.getByRole('form', { name: '委托表单' })).toBeVisible()
  await expect(page.getByRole('region', { name: '委托附件' })).toHaveCount(0)
  await page.goto(`/#${root}/commissions/demo-wt-1`)
  await expect(page.getByRole('heading', { name: '委托详情', exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '委托附件' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '附件乙.txt', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('添加附件', { exact: false })).toHaveCount(0)
  await page.goto(`/#${root}/commissions/new`)
  await expect(page.getByRole('form', { name: '委托表单' })).toBeVisible()
  await expect(page.getByRole('region', { name: '委托附件' })).toHaveCount(0)
})

test('attachment writes block repeated actions and completed commissions are download-only', async ({ page }, info) => {
  await page.goto(`/#${root}?cSort=code&cDirection=asc`)
  const dialog = await open(page)
  // Hold the first progress report so FilePond remains in its real "busy processing" state.
  await dialog.locator('.filepond--root').evaluate(root => {
    type Process = (...args: unknown[]) => unknown
    const host = window as unknown as { FilePond: { find(element: Element): { server: { process: Process }; setOptions(options: unknown): void } }; releaseUploadProgress: () => void }
    const pond = host.FilePond.find(root)
    const server = pond.server
    pond.setOptions({ server: { ...server, process: (...args: unknown[]) => {
      const progress = args[5] as Process
      let latest: unknown[] | undefined
      let released = false
      args[5] = (...values: unknown[]) => { latest = values; if (released) progress(...values) }
      host.releaseUploadProgress = () => { released = true; if (latest) progress(...latest); progress(true, 1, 2) }
      return server.process(...args)
    } } })
  })
  let release!: () => void, requests = 0
  let positions: number[] = []
  const textPositions = () => dialog.locator('.filepond--item').evaluate(item => {
    const top = item.getBoundingClientRect().top
    return ['.filepond--file-info-main', '.filepond--file-status-main'].map(selector => item.querySelector(selector)!.getBoundingClientRect().top - top)
  })
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/commissions/demo-wt-1/attachments', async route => { requests++; await gate; await route.continue() })
  try {
    await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '已保存.txt', mimeType: 'text/plain', buffer: Buffer.from('contents') })
    await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('status').filter({ hasText: '正在上传：已保存.txt' })).toBeVisible()
    expect(await page.evaluate(() => { const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented })).toBe(true)
    await expect(dialog.getByRole('region', { name: '委托附件' })).toHaveAttribute('inert', '')
    await expect(dialog.locator('.filepond--item[data-filepond-item-state="busy processing"]')).toHaveCount(1)
    await expect(dialog.locator('[data-upload-state-icon]')).toBeVisible()
    await dialog.screenshot({ path: info.outputPath('upload-busy-processing.png') })
    await page.evaluate(() => (window as unknown as { releaseUploadProgress: () => void }).releaseUploadProgress())
    await expect(dialog.locator('.filepond--item[data-filepond-item-state="processing"]')).toHaveCount(1)
    await expect(dialog.locator('[data-upload-state-icon]')).toHaveClass(/ri-file-upload-line/)
    await expect(dialog.locator('.filepond--item')).toHaveCSS('background-color', await themeColor(page, 'bg-primary-subtle'))
    positions = await textPositions()
    await dialog.press('Escape'); await expect(dialog).toBeVisible()
    expect(requests).toBe(1)
  } finally { release() }
  await expect(dialog.getByRole('button', { name: '已保存.txt', exact: true })).toBeVisible()
  await expect(dialog.locator('.filepond--file-status-main')).toHaveText('上传成功')
  const completedPositions = await textPositions()
  completedPositions.forEach((position, index) => expect(Math.abs(position - positions[index]!)).toBeLessThan(1))
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  await page.getByRole('button', { name: 'WT202609001 更多操作', exact: true }).click()
  await page.getByRole('menuitem', { name: '完成', exact: true }).click()
  await page.getByRole('dialog', { name: '完成', exact: true }).getByRole('button', { name: '确认', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '完成', exact: true })).toBeHidden()
  await open(page)
  await expect(dialog.getByText('当前委托仅支持查看和下载附件。', { exact: true })).toBeVisible()
  await expect(dialog.getByLabel('添加附件', { exact: false })).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: /删除附件/ })).toHaveCount(0)
  const download = page.waitForEvent('download')
  await dialog.getByRole('button', { name: '已保存.txt', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('已保存.txt')
})

test('FilePond failure retry restores the upload area without automatically sending again', async ({ page }) => {
  await page.goto(`/#${root}?cSort=code&cDirection=asc`)
  const dialog = await open(page)
  await page.route('**/commissions/demo-wt-1/attachments', route => route.fulfill({ status: 500, json: { error: { code: 'INTERNAL', message: '附件处理暂时失败，请重试。' } } }), { times: 1 })
  await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '重试.txt', mimeType: 'text/plain', buffer: Buffer.from('retry') })
  await expect(dialog.locator('.filepond--file-status-main')).toHaveText('附件处理暂时失败，点击重试')
  await expect(dialog.getByRole('button', { name: '重试.txt', exact: true })).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: '移除待上传文件', exact: true })).toBeHidden()
  await dialog.getByRole('button', { name: '附件处理暂时失败，点击重试', exact: true }).press('Enter')
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: '上传附件', exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '重试.txt', exact: true })).toHaveCount(0)
  await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '重试.txt', mimeType: 'text/plain', buffer: Buffer.from('retry') })
  await expect(dialog.getByRole('button', { name: '重试.txt', exact: true })).toHaveCount(1)
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
})

test('FilePond rejects oversized files without sending or retrying them', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto(`/#${root}?cSort=code&cDirection=asc`)
  const dialog = await open(page)
  let writes = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/commissions/demo-wt-1/attachments')) writes++ })
  await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '超限.rar', mimeType: 'application/octet-stream', buffer: Buffer.alloc(21 * 1024 * 1024) })
  await expect(dialog.locator('.filepond--file-status-main')).toHaveText('文件超过 20 MB，点击重试')
  await expect(dialog.getByRole('button', { name: '重试上传', exact: true })).toBeHidden()
  expect(writes).toBe(0)
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await expect(dialog.locator('.filepond--item')).toHaveCSS('background-color', await themeColor(page, 'bg-danger-subtle'))
    await expect(dialog.locator('.filepond--item .filepond--file-status')).toHaveCSS('color', await themeColor(page, 'text-danger-emphasis', 'color'))
    await expect(dialog.locator('.filepond--item .filepond--file-info')).toHaveCSS('color', await themeColor(page, 'text-body', 'color'))
    await expect(dialog.locator('.filepond--root')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
    await expect(dialog.locator('.filepond--root')).toHaveCSS('border-top-width', '0px')
    await expect(dialog.locator('.filepond--item .filepond--panel-bottom')).toHaveCSS('box-shadow', 'none')
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await dialog.screenshot({ path: info.outputPath(`upload-limit-${theme}.png`) })
  }
  await expect(dialog.getByRole('button', { name: '移除待上传文件', exact: true })).toBeHidden()
  await expect(dialog.locator('[data-upload-state-icon]')).toHaveClass(/ri-error-warning-line/)
  const retryArea = dialog.getByRole('button', { name: '文件超过 20 MB，点击重试', exact: true })
  const areaBounds = (await retryArea.boundingBox())!, fileBounds = (await dialog.locator('.filepond--item').boundingBox())!
  for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(areaBounds[key] - fileBounds[key])).toBeLessThan(1)
  // Even the blank left edge of the failure bar resets the upload area.
  await retryArea.click({ position: { x: 5, y: 5 } })
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
  await expect(dialog.locator('.filepond--drop-label')).toHaveCSS('opacity', '1')
  expect(writes).toBe(0)
  const chooser = page.waitForEvent('filechooser')
  await dialog.getByRole('button', { name: '上传附件', exact: true }).click()
  await (await chooser).setFiles({ name: '正常.txt', mimeType: 'text/plain', buffer: Buffer.from('ok') })
  await expect(dialog.getByRole('button', { name: '正常.txt', exact: true })).toBeVisible()
  expect(writes).toBe(1)
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
  await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '再次超限.rar', mimeType: 'application/octet-stream', buffer: Buffer.alloc(21 * 1024 * 1024) })
  await expect(dialog.locator('.filepond--file-status-main')).toHaveText('文件超过 20 MB，点击重试')
  await dialog.getByRole('button', { name: '文件超过 20 MB，点击重试', exact: true }).press('Space')
  await expect(dialog.locator('.filepond--item')).toHaveCount(0)
  await expect(dialog.locator('.filepond--drop-label')).toHaveCSS('opacity', '1')
  expect(writes).toBe(1)
})

test('attachment failures retain files and require refresh after a version conflict', async ({ page }) => {
  await page.goto(`/#${root}?cSort=code&cDirection=asc`)
  await page.route('**/commissions/demo-wt-1/attachments', route => route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '附件暂不可用' } } }), { times: 1 })
  const dialog = await open(page)
  await expect(dialog.getByText('附件暂不可用', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '重试', exact: true }).click()
  const upload = dialog.getByLabel('添加附件', { exact: false })
  await upload.setInputFiles({ name: '保留.txt', mimeType: 'text/plain', buffer: Buffer.from('retain') })
  await expect(dialog.getByRole('button', { name: '保留.txt', exact: true })).toBeVisible()
  await page.route('**/attachments/*', route => route.abort(), { times: 1 })
  await dialog.getByRole('button', { name: '删除附件 保留.txt', exact: true }).click()
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '刷新附件', exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '保留.txt', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '刷新附件', exact: true }).click()
  await page.route('**/commissions/demo-wt-1/attachments', route => route.fulfill({ status: 409, json: { error: { code: 'VERSION_CONFLICT', message: '记录已更新，请刷新后重试。' } } }), { times: 1 })
  await upload.setInputFiles({ name: '冲突.txt', mimeType: 'text/plain', buffer: Buffer.from('conflict') })
  await expect(dialog.getByText('记录已更新，请刷新后重试。', { exact: true })).toBeVisible()
  await expect(upload).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: '冲突.txt', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: '刷新附件', exact: true }).click()
  await expect(upload).toBeVisible()
  await expect(dialog.getByRole('button', { name: '保留.txt', exact: true })).toBeVisible()
})

