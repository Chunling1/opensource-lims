import { test, expect, type Page } from '@playwright/test'
const root = '/commissions/registration'
async function open(page: Page, code = 'SP2026090001') {
  await page.getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
  const menu = page.getByRole('menu', { name: `${code} 更多操作`, exact: true })
  await expect(menu.getByRole('menuitem').last()).toHaveText('附件管理')
  await menu.getByRole('menuitem', { name: '附件管理', exact: true }).click()
  return page.getByRole('dialog', { name: '附件', exact: true })
}
for (const width of [1440, 390]) test(`sample attachments support CRUD and preserve lists at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 })
  await page.goto(`/#${root}?current=demo-wt-1&sSort=code&sDirection=asc`)
  await page.getByRole('checkbox', { name: '选择样品 SP2026090001', exact: true }).check()
  const url = page.url(), dialog = await open(page)
  const upload = dialog.getByLabel('添加附件', { exact: false })
  const queries: string[] = []
  page.on('request', request => { if (/\/api\/registration\/(commissions\/query|samples\/query|commissions\/[^/]+\/summary)$/.test(request.url())) queries.push(request.url()) })
  const file = { name: '样品资料.txt', mimeType: 'text/plain', buffer: Buffer.from('样品资料') }
  await upload.setInputFiles(file)
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await dialog.getByRole('button', { name: file.name, exact: true }).click()
  expect((await download).suggestedFilename()).toBe(file.name)
  await dialog.getByRole('button', { name: `删除附件 ${file.name}`, exact: true }).click()
  await page.getByRole('dialog', { name: '删除附件', exact: true }).getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: `删除附件 ${file.name}`, exact: true }).click()
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toHaveCount(0)
  await upload.setInputFiles({ ...file, name: '保留资料.txt' })
  await expect(dialog.getByRole('button', { name: '保留资料.txt', exact: true })).toBeVisible()
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await expect(upload).toBeInViewport()
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`sample-attachments-${width}-${theme}.png`) })
  }
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(page.url()).toBe(url)
  await expect(page.getByRole('checkbox', { name: '选择样品 SP2026090001', exact: true })).toBeChecked()
  await open(page, 'WT202609001')
  await expect(dialog.getByRole('region', { name: '委托附件', exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '保留资料.txt', exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  await open(page)
  await expect(dialog.getByRole('button', { name: '保留资料.txt', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click({ trial: true })
  await dialog.press('Escape'); await expect(dialog).toBeHidden()
  expect(queries).toEqual([])
  for (const suffix of ['new?commissionId=demo-wt-1', 'demo-yp-1/edit', 'demo-yp-1']) {
    await page.goto(`/#${root}/samples/${suffix}`)
    await expect(page.getByRole('form', { name: '样品表单' })).toBeVisible()
    await expect(page.getByRole('region', { name: '样品附件' })).toHaveCount(0)
    await expect(page.getByLabel('添加附件', { exact: false })).toHaveCount(0)
  }
})
test('sample attachment failures and conflicts retain files', async ({ page }) => {
  await page.goto(`/#${root}?current=demo-wt-1&sSort=code&sDirection=asc`)
  const dialog = await open(page), upload = dialog.getByLabel('添加附件', { exact: false })
  const file = { name: '检查.txt', mimeType: 'text/plain', buffer: Buffer.from('check') }
  await page.route('**/samples/demo-yp-1/attachments', route => route.abort(), { times: 1 })
  await upload.setInputFiles(file)
  await expect(dialog.getByRole('button', { name: '刷新附件', exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: '刷新附件', exact: true }).click()
  await upload.setInputFiles(file)
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
  await page.route('**/samples/demo-yp-1/attachments/*', route => route.fulfill({ status: 409, json: { error: { code: 'VERSION_CONFLICT', message: '记录已更新，请刷新后重试。' } } }), { times: 1 })
  await dialog.getByRole('button', { name: `删除附件 ${file.name}`, exact: true }).click()
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByText('记录已更新，请刷新后重试。', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
})
test('registration completion allows attachment writes and void application makes attachments read-only', async ({ page }) => {
  await page.goto(`/#${root}?current=demo-wt-1&sSort=code&sDirection=asc`)
  const dialog = await open(page)
  await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '历史资料.txt', mimeType: 'text/plain', buffer: Buffer.from('history') })
  await expect(dialog.getByRole('button', { name: '历史资料.txt', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
  for (const action of ['完成', '作废']) {
    await page.getByRole('button', { name: 'SP2026090001 更多操作', exact: true }).click()
    await page.getByRole('menuitem', { name: action, exact: true }).click()
    const confirm = page.getByRole('dialog', { name: action === '作废' ? '作废申请' : action, exact: true })
    if (action === '作废') await confirm.getByLabel('申请作废原因').fill('重复登记')
    await confirm.getByRole('button', { name: '确认', exact: true }).click()
    await expect(confirm).toBeHidden()
    await open(page)
    if (action === '完成') {
      await dialog.getByLabel('添加附件', { exact: false }).setInputFiles({ name: '登记后资料.txt', mimeType: 'text/plain', buffer: Buffer.from('after registration') })
      await expect(dialog.getByRole('button', { name: '登记后资料.txt', exact: true })).toBeVisible()
      await dialog.getByRole('button', { name: '删除附件 登记后资料.txt', exact: true }).click()
      await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
      await expect(dialog.getByRole('button', { name: '登记后资料.txt', exact: true })).toHaveCount(0)
    } else {
      await expect(dialog.getByText('当前样品仅支持查看和下载附件。', { exact: true })).toBeVisible()
      await expect(dialog.getByLabel('添加附件', { exact: false })).toHaveCount(0)
      await expect(dialog.getByRole('button', { name: /删除附件/ })).toHaveCount(0)
    }
    const download = page.waitForEvent('download')
    await dialog.getByRole('button', { name: '历史资料.txt', exact: true }).click()
    expect((await download).suggestedFilename()).toBe('历史资料.txt')
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).toBeHidden()
  }
})

test('sample attachment controls use backend permissions and default to read-only when absent', async ({ page }) => {
  await page.goto(`/#${root}?current=demo-wt-1&sSort=code&sDirection=asc`)
  for (const canManageAttachments of [true, false, undefined]) {
    await page.route('**/api/registration/samples/demo-yp-1/attachments', async route => {
      const response = await route.fetch()
      await route.fulfill({ response, json: { ...await response.json(), canManageAttachments, attachments: [{ id: 'fixture', name: 'history.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }] } })
    }, { times: 1 })
    const dialog = await open(page)
    await expect(dialog.getByRole('button', { name: 'history.txt', exact: true })).toBeVisible()
    if (!canManageAttachments) {
      await expect(dialog.getByLabel('添加附件', { exact: false })).toHaveCount(0)
      await expect(dialog.getByRole('button', { name: '删除附件 history.txt', exact: true })).toHaveCount(0)
      await expect(dialog.getByText('当前样品仅支持查看和下载附件。', { exact: true })).toBeVisible()
    } else {
      await expect(dialog.getByLabel('添加附件', { exact: false })).toBeVisible()
      await expect(dialog.getByRole('button', { name: '删除附件 history.txt', exact: true })).toBeVisible()
      await expect(dialog.getByText('当前样品仅支持查看和下载附件。', { exact: true })).toHaveCount(0)
    }
    await dialog.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(dialog).toBeHidden()
  }
})
