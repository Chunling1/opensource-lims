import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'

test('report menu follows the documented hierarchy and restores nested page context', async ({ page }) => {
  const section = readFileSync('docs/菜单.txt', 'utf8').split('\n报告管理')[1]!.split('\n客户管理')[0]!
  const rows = section.split(/\r?\n/).filter(line => line.includes('- '))
  await page.goto('/#/reports/check')
  const menu = page.locator('#menu-reports')
  await expect(menu.locator('a')).toHaveText(rows.map(line => line.trim().slice(2)))
  await expect(menu.locator(':scope > ul > li > a')).toHaveText(rows.filter(line => line.startsWith('- ')).map(line => line.slice(2)))
  const links = await menu.locator('a:not([data-bs-toggle])').evaluateAll(nodes => nodes.map(node => ({ label: node.textContent!.trim(), href: node.getAttribute('href')! })))
  expect(links).toHaveLength(10)
  for (const link of links) {
    await page.goto(`/${link.href}`)
    const labels = ['报告管理', ...(link.href.includes('/changes/') ? ['报告更改申请'] : []), link.label]
    await expect(page.getByRole('heading', { name: link.label, exact: true, level: 4 })).toBeVisible()
    await expect(page.getByRole('navigation', { name: '面包屑', exact: true }).locator('li')).toHaveText(labels)
    await expect(menu.locator('a.active:not([data-bs-toggle])')).toHaveText(link.label)
    await page.reload()
    await expect(menu.locator('a.active:not([data-bs-toggle])')).toHaveText(link.label)
    if (labels.length === 3) await expect(menu.getByRole('button', { name: labels[1], exact: true })).toHaveAttribute('aria-expanded', 'true')
  }
})

test('nested report navigation works in four layouts on desktop and mobile', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 })
    for (const layout of ['vertical', 'horizontal', 'twocolumn', 'semibox']) {
      await page.goto('/#/dashboard')
      await page.getByRole('button', { name: '打开主题设置' }).click()
      await page.getByTestId(`theme-label-layout-${layout}`).click()
      await page.getByRole('button', { name: '关闭主题设置' }).click()
      await expect(page.locator('.offcanvas-backdrop')).toHaveCount(0)
      if (width < 768) await page.getByRole('button', { name: '切换导航菜单' }).click()
      if (layout === 'twocolumn' && width > 768) await page.getByRole('link', { name: '报告管理', exact: true }).first().click()
      else await page.locator('a.menu-link').filter({ hasText: '报告管理' }).click()
      await page.locator('#menu-reports').getByRole('button', { name: '报告更改申请', exact: true }).click()
      await page.locator('#submenu-reports-changes').getByRole('link', { name: '内部申请', exact: true }).click()
      await expect(page).toHaveURL(/#\/reports\/changes\/internal$/)
      await expect(page.getByRole('heading', { name: '内部申请', exact: true, level: 4 })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    }
  }
})
