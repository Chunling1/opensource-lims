import { test, expect, type Page } from '@playwright/test'
const area = (page: Page, label: string) => page.getByRole('region', { name: `${label}区域`, exact: true })
const table = (page: Page, label: string) => page.getByRole('table', { name: `${label}列表`, exact: true })
async function openForm(page: Page) {
  await page.goto('/#/quality/personnel/certificates')
  await table(page, '人员').getByRole('cell', { name: 'DEMO-001', exact: true }).click()
  await page.getByRole('button', { name: '新增上岗证', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新增上岗证', exact: true })
  await form.getByLabel('上岗证类别', { exact: true }).fill('测试类别')
  await form.getByRole('textbox', { name: '上岗证号', exact: true }).fill('BACKGROUND-CERT')
  const files = page.getByRole('dialog', { name: '上岗证附件', exact: true })
  const openFiles = () => form.getByRole('button', { name: '管理上岗证附件', exact: true }).click()
  const closeFiles = () => files.getByRole('button', { name: '完成', exact: true }).click()
  return { form, files, openFiles, closeFiles }
}
const file = { name: 'background.txt', mimeType: 'text/plain', buffer: Buffer.from('certificate pending upload') }
test('certificate upload continues with panel closed, retries, and saves only server references', async ({ page }) => {
  const { form, files, openFiles, closeFiles } = await openForm(page)
  let release!: () => void, requests = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/attachment-drafts/*/upload', async route => {
    expect(route.request().resourceType()).toBe('xhr'); requests++
    if (requests === 1) { await gate; await route.fulfill({ status: 422, json: { error: { code: 'VALIDATION', message: '测试上传失败' } } }) }
    else await route.continue()
  })
  await openFiles(); await files.locator('input[type=file]').setInputFiles(file)
  try {
    await expect.poll(() => requests).toBe(1)
    await closeFiles()
    await expect(form.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
    await expect(form.getByText('附件正在上传，请稍候', { exact: true })).toBeVisible()
  } finally { release() }
  await expect(form.getByText('请重试或移除失败的附件后保存', { exact: true })).toBeVisible()
  await openFiles(); await files.getByRole('button', { name: '重试', exact: true }).click()
  await expect(files.getByRole('button', { name: file.name, exact: true })).toBeVisible()
  await closeFiles()
  let saved = false
  await page.route('**/quality/certificates/certificates', async route => {
    const body = route.request().postDataJSON()
    expect(body.attachmentDraftId).toBeTruthy()
    expect(body.files).toMatchObject([{ name: file.name, dataUrl: '' }])
    expect(route.request().postData()).not.toContain(file.buffer.toString('base64'))
    saved = true; await route.continue()
  })
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form).toBeHidden(); expect(saved).toBe(true)
  await page.reload(); await page.getByRole('tab', { name: '全部上岗证', exact: true }).click()
  await expect(table(page, '上岗证')).toContainText('BACKGROUND-CERT')
})
test('abandoning certificate form cancels uploads and rejects late requests', async ({ page }) => {
  const { form, files, openFiles, closeFiles } = await openForm(page)
  let release!: () => void, url = '', data: unknown
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/attachment-drafts/*/upload', async route => { url = route.request().url(); data = route.request().postDataJSON(); await gate; await route.abort().catch(() => {}) })
  await openFiles(); await files.locator('input[type=file]').setInputFiles(file)
  try {
    await expect.poll(() => url).not.toBe('')
    await closeFiles()
    await form.getByRole('button', { name: '取消', exact: true }).click()
    const leave = page.getByRole('dialog', { name: '放弃未保存内容', exact: true })
    await expect(leave).toContainText('取消上传')
    await leave.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(form).toBeVisible()
    const cleaned = page.waitForResponse(r => r.url().endsWith('/discard'))
    await form.getByRole('button', { name: '取消', exact: true }).click()
    await leave.getByRole('button', { name: '放弃更改', exact: true }).click()
    await expect(form).toBeHidden(); expect((await cleaned).status()).toBe(200)
    expect((await page.request.post(url, { headers: { 'X-Demo-Actor': 'admin' }, data })).status()).toBe(422)
  } finally { release() }
})
test('remote queries show loading, ignore superseded results and retry failures', async ({ page }) => {
  await page.goto('/#/quality/personnel/certificates')
  await table(page, '人员').getByRole('cell', { name: 'DEMO-001', exact: true }).click()
  await expect(table(page, '上岗证')).toContainText('DEMO-C001-1')
  let release!: () => void, waiting = false
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/quality/certificates/certificates/query', async route => {
    if (route.request().postDataJSON().parentIds[0] === 'demo-person-2') { waiting = true; await gate; await route.continue().catch(() => {}) }
    else await route.continue()
  })
  await table(page, '人员').getByRole('cell', { name: 'DEMO-002', exact: true }).click()
  try {
    await expect.poll(() => waiting).toBe(true)
    await expect(area(page, '上岗证').getByRole('status')).toContainText('正在加载')
    await expect(table(page, '上岗证').getByRole('checkbox').first()).toBeDisabled()
    await table(page, '人员').getByRole('cell', { name: 'DEMO-003', exact: true }).click()
    await expect(table(page, '上岗证')).toContainText('DEMO-C003-1')
  } finally { release() }
  await page.unroute('**/quality/certificates/certificates/query')
  let fail = true
  await page.route('**/quality/certificates/certificates/query', route => fail ? route.fulfill({ status: 503, json: { error: { code: 'SERVER_ERROR', message: '测试服务暂不可用' } } }) : route.continue())
  await area(page, '上岗证').getByRole('button', { name: '查询', exact: true }).click()
  await expect(area(page, '上岗证').getByRole('button', { name: '重试', exact: true })).toBeVisible()
  fail = false; await area(page, '上岗证').getByRole('button', { name: '重试', exact: true }).click()
  await expect(table(page, '上岗证')).toContainText('DEMO-C003-1')
  await expect(table(page, '上岗证')).not.toContainText('DEMO-C002')
  await expect(page.getByText('当前使用独立示例数据。', { exact: false })).toHaveCount(0)
})
