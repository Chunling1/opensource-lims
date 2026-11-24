import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

async function settleViewport(page: Page) {
  await page.evaluate(async () => {
    // The theme animates the sidebar and content margins across breakpoints.
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    await Promise.all(document.getAnimations().filter(animation => animation.effect?.getComputedTiming().iterations !== Infinity).map(animation => animation.finished.catch(() => {})))
  })
}

test('expanded query fields stop before the action column and remain full-width on narrow screens', async ({ page }, testInfo) => {
  test.setTimeout(90000)
  const pages = [
    ['testing/assignment', 'assignment'], ['testing/sample-pickup', 'pickup'],
    ['testing/task-query', 'task-query'], ['testing/data-entry', 'data-entry'], ['samples/flow', 'flow'],
  ] as const
  for (const [path, prefix] of pages) {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto(`/#/${path}`)
    const more = page.locator(`#${prefix}-more-filters`)
    const form = more.locator('xpath=ancestor::form')
    const search = form.getByRole('button', { name: '查询', exact: true })
    await expect(search).toBeEnabled()
    await form.getByRole('button', { name: /更多筛选/ }).click()
    await expect(more).toBeVisible()
    for (const width of [1920, 1440, 1280, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      await settleViewport(page)
      const area = await more.boundingBox(), button = await search.boundingBox()
      const fields = await form.evaluate((element, moreId) => {
        const controls = Array.from(element.querySelectorAll<HTMLElement>('input,select')).filter(control => !control.closest(`#${moreId}`) && control.getClientRects().length)
        const rects = controls.map(control => control.getBoundingClientRect())
        return { right: Math.max(...rects.map(rect => rect.right)), bottom: Math.max(...rects.map(rect => rect.bottom)) }
      }, `${prefix}-more-filters`)
      if (width >= 1200) {
        expect(area!.x + area!.width).toBeLessThanOrEqual(button!.x)
        expect(Math.abs(button!.y + button!.height - fields.bottom)).toBeLessThan(2)
      } else {
        expect(button!.y).toBeGreaterThanOrEqual(area!.y + area!.height)
      }
      const right = await more.evaluate(element => Math.max(...Array.from(element.querySelectorAll<HTMLElement>('input,select')).map(control => control.getBoundingClientRect().right)))
      expect(Math.abs(right - fields.right)).toBeLessThan(2)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      if (width === 1440 || width === 390) {
        await page.evaluate(theme => document.documentElement.setAttribute('data-bs-theme', theme), width === 390 ? 'dark' : 'light')
        await form.screenshot({ path: testInfo.outputPath(`${prefix}-expanded-${width}.png`) })
      }
    }
    await form.getByRole('button', { name: /更多筛选/ }).click()
    await expect(more).toBeHidden()
    await expect(search).toBeEnabled()
  }
})

test('query inputs stay balanced on wide screens across stock and commission pages', async ({ page }, testInfo) => {
  for (const path of ['/samples/inbound', '/samples/outbound', '/samples/disposal', '/commissions/registration', '/commissions/review', '/commissions/query']) {
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto(`/#${path}${path.startsWith('/commissions/') ? '?scope=all' : ''}`)
    const selectors = path.startsWith('/commissions/') ? ['#commission-filter-contains', '#sample-filter-contains'] : [path.endsWith('/disposal') ? '#disposal-keyword' : '#inbound-code']
    for (const width of [1920, 2560, 1280]) {
      await page.setViewportSize({ width, height: 1080 })
      await settleViewport(page)
      for (const selector of selectors) {
        const input = page.locator(selector)
        await expect(input).toBeVisible()
        const box = await input.boundingBox()
        expect(box!.width, `${path}: ${selector} at ${width}`).toBeGreaterThanOrEqual(150)
        const form = input.locator('xpath=ancestor::form'), formBox = await form.boundingBox()
        expect(box!.width).toBeLessThan(formBox!.width / 2)
        const peer = selector === '#inbound-code' ? '#inbound-status' : selector === '#commission-filter-contains' ? '#commission-filter-status' : selector === '#sample-filter-contains' ? '#sample-filter-data-status' : undefined
        if (peer) expect(Math.abs(box!.width - (await page.locator(peer).boundingBox())!.width)).toBeLessThan(2)
        const gap = await form.getByRole('button', { name: '查询', exact: true }).evaluate(button => {
          const row = button.closest('.row')!, cells = Array.from(row.children), action = cells.at(-1)!.getBoundingClientRect(), previous = cells.at(-2)!.getBoundingClientRect()
          return Math.abs(action.bottom - previous.bottom) < 2 ? action.left - previous.right : 0
        })
        expect(gap).toBeLessThan(2)
      }
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      if (width === 1920) await page.locator(selectors[0]!).locator('xpath=ancestor::form').screenshot({ path: testInfo.outputPath(`${path.replaceAll('/', '-')}-wide.png`) })
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  }
})
