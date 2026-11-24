import { expect, test } from '@playwright/test'

test('record dialogs keep their height and reuse visited tabs without clearing the table', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/#/testing/data-entry/demo-yp-76')
  let release!: () => void, requests = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/data-entry/records/query', async route => {
    requests++
    if (route.request().postDataJSON().kind === 'testing') await gate
    await route.continue()
  })
  await page.getByRole('button', { name: '查看修改记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '修改记录', exact: true })
  await expect(dialog).toBeFocused()
  await expect(dialog.getByText('暂无委托更改记录')).toBeVisible()
  const bounds = await dialog.locator('.modal-content').boundingBox()
  expect(bounds!.height).toBeGreaterThan(850)
  expect(bounds!.width).toBe(1140)
  try {
    await dialog.getByRole('tab', { name: '检测更改记录', exact: true }).click()
    await expect(dialog.getByRole('status')).toContainText('正在加载记录')
    await expect(dialog.getByRole('columnheader')).toHaveCount(7)
    await expect(dialog.getByRole('navigation', { name: '修改记录分页' })).toBeVisible()
    expect(await dialog.locator('.modal-content').boundingBox()).toEqual(bounds)
  } finally { release() }
  await expect(dialog.getByText('暂无检测更改记录')).toBeVisible()
  for (const name of ['委托更改记录', '检测更改记录']) {
    await dialog.getByRole('tab', { name, exact: true }).click()
    await expect(dialog.getByRole('status')).toHaveCount(0)
    expect(await dialog.locator('.modal-content').boundingBox()).toEqual(bounds)
  }
  expect(requests).toBe(2)
  await dialog.getByRole('button', { name: '返回', exact: true }).click()
  await expect(dialog).toBeHidden()
  await page.locator('#trial-conclusion').fill('重新打开时读取最新记录')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('试验信息已保存。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看修改记录', exact: true }).click()
  await dialog.getByRole('tab', { name: '检测更改记录', exact: true }).click()
  await expect(dialog.getByRole('cell', { name: '重新打开时读取最新记录', exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: '返回', exact: true }).click()
  await expect(dialog).toBeHidden()
  for (const name of ['附件管理', '查看问题记录']) {
    await page.getByRole('button', { name, exact: true }).click()
    const active = page.getByRole('dialog', { name: name === '附件管理' ? name : '问题记录', exact: true })
    await expect(active).toBeFocused()
    const size = (await active.locator('.modal-content').boundingBox())!
    if (name === '附件管理') expect(size.height).toBeLessThan(600)
    else { expect(size.height).toBeGreaterThan(850); expect(size.width).toBe(1140) }
    await active.getByRole('button', { name: '关闭弹窗', exact: true }).click()
    await expect(active).toBeHidden()
  }
})

test('footer dialogs preserve drafts and attachments do not conflict with subsequent saving', async ({ page }) => {
  await page.goto('/#/testing/data-entry/demo-yp-76')
  await page.locator('#trial-conclusion').fill('尚未保存的结论')
  await page.getByRole('button', { name: '附件管理', exact: true }).click()
  const attachments = page.getByRole('dialog', { name: '附件管理', exact: true })
  await expect(attachments).toBeVisible()
  await attachments.getByLabel('添加附件（最大 20 MB）').setInputFiles({ name: '普通附件.txt', mimeType: 'text/plain', buffer: Buffer.from('sample attachment') })
  await expect(attachments.getByRole('button', { name: '普通附件.txt', exact: true })).toBeVisible()
  await attachments.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(attachments).toBeHidden()
  await expect(page.locator('#trial-conclusion')).toHaveValue('尚未保存的结论')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('试验信息已保存。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看修改记录', exact: true }).click()
  const history = page.getByRole('dialog', { name: '修改记录', exact: true })
  await history.getByRole('tab', { name: '检测更改记录', exact: true }).click()
  await expect(history.getByRole('row').filter({ hasText: '尚未保存的结论' })).toContainText('保存试验信息')
  await expect(history.getByRole('columnheader')).toHaveText(['修改人员', '修改日期', '修改信息项', '改前值', '改后值', '修改类型', '第几次修改'])
  await history.getByRole('button', { name: '返回', exact: true }).click()
  await expect(history).toBeHidden()
  for (const name of ['委托信息', '样品信息', '原始记录', '试验信息']) {
    await page.getByRole('tab', { name, exact: true }).click()
    for (const button of ['附件管理', '查看修改记录', '查看问题记录', '保存']) await expect(page.getByRole('button', { name: button, exact: true })).toBeVisible()
  }
  await page.getByRole('button', { name: '查看问题记录', exact: true }).click()
  const issues = page.getByRole('dialog', { name: '问题记录', exact: true })
  await expect(issues.getByRole('columnheader')).toHaveText(['提交人账号', '提交人', '问题描述', '问题类型', '提交日期', '处理人账号', '处理人', '处理意见', '处理日期', '第几次问题'])
  await expect(issues.getByText('暂无问题记录')).toBeVisible()
  await expect(issues).toBeFocused()
  await page.keyboard.press('Escape'); await expect(issues).toBeHidden()
  await expect(page.getByRole('button', { name: '查看问题记录', exact: true })).toBeFocused()
})

test('view mode keeps all supporting entries, read-only attachments and responsive dialogs', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/testing/data-entry/demo-yp-76?mode=view')
  await page.getByRole('button', { name: '附件管理', exact: true }).click()
  const attachments = page.getByRole('dialog', { name: '附件管理', exact: true })
  await expect(attachments.getByText('当前样品仅支持查看和下载附件。')).toBeVisible()
  await expect(attachments.locator('input[type=file]')).toHaveCount(0)
  await attachments.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '查看修改记录', exact: true }).click()
  const history = page.getByRole('dialog', { name: '修改记录', exact: true })
  await expect(history.getByText('暂无委托更改记录')).toBeVisible()
  await expect(history).toBeFocused()
  await page.screenshot({ path: info.outputPath('mobile-history.png') })
  expect(await history.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  await history.getByRole('button', { name: '返回', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: '切换明暗模式', exact: true }).click()
  await page.getByRole('button', { name: '查看问题记录', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '问题记录', exact: true })).toBeFocused()
  await page.screenshot({ path: info.outputPath('dark-issues.png') })
})
