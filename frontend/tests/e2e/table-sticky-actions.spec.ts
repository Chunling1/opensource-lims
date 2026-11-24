import { expect, test, type Locator } from '@playwright/test'

async function scrollTo(table: Locator, fraction: number) {
  await table.evaluate((element, value) => {
    const container = element.closest('.table-responsive')!
    container.scrollLeft = (container.scrollWidth - container.clientWidth) * value
  }, fraction)
}
async function rightGap(cell: Locator) {
  return cell.evaluate(element => element.closest('.table-responsive')!.getBoundingClientRect().right - element.getBoundingClientRect().right)
}

for (const width of [1440, 390]) test(`sticky action cells, backgrounds and menus at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.goto('/#/components')
  const example = page.getByRole('region', { name: '公共表格固定操作列验证' })
  const table = example.getByRole('table', { name: '固定列示例列表' })
  const row = table.locator('tbody tr').first(), cell = row.locator('td').last()
  const header = table.getByRole('columnheader', { name: '操作', exact: true })
  await table.scrollIntoViewIfNeeded()
  expect(await table.evaluate(el => { const parent = el.closest('.table-responsive')!; return parent.scrollWidth > parent.clientWidth })).toBe(true)
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await scrollTo(table, 0)
    const start = await row.locator('td').nth(1).evaluate(el => el.getBoundingClientRect().left)
    for (const fraction of [0, 0.5, 1]) {
      await scrollTo(table, fraction)
      await expect.poll(() => rightGap(cell)).toBeCloseTo(0, 0)
      await expect.poll(() => rightGap(header)).toBeCloseTo(0, 0)
      await expect(cell).toHaveCSS('position', 'sticky')
      await expect(header).toHaveCSS('position', 'sticky')
      await expect(cell.locator('.border-start')).toHaveCount(0)
      await expect(header.locator('.border-start')).toHaveCount(0)
      await expect(header.locator('.ri-menu-4-line')).toBeVisible()
    }
    expect(await row.locator('td').nth(1).evaluate(el => el.getBoundingClientRect().left)).toBeLessThan(start)
    await scrollTo(table, 0.5)
    expect(await cell.evaluate(el => getComputedStyle(el).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)')
    const trigger = row.getByRole('button', { name: /更多操作/ })
    await page.mouse.move(0, 0)
    const normal = await cell.evaluate(el => getComputedStyle(el).boxShadow)
    await trigger.hover()
    await expect.poll(() => cell.evaluate(el => getComputedStyle(el).boxShadow)).not.toBe(normal)
    expect(await cell.evaluate(el => getComputedStyle(el).boxShadow)).toBe(await row.locator('td').nth(1).evaluate(el => getComputedStyle(el).boxShadow))
    await trigger.press('ArrowDown')
    const menu = page.getByRole('menu', { name: 'SP-DEMO-1 更多操作' })
    await expect(menu.getByRole('menuitem', { name: '查看' })).toBeFocused()
    const box = (await menu.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(width)
    await scrollTo(table, 0)
    await expect(menu).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(trigger).toBeFocused()
    await row.getByRole('checkbox').check()
    await page.mouse.move(0, 0)
    await expect(row).toHaveClass(/table-active/)
    expect(await cell.evaluate(el => getComputedStyle(el).boxShadow)).toBe(await row.locator('td').nth(1).evaluate(el => getComputedStyle(el).boxShadow))
    await scrollTo(table, 0.5)
    await example.screenshot({ path: info.outputPath(`sticky-actions-${width}-${theme}.png`) })
    await scrollTo(table, 0)
    await row.getByRole('checkbox').uncheck()
  }
  await example.getByLabel('固定右侧操作列', { exact: true }).uncheck()
  await scrollTo(table, 0)
  await expect(cell).toHaveCSS('position', 'static')
  await expect(header).toHaveCSS('position', 'static')
  await expect(cell.locator('.border-start')).toHaveCount(0)
  expect(await rightGap(cell)).toBeLessThan(-100)
  await scrollTo(table, 1)
  await expect.poll(() => rightGap(cell)).toBeCloseTo(0, 0)
  await example.getByLabel('固定右侧操作列', { exact: true }).check()
  await example.getByLabel('显示更多列', { exact: true }).uncheck()
  expect(await table.evaluate(el => { const parent = el.closest('.table-responsive')!; return parent.scrollWidth <= parent.clientWidth })).toBe(true)
  await expect.poll(() => rightGap(cell)).toBeCloseTo(0, 0)
  await example.getByRole('button', { name: '下一页', exact: true }).click()
  await expect(row).toContainText('SP-DEMO-3')
  await expect(cell).toHaveCSS('position', 'sticky')
  await example.getByLabel('显示操作列', { exact: true }).uncheck()
  await expect(header).toHaveCount(0)
  await expect(row.locator('td')).toHaveCount(2)
  await expect(table.locator('.position-sticky')).toHaveCount(0)
  await example.getByLabel('空数据', { exact: true }).check()
  await expect(table).toContainText('暂无符合条件的固定列示例')
  await expect(table.locator('tbody td')).toHaveAttribute('colspan', '2')
  await example.getByLabel('显示操作列', { exact: true }).check()
  await expect(table.locator('tbody td')).toHaveAttribute('colspan', '3')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('loading and disabled actions remain blocked above sticky cells', async ({ page }) => {
  await page.goto('/#/components')
  const example = page.getByRole('region', { name: '公共表格固定操作列验证' })
  const table = example.getByRole('table', { name: '固定列示例列表' })
  const trigger = table.getByRole('button', { name: 'SP-DEMO-1 更多操作', exact: true })
  await example.getByLabel('禁用操作', { exact: true }).check()
  await expect(trigger).toBeDisabled()
  await example.getByLabel('禁用操作', { exact: true }).uncheck()
  await trigger.click()
  await expect(page.getByRole('menu')).toBeVisible()
  await example.getByLabel('模拟加载', { exact: true }).check()
  await expect(page.getByRole('menu')).toHaveCount(0)
  await expect(trigger).toBeDisabled()
  expect(await table.evaluate(el => !!el.closest('[inert]'))).toBe(true)
  await table.scrollIntoViewIfNeeded()
  expect(await trigger.evaluate(el => { const r = el.getBoundingClientRect(); return !!document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest('.z-2') })).toBe(true)
  await example.getByLabel('模拟加载', { exact: true }).uncheck()
  await trigger.click()
  await page.getByRole('menuitem', { name: '查看', exact: true }).click()
  await expect(example.getByRole('status')).toHaveText('已查看 SP-DEMO-1')
})

test('business tables pin actions by default', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 })
  for (const [path, names] of [
    ['/testing/data-entry', ['检测数据录入列表']],
    ['/commissions/registration?scope=all', ['委托列表', '样品列表']],
  ] as const) {
    await page.goto(`/#${path}`)
    for (const name of names) {
      const table = page.getByRole('table', { name, exact: true })
      const cell = table.locator('tbody tr').first().locator('td').last()
      await table.scrollIntoViewIfNeeded()
      await expect(cell).toHaveCSS('position', 'sticky')
      for (const fraction of [0, 0.5, 1]) {
        await scrollTo(table, fraction)
        await expect.poll(() => rightGap(cell)).toBeCloseTo(0, 0)
      }
      await cell.getByRole('button', { name: /更多操作/ }).click()
      await expect(page.getByRole('menu')).toBeVisible()
      await page.keyboard.press('Escape')
    }
  }
})
