import { test, expect } from '@playwright/test'

test('breadcrumbs follow menu hierarchy and keep registration list context', async ({ page }) => {
  const list = '/commissions/registration?cKeyword=WT202609001&cPageSize=10&scope=all'
  await page.goto(`/#${list}`)
  const breadcrumb = page.getByRole('navigation', { name: '面包屑', exact: true })
  await expect(breadcrumb.locator('li')).toHaveText(['委托管理', '委托登记'])
  await page.getByRole('button', { name: 'WT202609001 更多操作', exact: true }).click()
  await page.getByRole('menuitem', { name: '新增样品', exact: true }).click()
  await expect(breadcrumb.locator('li')).toHaveText(['委托管理', '委托登记', '新增样品'])
  await expect(breadcrumb.locator('[aria-current="page"]')).toHaveText('新增样品')
  await expect(breadcrumb.getByRole('link')).toHaveCount(1)
  const back = breadcrumb.getByRole('link', { name: '委托登记', exact: true })
  const returnUrl = await back.getAttribute('href')
  expect(returnUrl).toContain('cKeyword=WT202609001')
  expect(returnUrl).toContain('scope=all')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(breadcrumb).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await back.click()
  await expect(page).toHaveURL(new RegExp('cKeyword=WT202609001'))
  await expect(page.getByRole('tab', { name: '全部样品', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(breadcrumb.locator('li')).toHaveText(['委托管理', '委托登记'])
})

test('current labels change for forms, details, printing and other menu groups', async ({ page }) => {
  const breadcrumb = page.getByRole('navigation', { name: '面包屑', exact: true })
  const cases = [
    ['/commissions/registration/commissions/new', ['委托管理', '委托登记', '新增委托']],
    ['/commissions/registration/commissions/demo-wt-1/edit', ['委托管理', '委托登记', '修改委托']],
    ['/commissions/registration/commissions/demo-wt-1', ['委托管理', '委托登记', '委托详情']],
    ['/commissions/registration/commissions/demo-wt-1/print', ['委托管理', '委托登记', '打印委托单']],
    ['/commissions/review', ['委托管理', '合同评审']],
    ['/commissions/query/samples/demo-yp-1', ['委托管理', '委托查询', '样品详情']],
    ['/dashboard', ['首页', '工作台']],
  ] as const
  for (const [path, labels] of cases) {
    await page.goto(`/#${path}`)
    await expect(breadcrumb.locator('li')).toHaveText([...labels])
    await expect(breadcrumb.locator('[aria-current="page"] a')).toHaveCount(0)
  }
  await page.goto('/#/commissions/registration/commissions/new?returnTo=https%3A%2F%2Fexample.com')
  await expect(breadcrumb.getByRole('link', { name: '委托登记', exact: true })).toHaveAttribute('href', '#/commissions/registration')
})
