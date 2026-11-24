import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { toolbarButton } from './helpers/toolbar'

for (const width of [1440, 390]) test(`calibration output requires selection and exports only checked records at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 950 })
  await page.goto('/#/quality/equipment/ledger')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增设备', exact: true })
  await dialog.getByRole('tab', { name: '检定记录', exact: true }).click()
  for (const organization of ['选中计量中心', '未选计量中心']) {
    await dialog.getByRole('button', { name: '新增', exact: true }).click()
    const form = page.getByRole('dialog', { name: '新增检定记录', exact: true })
    await form.getByLabel('检定单位', { exact: true }).fill(organization)
    await form.getByRole('button', { name: '确认', exact: true }).click()
  }
  await expect(await toolbarButton(page, '检定记录', '打印')).toBeDisabled()
  await expect(await toolbarButton(page, '检定记录', '导出')).toBeDisabled()
  const table = dialog.getByRole('table', { name: '检定记录列表', exact: true })
  await table.getByRole('checkbox', { name: /^选择检定记录 选中计量中心(?: |$)/ }).check()
  await expect(await toolbarButton(page, '检定记录', '打印')).toBeEnabled()
  const download = page.waitForEvent('download')
  await (await toolbarButton(page, '检定记录', '导出')).click()
  const file = await download
  expect(file.suggestedFilename()).toBe('检定记录.csv')
  const csv = await readFile((await file.path())!, 'utf8')
  expect(csv).toContain('选中计量中心')
  expect(csv).not.toContain('未选计量中心')
  expect(csv.trim().split('\r\n')).toHaveLength(2)
  await table.getByRole('checkbox', { name: /^选择检定记录 选中计量中心(?: |$)/ }).uncheck()
  await expect(await toolbarButton(page, '检定记录', '打印')).toBeDisabled()
  await expect(await toolbarButton(page, '检定记录', '导出')).toBeDisabled()
})
