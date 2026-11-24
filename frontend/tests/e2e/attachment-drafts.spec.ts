import { test, expect, type Page } from '@playwright/test'

async function openForm(page: Page, kind: 'personnel' | 'external') {
  await page.goto(kind === 'personnel' ? '/#/quality/personnel/registration' : '/#/reports/changes/external')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const form = page.getByRole('dialog', { name: kind === 'personnel' ? '新增人员' : '新增申请', exact: true })
  if (kind === 'personnel') {
    for (const [label, value] of [['姓名', '后台上传测试'], ['人员编号', 'DRAFT-UPLOAD-1'], ['职称/资格', '工程师'], ['岗位/职务', '检测员']]) await form.getByLabel(label!, { exact: true }).fill(value!)
  } else {
    await form.getByRole('button', { name: '选择报告', exact: true }).click()
    const picker = page.getByRole('dialog', { name: '选择报告', exact: true })
    await picker.getByRole('checkbox', { name: '选择 SP2026090092', exact: true }).check()
    await picker.getByRole('button', { name: '移入', exact: true }).click()
    await picker.getByRole('button', { name: '确认', exact: true }).click()
    await form.getByLabel('更改原因').fill('测试附件后台上传')
  }
  async function openFiles() { await form.getByRole('button', { name: kind === 'personnel' ? '管理学历附件' : '附件', exact: true }).click() }
  async function closeFiles() {
    if (kind === 'personnel') await page.getByRole('dialog', { name: '学历附件', exact: true }).getByRole('button', { name: '完成', exact: true }).click()
    else await form.getByRole('button', { name: '附件', exact: true }).click()
  }
  return { form, openFiles, closeFiles }
}
const file = { name: '后台上传.txt', mimeType: 'text/plain', buffer: Buffer.from('staged attachment content') }

for (const kind of ['personnel', 'external'] as const) {
  test(`${kind}: closing the attachment panel keeps uploading; retry and form save only submit references`, async ({ page }) => {
    test.setTimeout(60000)
    const { form, openFiles, closeFiles } = await openForm(page, kind)
    let release!: () => void, requests = 0
    const gate = new Promise<void>(resolve => { release = resolve })
    await page.route('**/attachment-drafts/*/upload', async route => {
      expect(route.request().resourceType()).toBe('xhr'); requests++
      if (requests === 1) { await gate; await route.fulfill({ status: 422, json: { error: { code: 'VALIDATION', message: '测试上传失败' } } }) }
      else await route.continue()
    })
    await openFiles()
    await page.getByRole('dialog').locator('input[type=file]').setInputFiles(file)
    try {
      await expect.poll(() => requests).toBe(1)
      await closeFiles()
      await expect(form.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
      await expect(form.getByText('附件正在上传，请稍候', { exact: true })).toBeVisible()
      await expect(form.getByText(file.name, { exact: true }).first()).toBeVisible()
      expect(await page.evaluate(() => { const e = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented })).toBe(true)
    } finally { release() }
    await expect(form.getByText('请重试或移除失败的附件后保存', { exact: true })).toBeVisible()
    await openFiles()
    await page.getByRole('dialog').getByRole('button', { name: '重试', exact: true }).click()
    await expect(page.getByRole('dialog').getByRole('button', { name: file.name, exact: true })).toBeVisible()
    await closeFiles()
    const endpoint = kind === 'personnel' ? '**/quality/personnel' : '**/reports/external-changes'
    let savedPayload: Record<string, unknown> | undefined
    await page.route(endpoint, async route => {
      savedPayload = route.request().postDataJSON()
      expect(route.request().postData()).not.toContain(file.buffer.toString('base64'))
      expect(savedPayload?.attachmentDraftId).toBeTruthy()
      await route.continue()
    })
    await form.getByRole('button', { name: '保存', exact: true }).click()
    await expect(form).toBeHidden()
    expect(savedPayload).toBeTruthy(); expect(requests).toBe(2)
    expect(await page.evaluate(() => { const e = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented })).toBe(false)
  })

  test(`${kind}: abandoning the form confirms, cancels uploads and rejects late requests`, async ({ page }) => {
    const { form, openFiles, closeFiles } = await openForm(page, kind)
    let release!: () => void, requestData: unknown, uploadUrl = ''
    const gate = new Promise<void>(resolve => { release = resolve })
    await page.route('**/attachment-drafts/*/upload', async route => {
      requestData = route.request().postDataJSON(); uploadUrl = route.request().url()
      await gate
      await route.abort().catch(() => {})
    })
    await openFiles(); await page.getByRole('dialog').locator('input[type=file]').setInputFiles(file)
    try {
      await expect.poll(() => uploadUrl).not.toBe('')
      await closeFiles()
      await form.getByRole('button', { name: '取消', exact: true }).click()
      const leave = page.getByRole('dialog', { name: '放弃未保存内容', exact: true })
      await expect(leave).toContainText('取消上传')
      await leave.getByRole('button', { name: '继续编辑', exact: true }).click()
      await expect(form).toBeVisible()
      const url = page.url()
      await page.evaluate(() => { location.hash = '#/reports/query' })
      await expect(leave).toContainText('取消上传')
      await leave.press('Escape')
      await expect(page).toHaveURL(url)
      await expect(form).toBeVisible()
      const cleaned = page.waitForResponse(response => response.url().endsWith('/discard'))
      await form.getByRole('button', { name: '取消', exact: true }).click()
      await leave.getByRole('button', { name: '放弃更改', exact: true }).click()
      await expect(form).toBeHidden()
      expect((await cleaned).status()).toBe(200)
      const late = await page.request.post(uploadUrl, { headers: { 'X-Demo-Actor': 'admin' }, data: requestData })
      expect(late.status()).toBe(422)
      expect(await late.text()).toContain('失效')
    } finally { release() }
  })
}

for (const kind of ['personnel', 'external'] as const) test(`${kind}: removing a failed upload allows saving without a server draft`, async ({ page }) => {
  const { form, openFiles, closeFiles } = await openForm(page, kind)
  await page.route('**/attachment-drafts/*/upload', route => route.abort('failed'))
  await openFiles(); await page.getByRole('dialog').locator('input[type=file]').setInputFiles(file)
  await expect(page.getByRole('dialog').getByRole('button', { name: '移除', exact: true })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: '移除', exact: true }).click()
  await closeFiles()
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form).toBeHidden()
})
