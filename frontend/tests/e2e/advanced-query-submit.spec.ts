import { test, expect } from '@playwright/test'

for (const { kind, label, code, size } of [
  { kind: 'commissions', label: '委托', code: 'WT202609001', size: 5 },
  { kind: 'samples', label: '样品', code: 'SP2026090001', size: 10 },
]) {
  test(`${label} advanced query waits for success, retains failed drafts and never submits duplicate requests`, async ({ page }) => {
    await page.goto('/#/commissions/query?scope=all')
    const form = page.getByRole('form', { name: `${label}查询`, exact: true })
    const table = page.getByRole('table', { name: `${label}列表`, exact: true })
    const dialog = page.getByRole('dialog', { name: `${label}高级查询`, exact: true })
    await expect(table.locator('tbody tr')).toHaveCount(size)
    const originalUrl = page.url()
    let release!: () => void, calls = 0
    const gate = new Promise<void>(resolve => { release = resolve })
    await page.route(`**/api/registration/${kind}/query`, async route => {
      calls++
      if (calls === 1) {
        await gate
        await route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '模拟高级查询失败，请重试' } } })
      } else await route.continue()
    })
    await form.getByRole('button', { name: '高级', exact: true }).click()
    await dialog.getByLabel(`${label}编号`, { exact: true }).fill(code)
    await dialog.getByRole('button', { name: '查询', exact: true }).click()
    await expect(dialog.getByRole('button', { name: '查询中…', exact: true })).toBeDisabled()
    await expect(dialog.getByLabel(`${label}编号`, { exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '关闭弹窗', exact: true })).toBeDisabled()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeVisible()
    await dialog.getByRole('form').evaluate(form => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
    expect(calls).toBe(1)
    expect(page.url()).toBe(originalUrl)
    await expect(table.locator('tbody tr')).toHaveCount(size)
    release()
    await expect(dialog.getByRole('alert')).toContainText('模拟高级查询失败，请重试')
    await expect(dialog.getByLabel(`${label}编号`, { exact: true })).toHaveValue(code)
    await expect(dialog.getByLabel(`${label}编号`, { exact: true })).toBeEditable()
    await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeEnabled()
    expect(page.url()).toBe(originalUrl)
    await dialog.getByRole('button', { name: '重试', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(table.locator('tbody tr')).toHaveCount(1)
    await expect(table).toContainText(code)
    expect(calls).toBe(2)
    await form.getByRole('button', { name: '高级', exact: true }).click()
    await dialog.getByRole('button', { name: '查询', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(calls).toBe(3)
    await expect(table).toContainText(code)
  })
}

test('network failure keeps the modal draft; leaving during a query ignores the late response', async ({ page }) => {
  await page.goto('/#/commissions/query?scope=all')
  const form = page.getByRole('form', { name: '样品查询', exact: true })
  const table = page.getByRole('table', { name: '样品列表', exact: true })
  const dialog = page.getByRole('dialog', { name: '样品高级查询', exact: true })
  await expect(table.locator('tbody tr')).toHaveCount(10)
  let calls = 0, release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/registration/samples/query', async route => {
    calls++
    if (calls === 1) { await route.abort('failed'); return }
    if (calls === 2) { await gate; await route.fulfill({ json: { items: [], total: 0, page: 1, pageSize: 10 } }); return }
    await route.continue()
  })
  await form.getByRole('button', { name: '高级', exact: true }).click()
  await dialog.getByLabel('样品编号', { exact: true }).fill('SP2026090001')
  await dialog.getByRole('button', { name: '查询', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('无法连接登记接口')
  await expect(dialog.getByLabel('样品编号', { exact: true })).toHaveValue('SP2026090001')
  await dialog.getByRole('button', { name: '重试', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '查询中…', exact: true })).toBeDisabled()
  await page.goto('/#/commissions/registration?scope=all')
  release()
  await expect(dialog).toBeHidden()
  await expect(page).toHaveURL(/commissions\/registration/)
  await expect(table.locator('tbody tr')).toHaveCount(10)
  expect(page.url()).not.toContain('sQueryMode')
})
