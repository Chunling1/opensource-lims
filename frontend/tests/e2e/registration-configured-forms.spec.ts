import { test, expect } from '@playwright/test'

for (const kind of ['commissions', 'samples'] as const) {
  test(`${kind} schema preserves mounted inputs and unique IDs on desktop and dark phone`, async ({ page }, testInfo) => {
    await page.goto(`/#/commissions/registration/${kind}/new${kind === 'samples' ? '?commissionId=demo-wt-1' : ''}`)
    const form = page.getByRole('form', { name: kind === 'samples' ? '样品表单' : '委托表单', exact: true })
    const input = form.locator(kind === 'samples' ? '#sample-name' : '#commission-name')
    await expect(input).toBeVisible()
    await input.evaluate(element => element.setAttribute('data-mount-proof', 'retained'))
    await input.fill('字段配置验证')
    await expect(input).toBeFocused()
    await expect(input).toHaveAttribute('data-mount-proof', 'retained')
    const ids = await form.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id))
    expect(new Set(ids).size).toBe(ids.length)
    if (kind === 'samples') {
      await form.locator('#sample-standardPrice').fill('125.50')
      await expect(form.locator('#sample-standardPrice')).toHaveValue('125.50')
      await form.locator('#sample-urgent').selectOption('true')
      await form.getByRole('tab', { name: '委托信息', exact: true }).click()
      await form.getByRole('tab', { name: '样品信息', exact: true }).click()
      await expect(input).toHaveAttribute('data-mount-proof', 'retained')
      await expect(form.locator('#sample-urgent')).toHaveValue('true')
    }
    for (const [width, theme] of [[1440, 'light'], [390, 'dark']] as const) {
      await page.setViewportSize({ width, height: 1000 })
      await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await input.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`${kind}-${width}-${theme}.png`), fullPage: true })
    }
    await expect(input).toHaveValue('字段配置验证')
  })
}
