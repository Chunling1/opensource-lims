import { test, expect } from '@playwright/test'

test('error routes retain navigation by default, support full pages and valid local images', async ({ page }) => {
  for (const code of [400, 401, 403, 404, 500, 503]) {
    await page.goto(`/#/errors/${code}`)
    await expect(page.locator('#layout-wrapper')).toBeVisible()
    await expect(page.locator('main h3')).toBeVisible()
    expect(await page.locator('main img').evaluateAll(images => images.every(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true)
  }
  await page.goto('/#/errors/500/standalone')
  await expect(page.getByRole('heading', { name: '暂时无法完成操作' })).toBeVisible()
  await expect(page.locator('#layout-wrapper')).toHaveCount(0)
  await page.goto('/#/not-an-existing-page')
  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible()
  await page.getByRole('link', { name: '返回工作台', exact: true }).click()
  await expect(page).toHaveURL(/dashboard$/)
})

test('missing records show a content error and preserve the explicit query return path', async ({ page }) => {
  const list = '/commissions/query?scope=all&sKeyword=SP'
  await page.goto(`/#${list}`)
  await expect(page.getByRole('heading', { name: '委托查询', exact: true })).toBeVisible()
  await page.evaluate(list => { location.hash = `/commissions/query/samples/missing-record?returnTo=${encodeURIComponent(list)}` }, list)
  await expect(page.getByRole('heading', { name: '记录不存在或已不可访问' })).toBeVisible()
  await expect(page.locator('#layout-wrapper')).toBeVisible()
  await page.getByRole('link', { name: '返回列表', exact: true }).click()
  await expect(page).toHaveURL(new RegExp('commissions/query\\?scope=all&sKeyword=SP$'))
})

test('startup storage failure gives standalone recovery without deleting data', async ({ page }) => {
  await page.addInitScript(() => { const open = IDBFactory.prototype.open; let first = true; IDBFactory.prototype.open = function (...args: Parameters<IDBFactory['open']>) { if (first) { first = false; throw new DOMException('blocked by test', 'SecurityError') }; return open.apply(this, args) } })
  await page.goto('/#/dashboard')
  await expect(page.getByRole('heading', { name: '本地业务数据暂不可用' })).toBeVisible()
  await expect(page.locator('#layout-wrapper')).toHaveCount(0)
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.locator('#layout-wrapper')).toBeVisible()
  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
})

test('lazy route failure keeps the current workspace, and explicit retry recovers', async ({ page }) => {
  await page.goto('/#/dashboard')
  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
  await page.route('**/src/views/commissions/CommissionQueryView.vue', route => route.abort())
  await page.evaluate(() => { location.hash = '/commissions/query' })
  await expect(page.getByRole('alert').filter({ hasText: '页面资源加载失败' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
  await page.unroute('**/src/views/commissions/CommissionQueryView.vue')
  await page.getByRole('button', { name: '刷新页面', exact: true }).click()
  await expect(page.getByRole('heading', { name: '委托查询', exact: true }).first()).toBeVisible()
})

test('offline does not block cached notifications; main script failure has static feedback', async ({ page, context }) => {
  await page.goto('/#/notifications')
  await expect(page.getByRole('heading', { name: '通知中心', exact: true })).toBeVisible()
  await context.setOffline(true)
  await page.locator('main .notification-item').first().click()
  await expect(page.locator('main .notification-item')).toHaveCount(3)
  await expect(page.locator('main [role="alert"]')).toHaveCount(0)
  await context.setOffline(false)
  await page.route(url => url.pathname === '/src/main.ts', route => route.abort())
  await page.reload()
  await expect(page.getByRole('heading', { name: '应用资源加载失败' })).toBeVisible()
  await expect(page.getByRole('button', { name: '重新加载' })).toBeVisible()
})


test('module access denial retains navigation and offers identity recovery', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lims.identity.v1', 'finance'))
  await page.goto('/#/quality/equipment/ledger')
  await expect(page.getByRole('heading', { name: '当前身份无权访问', exact: true })).toBeVisible()
  await expect(page.locator('#layout-wrapper')).toBeVisible()
  await expect(page.getByRole('link', { name: '返回工作台', exact: true })).toBeVisible()
  await page.locator('main').getByRole('link', { name: '切换演示身份', exact: true }).click()
  await expect(page.getByRole('heading', { name: '演示身份', exact: true }).first()).toBeVisible()
})

for (const width of [1440, 820, 390]) test(`template errors fit all themes and layouts at ${width}px`, async ({ page }, testInfo) => {
  test.setTimeout(120000)
  await page.setViewportSize({ width, height: 960 })
  await page.goto('/#/errors/404')
  await expect(page.getByRole('heading', { name: '页面不存在', exact: true })).toBeVisible()
  for (const theme of ['default', 'saas', 'corporate', 'galaxy', 'material', 'creative', 'minimal', 'modern', 'interactive', 'classic', 'vintage']) {
    for (const layout of ['vertical', 'horizontal', 'twocolumn', 'semibox']) {
      await page.evaluate(async ({ theme, layout }) => { const path = '/src/stores/theme/index.ts'; const { useThemeStore } = await import(path); const store = useThemeStore(); store.set('theme', theme); store.set('layout', layout) }, { theme, layout })
      for (const code of [404, 500]) {
        await page.evaluate(code => { location.hash = `/errors/${code}` }, code)
        await expect(page.locator('main h3')).toHaveText(code === 404 ? '页面不存在' : '暂时无法完成操作')
        await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
        await expect(page.locator('main img')).toBeVisible()
        if (theme === 'default' && layout === 'vertical') await page.screenshot({ path: testInfo.outputPath(`error-${code}-${width}.png`), fullPage: true })
      }
    }
  }
  await page.goto('/#/errors/500/standalone')
  await expect(page.locator('#layout-wrapper')).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath(`standalone-500-${width}.png`), fullPage: true })
})


test('first route chunk failure offers standalone refresh recovery', async ({ page }) => {
  await page.route('**/src/views/commissions/CommissionQueryView.vue', route => route.abort())
  await page.goto('/#/commissions/query')
  await expect(page.getByRole('heading', { name: '页面资源加载失败', exact: true })).toBeVisible()
  await expect(page.locator('#layout-wrapper')).toHaveCount(0)
  await page.unroute('**/src/views/commissions/CommissionQueryView.vue')
  await page.getByRole('button', { name: '刷新页面', exact: true }).click()
  await expect(page.getByRole('heading', { name: '委托查询', exact: true }).first()).toBeVisible()
})

test('database initialization write failure settles and can be retried', async ({ page }) => {
  await page.addInitScript(() => { const put = IDBObjectStore.prototype.put; let first = true; IDBObjectStore.prototype.put = function (...args: Parameters<IDBObjectStore['put']>) { if (first) { first = false; throw new DOMException('quota fault', 'QuotaExceededError') }; return put.apply(this, args) } })
  await page.goto('/#/dashboard')
  await expect(page.getByRole('heading', { name: '本地业务数据暂不可用' })).toBeVisible()
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
})
