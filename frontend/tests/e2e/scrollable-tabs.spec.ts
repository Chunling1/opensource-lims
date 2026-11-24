import { test, expect, type Locator } from '@playwright/test'

async function noVerticalOverflow(tablist: Locator) {
  await expect(tablist).toBeVisible()
  await expect.poll(() => tablist.evaluate(list => {
    const viewport = list.parentElement!
    return getComputedStyle(viewport).overflowY === 'hidden' && viewport.scrollHeight <= viewport.clientHeight + 1
  })).toBe(true)
  // The pill pointer must remain visible, rather than merely hiding the overflow.
  if (await tablist.evaluate(list => list.classList.contains('arrow-navtabs'))) {
    expect(await tablist.evaluate(list => {
      const viewport = list.parentElement!, button = list.querySelector<HTMLElement>('[aria-selected="true"]')!
      const pointer = getComputedStyle(button, '::before')
      return button.getBoundingClientRect().bottom - parseFloat(pointer.bottom) <= viewport.getBoundingClientRect().top + viewport.clientHeight + 1
    })).toBe(true)
  }
}

async function fullyVisible(tab: Locator) {
  await expect.poll(() => tab.evaluate(element => {
    const viewport = element.closest('[role="tablist"]')!.parentElement!
    const bounds = viewport.getBoundingClientRect(), target = element.getBoundingClientRect()
    return target.left >= bounds.left - 1 && target.right <= bounds.right + 1
  })).toBe(true)
}

test('equipment tabs scroll with arrows, retain active tab on resize and support keyboard navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 950 })
  await page.goto('/#/quality/equipment/ledger')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增设备', exact: true })
  const tabs = dialog.getByRole('tab'), first = tabs.first(), last = tabs.last()
  const left = dialog.getByRole('button', { name: '设备资料：向左滚动标签', exact: true })
  const right = dialog.getByRole('button', { name: '设备资料：向右滚动标签', exact: true })
  await expect(first).toBeEnabled()
  await noVerticalOverflow(dialog.getByRole('tablist'))
  await expect(right).toHaveCount(0)
  await last.click()
  await page.setViewportSize({ width: 390, height: 844 })
  await fullyVisible(last)
  await noVerticalOverflow(dialog.getByRole('tablist'))
  await expect(left).toBeEnabled()
  await expect(right).toBeDisabled()
  await last.press('Home')
  await expect(first).toBeFocused()
  await fullyVisible(first)
  await expect(left).toBeDisabled()
  await right.click()
  await expect(left).toBeEnabled()
  // Scrolling the strip must not change the selected panel.
  await expect(first).toHaveAttribute('aria-selected', 'true')
  await left.click()
  await fullyVisible(first)
  await first.press('End')
  await fullyVisible(last)
  await expect(last).toBeFocused()
  await last.press('ArrowRight')
  await expect(first).toBeFocused()
  await fullyVisible(first)
  await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeInViewport()
  expect(await tabs.evaluateAll(elements => new Set(elements.map(el => Math.round(el.getBoundingClientRect().top))).size)).toBe(1)
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
  await page.setViewportSize({ width: 1440, height: 950 })
  await expect(right).toHaveCount(0)
  await fullyVisible(first)
})

test('personnel tabs stay in one row and keep entered values across keyboard switching', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto('/#/quality/personnel/registration')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增人员', exact: true })
  const tabs = dialog.getByRole('tab'), first = tabs.first(), last = tabs.last()
  await expect(first).toBeEnabled()
  await noVerticalOverflow(dialog.getByRole('tablist'))
  await dialog.getByLabel('人员编号', { exact: true }).fill('TAB-DRAFT')
  await first.press('End')
  await expect(last).toBeFocused()
  await fullyVisible(last)
  expect(await tabs.evaluateAll(elements => new Set(elements.map(el => Math.round(el.getBoundingClientRect().top))).size)).toBe(1)
  await last.press('Home')
  await fullyVisible(first)
  await expect(first).toHaveAttribute('aria-selected', 'true')
  await expect(dialog.getByLabel('人员编号', { exact: true })).toHaveValue('TAB-DRAFT')
  await expect(dialog.getByRole('button', { name: '保存', exact: true })).toBeInViewport()
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
})

for (const width of [1440, 390]) test(`shared page tab strips have no vertical overflow at ${width}`, async ({ page }, info) => {
  test.setTimeout(120000)
  await page.setViewportSize({ width, height: 950 })
  const routes = [
    ['/commissions/registration/samples/new?commissionId=demo-wt-1', '样品表单分区'],
    ['/testing/data-entry/demo-yp-76', '检测数据录入页签'],
    ['/testing/data-query/demo-yp-82', '检测数据录入页签'],
    ['/testing/data-changes/demo-yp-80', '检测数据录入页签'],
    ['/testing/data-check/demo-yp-77', '检测数据录入页签'],
    ['/reports/check/demo-yp-82', '检测数据录入页签'],
    ['/reports/review/demo-yp-82', '检测数据录入页签'],
    ['/reports/approval/demo-yp-88', '检测数据录入页签'],
    ['/reports/query/demo-yp-82', '检测数据录入页签'],
    ['/quality/equipment/loans', '领用与归还'],
  ] as const
  for (const [path, label] of routes) {
    await page.goto(`/#${path}`)
    const tablist = page.getByRole('tablist', { name: label, exact: true })
    await noVerticalOverflow(tablist)
    await fullyVisible(tablist.locator('[aria-selected="true"]'))
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    if (path.startsWith('/reports/check/')) await page.screenshot({ path: info.outputPath(`report-check-tabs-${width}.png`), animations: 'disabled' })
  }
  await page.goto('/#/testing/data-entry/demo-yp-76')
  await page.getByRole('button', { name: '查看修改记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '修改记录', exact: true })
  const records = dialog.getByRole('tablist', { name: '修改记录分类', exact: true })
  await noVerticalOverflow(records)
  await records.getByRole('tab').last().focus()
  await page.keyboard.press('Enter')
  await noVerticalOverflow(records)
})
