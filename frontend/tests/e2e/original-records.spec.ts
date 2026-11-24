import { expect, test, type Page } from '@playwright/test'
import { originalPdf, PDFDocument } from '../helpers/originalPdf'
let pdfBytes: Buffer
test.beforeAll(async () => { pdfBytes = await originalPdf() })
const pdf = (name = '原始记录.pdf') => ({ name, mimeType: 'application/pdf', buffer: pdfBytes })
const manager = (page: Page) => page.getByRole('dialog', { name: '上传原始记录', exact: true })
async function openManager(page: Page) { await page.getByRole('button', { name: '上传记录', exact: true }).click(); await expect(manager(page)).toBeVisible() }
async function importFiles(page: Page) { await expect(manager(page).getByLabel('上传 PDF 原始记录', { exact: true })).toBeEnabled() }
test.beforeEach(async ({ page }) => { page.on('pageerror', error => { throw error }); await page.goto('/#/testing/data-entry/demo-yp-76?tab=original') })

test('preview is the default workspace; manager persists order, names and deletion with readonly viewing', async ({ page }, info) => {
  await expect(page.getByRole('region', { name: '原始记录预览', exact: true })).toBeVisible()
  await expect(page.getByText('暂无原始记录，请上传记录', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '打印', exact: true })).toBeDisabled()
  await expect(manager(page).locator('[data-attachment-file]')).toBeHidden()
  await openManager(page); await importFiles(page)
  const dialog = manager(page)
  await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles([pdf(), pdf('第二份.pdf')])
  await expect(dialog.locator('[data-attachment-file]')).toHaveCount(2)
  await expect(dialog.getByRole('button', { name: '上移 原始记录.pdf', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '下移 第二份.pdf', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '上移 第二份.pdf', exact: true }).click()
  await expect(dialog.locator('[data-attachment-file]').nth(0)).toContainText('第二份.pdf')
  await dialog.getByRole('button', { name: '重命名 第二份.pdf', exact: true }).click()
  await dialog.getByLabel('记录名称', { exact: true }).fill('第二份核对记录')
  await dialog.getByRole('button', { name: '保存名称', exact: true }).click()
  await expect(dialog.locator('[data-attachment-file]').nth(0)).toContainText('第二份核对记录')
  const download = page.waitForEvent('download')
  await dialog.locator('[data-attachment-file]').nth(0).getByRole('button', { name: '下载原始记录 第二份.pdf', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('第二份.pdf')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 950 })
    await page.evaluate(theme => document.documentElement.setAttribute('data-bs-theme', theme), width === 390 ? 'dark' : 'light')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await dialog.screenshot({ path: info.outputPath('original-manager-' + width + '.png') })
  }
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeAttached()
  const mergedUrl = await page.locator('iframe[title="原始记录预览"]').getAttribute('src')
  await dialog.getByRole('button', { name: '第二份核对记录', exact: true }).click()
  const fileDialog = page.getByRole('dialog', { name: '查看原始记录', exact: true })
  await expect(fileDialog.locator('iframe[title="单份原始记录预览"]')).toBeVisible()
  await expect(page.locator('iframe[title="原始记录预览"]')).toHaveAttribute('src', mergedUrl!)
  await expect(page.locator('.modal-backdrop')).toHaveCount(1)
  await fileDialog.getByRole('button', { name: '返回文件列表', exact: true }).click()
  await expect(dialog.getByRole('checkbox', { name: '选择 第二份核对记录', exact: true })).not.toBeChecked()
  await expect(dialog.getByRole('button', { name: '删除', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: '返回', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  await page.reload()
  await expect(page.locator('#original-preview-record')).toHaveCount(0)
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  await page.screenshot({ path: info.outputPath('original-preview-mobile.png'), fullPage: true })
  await openManager(page)
  await dialog.getByRole('checkbox', { name: '选择 第二份核对记录', exact: true }).check()
  await dialog.getByRole('button', { name: '删除附件 第二份核对记录', exact: true }).click()
  await page.getByRole('dialog', { name: '删除原始记录', exact: true }).getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog.locator('[data-attachment-file]')).toHaveCount(2)
  await dialog.getByRole('button', { name: '删除附件 第二份核对记录', exact: true }).click()
  await page.getByRole('dialog', { name: '删除原始记录', exact: true }).getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.locator('[data-attachment-file]')).toHaveCount(1)
  await dialog.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  await page.goto('/#/testing/data-entry/demo-yp-76?tab=original&mode=view')
  await expect(page.getByRole('tab', { name: '试验信息', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: '原始记录', exact: true }).click()
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  await expect(page.getByRole('button', { name: '上传记录', exact: true })).toHaveCount(0)
  await expect(page.locator('input[type=file]')).toHaveCount(0)
})

test('partial failures and uncertain uploads preserve successes without duplicate submission', async ({ page }) => {
  await openManager(page); await importFiles(page)
  const dialog = manager(page)
  await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles([pdf(), pdf('不支持.png')])
  await expect(dialog.locator('[data-upload-retry]')).toHaveAccessibleName(/仅支持 PDF 文件.*点击重试/)
  await dialog.locator('[data-upload-retry]').click()
  await expect(dialog.locator('[data-attachment-file]')).toHaveCount(1)
  let submitted = 0
  await page.route('**/original-records/upload', async route => { submitted++; await route.fetch(); await route.abort('failed') })
  await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles(pdf('结果不确定.pdf'))
  await expect(dialog.getByRole('button', { name: '刷新原始记录', exact: true })).toBeEnabled()
  await expect(dialog.locator('.filepond--root')).toHaveAttribute('data-disabled', 'disabled')
  await dialog.getByRole('button', { name: '刷新原始记录', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '结果不确定.pdf', exact: true })).toBeVisible()
  expect(submitted).toBe(1)
})

test('ELN PDF import uses the same preview, supports explicit updates and prevents duplicate links', async ({ page }) => {
  await openManager(page); await importFiles(page)
  await manager(page).getByRole('button', { name: '关联 ELN', exact: true }).click()
  const eln = page.getByRole('dialog', { name: '关联 ELN', exact: true })
  await expect(eln.getByLabel('样品编号', { exact: true })).toHaveValue('SP2026090076')
  await expect(eln.getByRole('checkbox')).toHaveCount(3)
  await eln.getByRole('checkbox').first().check()
  await eln.getByRole('button', { name: '确认关联', exact: true }).click()
  await expect(manager(page)).toBeVisible()
  const row = manager(page).locator('[data-attachment-file]').nth(0)
  await expect(row).toContainText('外部 ELN')
  await expect(row.getByRole('button', { name: /^重命名 / })).toHaveCount(0)
  await row.getByRole('button', { name: '食品留样 76 · ELN 原始记录 1', exact: true }).click()
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  await expect(page.locator('iframe[title="单份原始记录预览"]')).toBeVisible()
  await expect(page.getByText(/ELN 导入版本：1/)).toBeVisible()
  await expect(page.getByRole('region', { name: '外部原始记录预览', exact: true })).toHaveCount(0)
  await page.getByRole('dialog', { name: '查看原始记录', exact: true }).getByRole('button', { name: '返回文件列表', exact: true }).click()
  await importFiles(page)
  await manager(page).getByRole('button', { name: '关联 ELN', exact: true }).click()
  await expect(eln.getByRole('checkbox').first()).toBeDisabled()
  await expect(page.locator('.modal-backdrop')).toHaveCount(1)
  await eln.getByRole('button', { name: '返回文件列表', exact: true }).click()
  const updated = page.waitForResponse(response => response.url().endsWith('/original-records/update-eln'))
  await manager(page).getByRole('button', { name: '更新', exact: true }).click()
  await page.getByRole('dialog', { name: '更新外部原始记录', exact: true }).getByRole('button', { name: '确认更新', exact: true }).click()
  expect((await updated).ok()).toBe(true)
  await expect(manager(page).getByText(/版本 1/)).toBeVisible()
  await row.getByRole('button', { name: /^删除附件 / }).click()
  await expect(page.getByRole('dialog', { name: '删除原始记录', exact: true })).toContainText('不会删除 ELN')
  await page.getByRole('dialog', { name: '删除原始记录', exact: true }).getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(manager(page).locator('[data-attachment-file]')).toHaveCount(0)
  await expect(manager(page).getByText('暂无原始记录', { exact: true })).toBeVisible()
})

async function previewWidths(page: Page) {
  const bytes = await page.locator('iframe[title="原始记录预览"]').evaluate(async (node: HTMLIFrameElement) => Array.from(new Uint8Array(await (await fetch(node.src)).arrayBuffer())))
  return (await PDFDocument.load(new Uint8Array(bytes))).getPages().map(row => row.getWidth())
}
test('uploaded and ELN PDFs share an ordered combined preview, download and reload result', async ({ page }, info) => {
  await openManager(page)
  await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles({ name: '本地记录.pdf', mimeType: 'application/pdf', buffer: await originalPdf([300, 350]) })
  await expect(manager(page).getByRole('button', { name: '本地记录.pdf', exact: true })).toBeVisible()
  await importFiles(page)
  await manager(page).getByRole('button', { name: '关联 ELN', exact: true }).click()
  const eln = page.getByRole('dialog', { name: '关联 ELN', exact: true })
  await eln.getByRole('checkbox').first().check(); await eln.getByRole('button', { name: '确认关联', exact: true }).click()
  await expect(manager(page).locator('[data-attachment-file]')).toHaveCount(2)
  await manager(page).locator('[data-attachment-file]').nth(1).getByRole('checkbox').check()
  await manager(page).locator('[data-attachment-file]').nth(1).getByRole('button', { name: /^上移 / }).click()
  await expect(manager(page).locator('[data-attachment-file]').nth(0)).toContainText('外部 ELN')
  await manager(page).getByRole('button', { name: '返回', exact: true }).click()
  await expect(manager(page)).toBeHidden()
  await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  expect(await previewWidths(page)).toEqual([595.28, 300, 350])
  await expect(page.locator('#original-preview-record')).toHaveCount(0)
  const download = page.waitForEvent('download')
  await page.getByRole('region', { name: '原始记录预览', exact: true }).getByRole('button', { name: '下载', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('SP2026090076-原始记录.pdf')
  await page.reload(); await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
  expect(await previewWidths(page)).toEqual([595.28, 300, 350])
  await page.screenshot({ path: info.outputPath('combined-original-preview.png'), fullPage: true })
})

test('preview updates show progress, ignore late results and retry without omitting files', async ({ page }) => {
  let release!: () => void, firstReady = false, fail = false, requests = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/original-records/preview?*', async route => {
    requests++
    if (fail) { await route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '合并服务暂不可用' } } }); return }
    const response = await route.fetch()
    if (requests === 1) { firstReady = true; await gate }
    await route.fulfill({ response })
  })
  try {
    await openManager(page)
    await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles(pdf('第一份.pdf'))
    await expect.poll(() => firstReady).toBe(true)
    await expect(page.getByText('正在更新预览…', { exact: true })).toBeVisible()
    await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles(pdf('第二份.pdf'))
    await expect(manager(page).locator('[data-attachment-file]')).toHaveCount(2)
    await manager(page).getByRole('button', { name: '返回', exact: true }).click()
    await expect(manager(page)).toBeHidden()
    await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
    expect(await previewWidths(page)).toHaveLength(2)
    const current = await page.locator('iframe[title="原始记录预览"]').getAttribute('src')
    release()
    await expect(page.locator('iframe[title="原始记录预览"]')).toHaveAttribute('src', current!)
    fail = true
    await openManager(page)
    await page.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles(pdf('第三份.pdf'))
    await expect(manager(page).locator('[data-attachment-file]')).toHaveCount(3)
    await manager(page).getByRole('button', { name: '返回', exact: true }).click()
    await expect(manager(page)).toBeHidden()
    await expect(page.getByText('合并服务暂不可用', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '打印', exact: true })).toBeDisabled()
    await expect(page.locator('iframe[title="原始记录预览"]')).toHaveCount(0)
    fail = false
    await page.getByRole('button', { name: '重试预览', exact: true }).click()
    await expect(page.locator('iframe[title="原始记录预览"]')).toBeVisible()
    expect(await previewWidths(page)).toHaveLength(3)
  } finally { release() }
})


for (const width of [1440, 390]) test(`unified original attachment layout stays stable at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 })
  await openManager(page)
  const dialog = manager(page), content = dialog.locator('.modal-content'), body = dialog.locator('.modal-body')
  const ghosts = dialog.locator('[data-attachment-placeholders] > li:not([data-placeholder-probe])')
  const expectFilledSpace = async () => {
    await expect(ghosts.first()).toBeVisible()
    await expect.poll(() => body.evaluate(node => node.scrollHeight - node.clientHeight)).toBeLessThanOrEqual(1)
    await expect.poll(() => ghosts.last().evaluate(row => {
      const body = row.closest('.modal-body')!
      const remaining = body.getBoundingClientRect().bottom - parseFloat(getComputedStyle(body).paddingBottom) - row.getBoundingClientRect().bottom
      return remaining >= -1 && remaining < row.getBoundingClientRect().height + 8
    })).toBe(true)
  }
  const counts: number[] = []
  for (const height of [650, 900, 1200, 1000]) {
    await page.setViewportSize({ width, height })
    await expectFilledSpace()
    counts.push(await ghosts.count())
  }
  expect(counts[2]).toBeGreaterThan(counts[0]!)
  await expect(dialog.getByText('暂无原始记录', { exact: true })).toBeVisible()
  await expect.poll(() => body.evaluate(node => node.scrollHeight - node.clientHeight)).toBeLessThanOrEqual(1)
  await dialog.evaluate(async node => { await Promise.all(node.getAnimations({ subtree: true }).map(animation => animation.finished.catch(() => {}))) })
  await dialog.screenshot({ path: info.outputPath(`original-empty-${width}.png`) })
  const bounds = await content.boundingBox()
  const rowHeight = await ghosts.first().evaluate(node => node.getBoundingClientRect().height)
  await dialog.getByLabel('上传 PDF 原始记录', { exact: true }).setInputFiles(pdf('布局测试.pdf'))
  const file = dialog.locator('[data-attachment-file]')
  await expect(file).toHaveCount(1)
  await expect(dialog.getByRole('button', { name: '布局测试.pdf', exact: true })).toBeVisible()
  const after = await content.boundingBox()
  expect(Math.abs(after!.y - bounds!.y)).toBeLessThan(1)
  expect(Math.abs(after!.height - bounds!.height)).toBeLessThan(1)
  expect(Math.abs(await file.evaluate(node => node.getBoundingClientRect().height) - rowHeight)).toBeLessThan(3)
  await expect(ghosts.first()).toBeVisible()
  await expect.poll(() => body.evaluate(node => node.scrollHeight - node.clientHeight)).toBeLessThanOrEqual(1)
  await expect(dialog.getByText('暂无原始记录', { exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  // Sample the success-to-chooser handoff, including FilePond's delayed DOM removal.
  const transition = await dialog.locator('.filepond--root').evaluate(async root => {
    const samples: { height: number; coverage: number }[] = []
    const opacity = (element: Element | null) => {
      let result = element ? 1 : 0
      for (let node = element; node && node !== root; node = node.parentElement) {
        const style = getComputedStyle(node)
        if (style.display === 'none' || style.visibility === 'hidden') return 0
        result *= Number(style.opacity)
      }
      return result
    }
    const start = performance.now()
    await new Promise<void>(resolve => {
      const frame = () => {
        const chooser = root.querySelector('.filepond--drop-label'), item = root.querySelector('.filepond--item')
        samples.push({ height: root.parentElement!.getBoundingClientRect().height, coverage: Math.max(opacity(chooser), opacity(item)) })
        if ((!item && opacity(chooser) >= 0.99) || performance.now() - start > 5000) resolve()
        else requestAnimationFrame(frame)
      }
      requestAnimationFrame(frame)
    })
    return samples
  })
  expect(Math.min(...transition.map(frame => frame.height))).toBeGreaterThanOrEqual(71)
  expect(Math.min(...transition.map(frame => frame.coverage))).toBeGreaterThan(0.1)
  await expect(dialog.locator('.filepond--item')).toHaveCount(0, { timeout: 10000 })
  await expect.poll(() => body.evaluate(node => node.scrollHeight - node.clientHeight)).toBeLessThanOrEqual(1)
  await expectFilledSpace()
  await dialog.screenshot({ path: info.outputPath(`original-files-${width}.png`) })
})

for (const height of [760, 900, 1000]) test(`original placeholders fill on first open without resizing at ${height}`, async ({ page }) => {
  await page.setViewportSize({ width: 1280, height })
  await openManager(page)
  const dialog = manager(page)
  const metrics = () => dialog.locator('[data-attachment-placeholders]').evaluate(list => {
    const body = list.closest('.modal-body')!, row = list.querySelector('li')!, last = list.lastElementChild!
    const available = body.getBoundingClientRect().bottom - parseFloat(getComputedStyle(body).paddingBottom) - list.getBoundingClientRect().top
    const rowHeight = row.getBoundingClientRect().height, gap = parseFloat(getComputedStyle(list).rowGap)
    return { count: list.children.length, expected: Math.floor((available + gap - 1) / (rowHeight + gap)), remaining: body.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom, rowHeight }
  })
  await expect.poll(async () => { const m = await metrics(); return m.count === m.expected }, { message: 'Initial placeholders should fill available space without requiring a resize' }).toBe(true)
})
