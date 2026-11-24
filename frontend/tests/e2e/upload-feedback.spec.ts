import { expect, test, type Page } from '@playwright/test'
import { openReportFiles } from './helpers/reportFiles'
import { originalPdf } from '../helpers/originalPdf'
let pdfBytes: Buffer
test.beforeAll(async () => { pdfBytes = await originalPdf() })
const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: pdfBytes })
async function unloadBlocked(page: Page) {
  return page.evaluate(() => { const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented })
}
for (const kind of ['original', 'appendix'] as const) test(`${kind} upload shows FilePond progress and prevents leaving throughout the batch`, async ({ page }) => {
  await page.goto(`/#/testing/data-entry/demo-yp-76?tab=${kind === 'original' ? 'original' : 'report'}`)
  if (kind === 'original') await page.getByRole('button', { name: '上传记录', exact: true }).click()
  else await openReportFiles(page)
  const input = kind === 'original' ? page.getByLabel('上传 PDF 原始记录', { exact: true }) : page.getByLabel('添加附加文件', { exact: true })
  await expect(input).toBeEnabled()
  let release!: () => void, requests = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  const path = kind === 'original' ? '**/original-records/upload' : '**/data-entry/upload'
  await page.route(path, async route => { expect(route.request().resourceType()).toBe('xhr'); requests++; if (requests === 2) await gate; await route.continue() })
  try {
    await input.setInputFiles([pdf('第一份.pdf'), pdf('等待上传.pdf')])
    await expect.poll(() => requests).toBe(2)
    const status = page.locator('.filepond--item').filter({ hasText: '等待上传.pdf' })
    await expect(status.locator('[data-upload-state-icon]')).toBeVisible()
    await expect(status.locator('.filepond--file-status-main')).toContainText(/正在上传|正在保存/)
    await expect(page.getByRole('button', { name: '第一份.pdf', exact: true })).toBeVisible()
    if (kind === 'original') await expect(page.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
    else await expect(page.getByRole('button', { name: '保存', exact: true })).toHaveCount(0)
    for (const button of await page.getByRole('button', { name: '返回', exact: true }).all()) await expect(button).toBeDisabled()
    await expect(page.locator('.filepond--root[data-disabled]').first()).toBeAttached()
    expect(await unloadBlocked(page)).toBe(true)
    const url = page.url()
    await page.evaluate(() => { location.hash = '#/testing/data-entry' })
    await expect(page).toHaveURL(url)
    await expect(page.getByText('文件正在上传，请等待完成后再离开。', { exact: true })).toBeVisible()
    expect(requests).toBe(2)
  } finally { release() }
  await expect(page.getByRole('button', { name: '等待上传.pdf', exact: true })).toBeVisible()
  await expect(page.getByText('第 2 / 2 个', { exact: true })).toHaveCount(0)
  if (kind === 'original') await expect(page.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
  else await expect(page.getByRole('button', { name: '保存', exact: true })).toHaveCount(0)
  expect(await unloadBlocked(page)).toBe(false)
})

test('batch failure keeps successful files and names failures, with upload controls restored', async ({ page }) => {
  await page.goto('/#/testing/data-entry/demo-yp-76?tab=original')
  await page.getByRole('button', { name: '上传记录', exact: true }).click()
  const input = page.getByLabel('上传 PDF 原始记录', { exact: true })
  await expect(input).toBeEnabled()
  await page.route('**/original-records/upload', route => route.request().postDataJSON().file.name === '失败.pdf' ? route.fulfill({ status: 422, json: { error: { code: 'VALIDATION', message: '文件校验失败' } } }) : route.continue())
  await input.setInputFiles([pdf('成功.pdf'), pdf('失败.pdf'), pdf('继续成功.pdf')])
  await expect(page.locator('[data-upload-retry]')).toHaveAccessibleName(/文件校验失败.*点击重试/)
  await expect(page.getByRole('button', { name: '成功.pdf', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '继续成功.pdf', exact: true })).toBeVisible()
  await expect(input).toBeEnabled()
  expect(await unloadBlocked(page)).toBe(false)
})

test('trademark reading displays a filename and protects the page before the form is dirty', async ({ page }) => {
  await page.addInitScript(() => {
    const read = FileReader.prototype.readAsDataURL
    FileReader.prototype.readAsDataURL = function(file: Blob) {
      if ((file as File).name === '等待读取.png') window.addEventListener('release-test-file', () => read.call(this, file), { once: true })
      else read.call(this, file)
    }
  })
  await page.goto('/#/commissions/registration/samples/new?commissionId=demo-wt-1')
  const form = page.getByRole('form', { name: '样品表单' })
  await form.getByLabel('上传商标图片', { exact: true }).setInputFiles({ name: '等待读取.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0n8AAAAASUVORK5CYII=', 'base64') })
  const status = page.getByRole('status').filter({ hasText: '正在读取：等待读取.png' })
  await expect(status).toBeVisible()
  await expect(form.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
  expect(await unloadBlocked(page)).toBe(true)
  const url = page.url()
  await page.evaluate(() => { location.hash = '#/commissions/registration' })
  await expect(page).toHaveURL(url)
  await expect(status).toContainText('请完成后再离开页面')
  await page.evaluate(() => window.dispatchEvent(new Event('release-test-file')))
  await expect(form.getByAltText('商标图片', { exact: true })).toBeVisible()
  await expect(status).toHaveCount(0)
  await expect(form.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
})

