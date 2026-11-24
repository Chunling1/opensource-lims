import { test, expect } from '@playwright/test'

test('retired pages no longer resolve while all menu destinations remain registered', async ({ page }) => {
  for (const path of ['/labels', '/testing/data-check/demo-yp-77/report', '/approvals', '/samples', '/samples/new', '/samples/old-record', '/samples/old-record/edit']) {
    await page.goto(`/#${path}`)
    await expect(page.getByRole('heading', { name: '页面不存在', exact: true })).toBeVisible()
    await page.getByRole('link', { name: '返回工作台', exact: true }).click()
    await expect(page).toHaveURL(/#\/dashboard$/)
  }
  const missing = await page.evaluate(async () => {
    const routerPath = '/src/router/index.ts', navigationPath = '/src/router/navigation/navigation.ts'
    const { router } = await import(routerPath)
    const { navigation, flattenNavigation } = await import(navigationPath)
    return flattenNavigation(navigation.flatMap((group: { children: unknown[] }) => group.children))
      .filter((item: { to: string }) => {
        const resolved = router.resolve(item.to)
        return !resolved.matched.length || resolved.meta.errorStatus === 404 || !resolved.matched.at(-1)?.components?.default
      }).map((item: { to: string }) => item.to)
  })
  expect(missing).toEqual([])
})

test('unreachable generic modules resolve to 404 for lists, forms and details', async ({ page }) => {
  const retiredModules = ['quotations', 'sampling', 'locations', 'batches', 'reports', 'reportChanges', 'reportTemplates', 'commissions', 'sampleLinks', 'movements', 'tasks', 'outsourcing']
  await page.goto('/#/dashboard')
  const statuses = await page.evaluate(async modules => {
    const path = '/src/router/index.ts'
    const { router } = await import(path)
    return modules.flatMap(kind => ['', '/new', '/old-record'].map(suffix => ({
      path: `/workspace/${kind}${suffix}`,
      status: router.resolve(`/workspace/${kind}${suffix}`).meta.errorStatus,
    })))
  }, retiredModules)
  for (const route of statuses) expect(route.status, route.path).toBe(404)
  await page.goto('/#/workspace/reports/old-record')
  await expect(page.getByRole('heading', { name: '页面不存在', exact: true })).toBeVisible()
})
