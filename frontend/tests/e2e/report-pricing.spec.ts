import { expect, test } from '@playwright/test'

for (const [width, code] of [[1440, 'SP2026090092'], [390, 'SP2026090093']] as const) {
  test(`repricing edits totals and keeps fee details readonly at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/reports/distribution')
    const open = async () => {
      await page.getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
      await page.getByRole('menuitem', { name: '重新计价', exact: true }).click()
    }
    await open()
    const dialog = page.getByRole('dialog', { name: '重新计价', exact: true })
    const parameters = dialog.getByRole('table', { name: '检测参数收费项', exact: true })
    await expect(parameters).toBeVisible()
    await expect(parameters.locator('input')).toHaveCount(0)
    await expect(dialog.getByRole('table', { name: '其他收费项', exact: true })).toContainText('暂无收费项')
    await expect(dialog.getByLabel('实际价格', { exact: true })).toHaveValue('')
    await dialog.getByLabel('实际价格', { exact: true }).fill('77')
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    await expect(dialog).toBeHidden()
    await open()
    await expect(dialog.getByLabel('实际价格', { exact: true })).toHaveValue('')
    await dialog.getByLabel('标准价格', { exact: true }).fill('100')
    await dialog.getByLabel('折扣价格', { exact: true }).fill('80')
    await dialog.getByLabel('实际价格', { exact: true }).fill('75.50')
    await expect(dialog).toHaveCSS('opacity', '1')
    await page.screenshot({ path: info.outputPath(`pricing-dialog-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    await dialog.getByRole('button', { name: '确认', exact: true }).click()
    await expect(dialog).toBeHidden()
    await open()
    await expect(dialog.getByLabel('标准价格', { exact: true })).toHaveValue('100')
    await expect(dialog.getByLabel('折扣价格', { exact: true })).toHaveValue('80')
    await expect(dialog.getByLabel('实际价格', { exact: true })).toHaveValue('75.5')
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
  })
}
