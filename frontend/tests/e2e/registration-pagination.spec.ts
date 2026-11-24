import { test, expect } from '@playwright/test'

test('organization picker pagination stays the same height across first middle and last pages', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/commissions/registration/commissions/new')
    await page.getByRole('button', { name: '选择合同甲方', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '选择合同甲方', exact: true })
    const nav = dialog.getByRole('navigation', { name: '可选单位分页' })
    const jump = dialog.getByRole('form', { name: '可选单位跳页' })
    await expect(nav.getByRole('button', { name: '第 1 页', exact: true })).toHaveAttribute('aria-current', 'page')
    const footer = nav.locator('..'), firstBox = await footer.boundingBox(), jumpBox = await jump.boundingBox()
    if (width === 1440) expect(Math.abs((await nav.boundingBox())!.y - jumpBox!.y)).toBeLessThan(10)
    for (const target of [3, 5, 9, 1]) {
      await dialog.getByRole('spinbutton', { name: '可选单位页码', exact: true }).fill(String(target))
      await jump.getByRole('button', { name: '跳转', exact: true }).click()
      await expect(nav.getByRole('button', { name: `第 ${target} 页`, exact: true })).toHaveAttribute('aria-current', 'page')
      expect((await footer.boundingBox())!.height).toBe(firstBox!.height)
      expect((await jump.boundingBox())!.y - (await footer.boundingBox())!.y).toBeCloseTo(jumpBox!.y - firstBox!.y, 0)
      if (width === 1440) await expect(nav.locator('button.page')).toHaveCount(5)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
  }
})

test('large page numbers reserve stable width before reaching thousands of pages', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/registration/organizations/query', async route => {
    const query = route.request().postDataJSON(), current = query.page || 1, pageSize = query.pageSize || 10
    await route.fulfill({ json: { items: [{ id: `organization-${current}`, name: `第 ${current} 页单位` }], total: 123450, page: current, pageSize } })
  })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/#/commissions/registration/commissions/new')
    await page.getByRole('button', { name: '选择合同甲方', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '选择合同甲方', exact: true })
    const nav = dialog.getByRole('navigation', { name: '可选单位分页' }), footer = nav.locator('..')
    const jump = dialog.getByRole('form', { name: '可选单位跳页' }), input = dialog.getByRole('spinbutton', { name: '可选单位页码', exact: true })
    await expect(nav.getByRole('button', { name: '第 1 页', exact: true })).toHaveAttribute('aria-current', 'page')
    const initial = await footer.boundingBox(), offset = (await jump.boundingBox())!.y - initial!.y
    const pageWidth = (await nav.getByRole('button', { name: '第 1 页', exact: true }).boundingBox())!.width
    const inputWidth = (await input.boundingBox())!.width
    if (width === 1440) expect(Math.abs((await nav.boundingBox())!.y - (await jump.boundingBox())!.y)).toBeLessThan(10)
    for (const target of [9, 99, 999, 1000, 9999, 12345, 1]) {
      await input.fill(String(target))
      await jump.getByRole('button', { name: '跳转', exact: true }).click()
      const active = nav.getByRole('button', { name: `第 ${target} 页`, exact: true })
      await expect(active).toHaveAttribute('aria-current', 'page')
      expect((await active.boundingBox())!.width).toBe(pageWidth)
      expect((await input.boundingBox())!.width).toBe(inputWidth)
      expect((await footer.boundingBox())!.height).toBe(initial!.height)
      expect((await jump.boundingBox())!.y - (await footer.boundingBox())!.y).toBeCloseTo(offset, 0)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
  }
})
