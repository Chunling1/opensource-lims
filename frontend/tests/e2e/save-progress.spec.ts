import { expect, test } from '@playwright/test'

for (const kind of ['personnel', 'external'] as const) test(`${kind} save reports transfer progress, waits for confirmation and preserves attachments on failure`, async ({ page }) => {
  await page.setViewportSize({ width: kind === 'personnel' ? 390 : 1440, height: 1000 })
  const endpoint = kind === 'personnel' ? '/quality/personnel' : '/reports/external-changes'
  // Control upload events independently of the eventual real HTTP response.
  await page.addInitScript(endpoint => {
    const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send
    const targets = new WeakSet<XMLHttpRequest>()
    XMLHttpRequest.prototype.open = function(method: string, url: string | URL) {
      if (method === 'POST' && String(url).endsWith(endpoint)) targets.add(this)
      open.call(this, method, url, true)
    }
    XMLHttpRequest.prototype.send = function(body) {
      if (!targets.has(this)) { send.call(this, body); return }
      const progress = (event: Event) => this.upload.dispatchEvent(new ProgressEvent('progress', { lengthComputable: true, loaded: (event as CustomEvent<number>).detail, total: 1000 }))
      window.addEventListener('test-save-progress', progress)
      window.addEventListener('test-send-save', () => {
        window.removeEventListener('test-save-progress', progress)
        send.call(this, body)
      }, { once: true })
      window.dispatchEvent(new CustomEvent('test-save-progress', { detail: 250 }))
    }
  }, endpoint)
  await page.goto(kind === 'personnel' ? '/#/quality/personnel/registration' : '/#/reports/changes/external')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const modal = page.getByRole('dialog', { name: kind === 'personnel' ? '新增人员' : '新增申请', exact: true })
  const file = { name: '保存进度证明.txt', mimeType: 'text/plain', buffer: Buffer.from('save progress attachment') }
  if (kind === 'personnel') {
    await modal.getByLabel('姓名', { exact: true }).fill('保存进度测试人员')
    await modal.getByLabel('人员编号', { exact: true }).fill('SAVE-PROGRESS-1')
    await modal.getByLabel('职称/资格', { exact: true }).fill('工程师')
    await modal.getByLabel('岗位/职务', { exact: true }).fill('检测员')
    await modal.getByRole('button', { name: '管理学历附件', exact: true }).click()
    const attachments = page.getByRole('dialog', { name: '学历附件', exact: true })
    await attachments.locator('input[type=file]').setInputFiles(file)
    await expect(attachments.getByRole('button', { name: file.name, exact: true })).toBeVisible()
    await attachments.getByRole('button', { name: '完成', exact: true }).click()
  } else {
    await modal.getByRole('button', { name: '选择报告', exact: true }).click()
    const picker = page.getByRole('dialog', { name: '选择报告', exact: true })
    await picker.getByRole('checkbox', { name: '选择 SP2026090092', exact: true }).check()
    await picker.getByRole('button', { name: '移入', exact: true }).click()
    await picker.getByRole('button', { name: '确认', exact: true }).click()
    await modal.getByLabel('更改原因').fill('保存进度测试')
    await modal.getByRole('button', { name: '附件', exact: true }).click()
    await modal.locator('input[type=file]').setInputFiles(file)
    await expect(modal.getByRole('button', { name: file.name, exact: true })).toBeVisible()
  }
  let requests = 0
  await page.route('**' + endpoint, async route => {
    expect(route.request().resourceType()).toBe('xhr')
    expect(route.request().postData()).toContain(file.name)
    requests++
    if (requests === 1) await route.fulfill({ status: 422, json: { error: { code: 'VALIDATION', message: '测试保存失败，请重试' } } })
    else await route.continue()
  })
  const progress = modal.getByRole('status').filter({ hasText: /正在传输|正在保存|正在准备/ })
  for (let attempt = 0; attempt < 2; attempt++) {
    await modal.getByRole('button', { name: kind === 'external' && attempt === 1 ? '提交' : '保存', exact: true }).click()
    await expect(progress).toHaveText('正在传输 25%')
    await expect(modal.getByRole('button', { name: kind === 'personnel' ? '取消' : '返回', exact: true })).toBeDisabled()
    expect(await modal.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('test-save-progress', { detail: 999 })))
    await expect(progress).toHaveText('正在传输 99%')
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('test-save-progress', { detail: 1000 })))
    await expect(progress).toHaveText('传输完成，正在保存…')
    await expect(modal).toBeVisible()
    await page.evaluate(() => window.dispatchEvent(new Event('test-send-save')))
    if (attempt === 0) {
      await expect(modal.getByRole('alert').filter({ hasText: '测试保存失败，请重试' })).toBeVisible()
      await expect(progress).toHaveCount(0)
      await expect(modal.getByLabel(kind === 'personnel' ? '姓名' : '更改原因', { exact: true })).toHaveValue(kind === 'personnel' ? '保存进度测试人员' : '保存进度测试')
      await expect(modal.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
    } else await expect(modal).toBeHidden()
  }
  expect(requests).toBe(2)
})
