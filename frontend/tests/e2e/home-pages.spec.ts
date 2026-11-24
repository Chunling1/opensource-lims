import { test, expect } from '@playwright/test'

test('home menu opens blank work pages without approval task entries', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/')
  await expect(page).toHaveURL(/#\/dashboard$/)
  const main = page.locator('main .page-content')
  const home = page.locator('#menu-overview')
  await expect(home.getByRole('link')).toHaveText(['工作台', '我的待办', '通知中心'])
  for (const [title, path] of [['我的待办', 'work'], ['工作台', 'dashboard']] as const) {
    await home.getByRole('link', { name: title, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`#/${path}$`))
    await expect(main.getByRole('heading', { name: title, exact: true })).toBeVisible()
    await expect(main.getByRole('navigation', { name: '面包屑' }).locator('li')).toHaveText(['首页', title])
    await expect(main.locator('.card, table, form, button, .notification-item')).toHaveCount(0)
    await expect(main).toHaveText(new RegExp(`^\\s*${title}\\s*首页\\s*${title}\\s*$`))
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await expect(main.getByRole('heading', { name: title, exact: true })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: info.outputPath(`${path}-${width}.png`), fullPage: true })
    }
    await page.setViewportSize({ width: 1440, height: 900 })
  }
  await expect(page.locator('a[href="#/approvals"]')).toHaveCount(0)
  await home.getByRole('link', { name: '通知中心', exact: true }).click()
  await expect(main.locator('.notification-item')).toHaveCount(3)
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.locator('.topbar-user').getByRole('link', { name: '切换演示身份' }).click()
  await expect(main.getByRole('heading', { name: '演示身份', exact: true }).first()).toBeVisible()
  const otherIdentity = main.locator('button.btn-soft-primary').first()
  const name = await otherIdentity.innerText()
  await otherIdentity.click()
  await expect(main.locator('p strong')).toHaveText(name)
  await expect(main.getByRole('button', { name, exact: true })).toHaveClass(/btn-primary/)
  expect(errors).toEqual([])
})
