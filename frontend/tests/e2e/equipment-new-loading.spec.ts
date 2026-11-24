import { test, expect } from '@playwright/test'

test('new equipment waits for options and recovers from loading failure', async ({ page }) => {
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/quality/equipment/ledger/options', async route => {
    await pending
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL', message: '选项暂时不可用' } }) })
  }, { times: 1 })
  await page.goto('/#/quality/equipment/ledger')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增设备', exact: true })
  try {
    await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
    await expect(dialog.getByLabel('档案号', { exact: true })).toHaveCount(0)
    await expect(dialog.getByRole('tab', { name: '基本信息', exact: true })).toBeVisible()
    await expect(dialog.locator('.btn-close')).toBeEnabled()
    await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
  } finally { release() }
  await expect(dialog.getByRole('alert')).toContainText('选项暂时不可用')
  await expect(dialog.getByLabel('档案号', { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: /重试/ }).click()
  await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
  await expect(dialog.getByLabel('所属部门', { exact: true })).toBeEnabled()
  await expect(dialog.getByLabel('所属部门', { exact: true })).not.toHaveValue('')
  await dialog.getByLabel('档案号', { exact: true }).fill('READY-AFTER-OPTIONS')
  await dialog.getByLabel('仪器设备名称', { exact: true }).fill('加载完成后的设备')
  await dialog.getByRole('tab', { name: '检定记录', exact: true }).click()
  await dialog.getByRole('button', { name: '新增', exact: true }).click()
  const record = page.getByRole('dialog', { name: '新增检定记录', exact: true })
  await expect(record.getByLabel('设备编号', { exact: true })).toHaveValue('READY-AFTER-OPTIONS')
})
