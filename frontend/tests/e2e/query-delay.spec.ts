import { test, expect } from '@playwright/test'

test.skip(Number(process.env.LIMS_MOCK_QUERY_DELAY_MS || 0) < 2000, '显式设置 LIMS_MOCK_QUERY_DELAY_MS=2000 以验证模拟延时。')

test('report print uses the shared query wait and keeps existing rows while refreshing', async ({ page }) => {
  const initial = page.waitForResponse(r => r.url().endsWith('/reports/lifecycle/print-query'))
  await page.goto('/#/reports/print')
  await expect(page.getByRole('region', { name: '报告打印列表区域' }).getByRole('status').filter({ hasText: '正在加载…' })).toBeVisible()
  await initial
  const table = page.getByRole('table', { name: '报告打印列表', exact: true })
  await expect(table).toContainText('SP2026090091')
  const queryButton = page.getByRole('form', { name: '报告打印条件', exact: true }).getByRole('button', { name: '查询', exact: true })
  const response = page.waitForResponse(r => r.url().endsWith('/reports/lifecycle/print-query'))
  const started = Date.now()
  await queryButton.click()
  await expect(queryButton).toBeDisabled()
  await expect(page.getByRole('region', { name: '报告打印列表区域' }).getByRole('status').filter({ hasText: '正在加载…' })).toBeVisible()
  await expect(page.locator('table[aria-label="报告打印列表"] tbody')).toHaveClass('opacity-25')
  await expect(page.locator('table[aria-label="报告打印列表"]')).toContainText('SP2026090091')
  expect((await response).status()).toBe(200)
  expect(Date.now() - started).toBeGreaterThanOrEqual(1900)
  await expect(queryButton).toBeEnabled()
  await expect(page.getByRole('region', { name: '报告打印列表区域' }).getByRole('status').filter({ hasText: '正在加载…' })).toHaveCount(0)
})

for (const { kind, label, code, rows } of [
  { kind: 'commissions', label: '委托', code: 'WT202609001', rows: 5 },
  { kind: 'samples', label: '样品', code: 'SP2026090001', rows: 10 },
]) {
  test(`${label} mock query really waits on the server while the advanced modal stays open`, async ({ page }) => {
    await page.goto('/#/commissions/query?scope=all')
    const table = page.getByRole('table', { name: `${label}列表`, exact: true })
    await expect(table.locator('tbody tr')).toHaveCount(rows)
    await page.getByRole('form', { name: `${label}查询`, exact: true }).getByRole('button', { name: '高级', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: `${label}高级查询`, exact: true })
    await dialog.getByLabel(`${label}编号`, { exact: true }).fill(code)
    const response = page.waitForResponse(r => r.url().endsWith(`/${kind}/query`) && r.request().method() === 'POST')
    const started = Date.now()
    await dialog.getByRole('button', { name: '查询', exact: true }).click()
    await expect(dialog.getByRole('button', { name: '查询中…', exact: true })).toBeDisabled()
    await expect(dialog).toBeVisible()
    expect((await response).status()).toBe(200)
    expect(Date.now() - started).toBeGreaterThanOrEqual(1900)
    await expect(dialog).toBeHidden()
    await expect(table).toContainText(code)
    await expect(table.locator('tbody tr')).toHaveCount(1)
  })
}
