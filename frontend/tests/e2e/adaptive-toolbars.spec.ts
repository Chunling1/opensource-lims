import { test, expect } from '@playwright/test'
import { toolbarButton } from './helpers/toolbar'

const routes = [
  '/commissions/registration', '/commissions/review', '/commissions/query', '/commissions/changes', '/commissions/cancellation-approval',
  '/samples/inbound', '/samples/outbound', '/samples/disposal', '/samples/flow',
  '/testing/assignment', '/testing/sample-pickup', '/testing/task-query', '/testing/data-entry', '/testing/data-check', '/testing/sample-copy', '/testing/data-query', '/testing/data-changes', '/testing/sample-completion',
  '/reports/check', '/reports/review', '/reports/approval', '/reports/print', '/reports/signing', '/reports/distribution', '/reports/archive', '/reports/query', '/reports/changes/internal', '/reports/changes/external',
  '/quality/personnel/registration', '/quality/personnel/query', '/quality/personnel/certificates', '/quality/equipment/ledger',
]
for (const width of [390, 1024, 1440]) test(`all list toolbars fit their containers at ${width}px`, async ({ page }) => {
  test.setTimeout(180000)
  await page.setViewportSize({ width, height: 1000 })
  for (const route of routes) await test.step(route, async () => {
    await page.goto('/#' + route)
    const toolbars = page.getByRole('group', { name: /工具栏$/ })
    await expect(toolbars.first()).toBeVisible()
    // Some workspaces poll in the background; wait for rendered rows instead.
    await expect(page.locator('tbody tr').first()).toBeVisible()
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    for (const toolbar of await toolbars.all()) {
      const geometry = await toolbar.evaluate(element => {
        const boxes = [...element.querySelectorAll<HTMLButtonElement>('button, a.btn')].filter(button => button.getClientRects().length && !button.closest('.dropdown-menu')).map(button => button.getBoundingClientRect())
        const parent = element.parentElement!.getBoundingClientRect()
        return { fits: boxes.every(box => box.left >= parent.left - 1 && box.right <= parent.right + 1), tops: boxes.map(box => box.top) }
      })
      expect(geometry.fits, route).toBe(true)
      expect(Math.max(...geometry.tops) - Math.min(...geometry.tops), route).toBeLessThan(2)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), route).toBe(true)
  })
})

test('report plan action stays available after moving into overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/#/reports/check')
  await expect(page.getByRole('table', { name: '报告校核列表', exact: true }).locator('tbody tr').first()).toBeVisible()
  for (const width of [1440, 320, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    await (await toolbarButton(page, '报告校核', '检测方案')).click()
    const drawer = page.getByRole('dialog', { name: '筛选检测方案', exact: true })
    await expect(drawer).toBeVisible()
    await drawer.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(drawer).toBeHidden()
  }
})
