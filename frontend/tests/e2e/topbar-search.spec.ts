import { test, expect } from '@playwright/test'

test('search uses current sample data and preserves number and name filters through detail and refresh', async ({ page }, info) => {
  await page.goto('/#/dashboard')
  const sample = await page.evaluate(async () => {
    const path = '/src/services/commissions/registrationApi.ts'
    return (await (await import(path)).registrationDemo.samples({ pageSize: 10 }, undefined, 'query')).items[0] as { id: string; code: string; name: string }
  })
  const search = page.getByRole('searchbox', { name: '全局样品搜索', exact: true })
  for (const term of [sample.code, sample.name]) {
    const queried = page.waitForResponse(r => r.url().endsWith('/samples/query') && r.request().postDataJSON().keyword === term)
    await search.fill(term)
    await search.focus()
    const result = await queried
    expect(result.request().postDataJSON()).toMatchObject({ workspace: 'query', keyword: term, page: 1, pageSize: 10 })
    const data = await result.json()
    const suggestions = page.locator('#search-dropdown')
    const links = suggestions.locator('a[href*="/commissions/query/samples/"]')
    await expect(links).toHaveCount(Math.min(4, data.items.length))
    await expect(suggestions.getByRole('button', { name: `查看全部结果（${data.total}）` })).toBeVisible()
    await expect(suggestions.locator('a[href^="#/samples"], a[href^="#/workspace"]')).toHaveCount(0)
    await page.screenshot({ path: info.outputPath(`search-${term === sample.code ? 'code' : 'name'}.png`) })
    await links.first().click()
    await expect(page).toHaveURL(/#\/commissions\/query\/samples\//)
    await expect(page.getByRole('heading', { name: '样品详情', exact: true })).toBeVisible()
    await page.getByRole('link', { name: '返回委托查询', exact: true }).click()
    await expect(page).toHaveURL(/#\/commissions\/query\?scope=all&sKeyword=/)
    await expect(page.getByRole('tab', { name: '全部样品', exact: true })).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByRole('form', { name: '样品查询', exact: true })).toContainText(`样品编号或名称包含：${term}`)
    await page.reload()
    await expect(page.getByRole('form', { name: '样品查询', exact: true })).toContainText(term)
    await expect(page.locator('#samples-panel tbody tr').first()).toBeVisible()
  }
  await page.getByRole('button', { name: '移除样品编号或名称条件', exact: true }).click()
  await page.getByRole('form', { name: '样品查询', exact: true }).getByRole('button', { name: '查询', exact: true }).click()
  await expect(page).not.toHaveURL(/sKeyword=/)
  await search.fill('不存在的搜索样品')
  await search.focus()
  await expect(page.locator('#search-dropdown')).toContainText('暂无匹配样品')
  await search.press('Enter')
  await expect(page.getByRole('form', { name: '样品查询', exact: true })).toContainText('不存在的搜索样品')
  await expect(page.locator('#samples-panel')).toContainText('暂无符合条件的样品')
})

test('search reports HTTP failure, retries, and clears results on identity change', async ({ page }) => {
  await page.goto('/#/dashboard')
  await page.route('**/api/registration/samples/query', route => route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '搜索服务暂不可用' } } }), { times: 1 })
  const search = page.getByRole('searchbox', { name: '全局样品搜索', exact: true })
  await search.fill('SP')
  await expect(page.locator('#search-dropdown')).toContainText('搜索服务暂不可用')
  await page.getByRole('button', { name: '重试搜索', exact: true }).click()
  await expect(page.locator('#search-dropdown a[href*="/commissions/query/samples/"]')).toHaveCount(4)
  await page.evaluate(async () => { const path = '/src/stores/session.ts'; await (await import(path)).switchIdentity('finance') })
  await expect(page.locator('#search-dropdown a[href*="/samples/"]')).toHaveCount(0)
  await expect(page.locator('#search-dropdown').getByRole('button', { name: '查看全部结果', exact: false })).toHaveCount(0)
})

test('late search responses cannot replace a newer query', async ({ page }) => {
  await page.goto('/#/dashboard')
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/registration/samples/query', async route => {
    const query = route.request().postDataJSON()
    if (query.keyword === 'SP') {
      const response = await route.fetch()
      await gate
      await route.fulfill({ response }).catch(() => {})
    } else await route.continue()
  })
  const search = page.getByRole('searchbox', { name: '全局样品搜索', exact: true })
  const pending = page.waitForRequest(r => r.url().endsWith('/samples/query') && r.postDataJSON().keyword === 'SP')
  await search.fill('SP')
  await pending
  await search.fill('没有这个新样品')
  await expect(page.locator('#search-dropdown')).toContainText('暂无匹配样品')
  release()
  await expect(page.locator('#search-dropdown a[href*="/samples/"]')).toHaveCount(0)
  await search.press('Escape')
  await expect(page.locator('#search-dropdown')).toHaveCount(0)
})

test('mobile suggestions and all results use the current query page', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/dashboard')
  await page.getByRole('button', { name: '打开手机搜索' }).click()
  await page.getByRole('searchbox', { name: '手机样品搜索', exact: true }).fill('SP')
  const suggestions = page.locator('#search-dropdown-responsive')
  await expect(suggestions.locator('a[href*="/commissions/query/samples/"]')).toHaveCount(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('mobile-search.png'), fullPage: true })
  await suggestions.getByRole('button', { name: '查看全部结果', exact: false }).click()
  await expect(page).toHaveURL(/#\/commissions\/query\?scope=all&sKeyword=SP/)
  await expect(page.getByRole('tab', { name: '全部样品', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('form', { name: '样品查询', exact: true })).toContainText('样品编号或名称包含：SP')
})
