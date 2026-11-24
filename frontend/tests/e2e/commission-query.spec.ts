import { test, expect, type Page } from '@playwright/test'
const root = '/commissions/query'
const list = `${root}?scope=all&current=demo-wt-1&cSort=code&cDirection=asc&sSort=code&sDirection=asc`
const headers = { 'X-Demo-Actor': 'admin' }
async function menu(page: Page, code: string) {
  await page.getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
  return page.getByRole('menu', { name: `${code} 更多操作`, exact: true })
}

test('query shares readonly details and printing, with only the requested row actions', async ({ page }, testInfo) => {
  await page.route('**/api/registration/samples/query', async route => {
    expect(route.request().postDataJSON().workspace).toBe('query')
    await route.continue()
  })
  await page.goto(`/#${list}`)
  await expect(page.getByRole('heading', { name: '委托查询', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /新增委托|新增样品/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '新增样品', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /批量修改|快速评审/ })).toHaveCount(0)
  let actions = await menu(page, 'WT202609001')
  await expect(actions.getByRole('menuitem')).toHaveText(['查看', '打印', '附件管理'])
  await actions.getByRole('menuitem', { name: '查看', exact: true }).click()
  await expect(page).toHaveURL(/query\/commissions\/demo-wt-1/)
  await expect(page.getByRole('button', { name: /保存/ })).toHaveCount(0)
  await page.getByRole('link', { name: '返回委托查询', exact: true }).click()
  await expect(page).toHaveURL(new RegExp('current=demo-wt-1'))
  actions = await menu(page, 'SP2026090001')
  await expect(actions.getByRole('menuitem')).toHaveText(['查看', '打印', '附件管理'])
  await actions.getByRole('menuitem', { name: '查看', exact: true }).click()
  await expect(page.locator('#sample-name')).not.toBeEditable()
  await page.getByRole('link', { name: '返回委托查询', exact: true }).click()
  for (const [code, kind, id, documentType] of [
    ['WT202609001', 'commissions', 'demo-wt-1', 'commission'],
    ['SP2026090001', 'samples', 'demo-yp-1', 'sample'],
  ]) {
    actions = await menu(page, code!)
    await actions.getByRole('menuitem', { name: '打印', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`query/${kind}/${id}/print`))
    await page.getByLabel('委托单类型', { exact: true }).selectOption('product')
    const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith(`/${kind}/${id}/prints`))
    await page.getByRole('button', { name: '生成并预览', exact: true }).click()
    expect(await (await response).json()).toMatchObject({ documentType, documentCode: code })
    await page.getByRole('link', { name: '返回委托查询', exact: true }).click()
  }
  await page.screenshot({ path: testInfo.outputPath('query-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => document.documentElement.setAttribute('data-bs-theme', 'dark'))
  actions = await menu(page, 'SP2026090001')
  const box = await actions.boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(391)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath('query-phone-dark.png') })
  await page.goto(`/#${root}/samples/demo-yp-1/edit`)
  await expect(page).toHaveURL(new RegExp(`${root}/samples/demo-yp-1$`))
  await expect(page.locator('#sample-name')).not.toBeEditable()
  await page.goto(`/#${root}/samples/new`)
  await expect(page).toHaveURL(new RegExp(`${root}$`))
})

test('query preserves empty-commission printing and readonly sample restrictions', async ({ page }) => {
  await page.goto(`/#${list}`)
  await expect(page.getByRole('button', { name: 'WT202609001 更多操作', exact: true })).toBeVisible()
  const order = await (await page.request.get('/api/registration/commissions/demo-wt-1', { headers })).json()
  const empty = await (await page.request.post('/api/registration/commissions', { headers, data: { input: { ...order, name: '查询空委托' } } })).json()
  await page.goto(`/#${root}?cCode=${empty.code}`)
  await expect((await menu(page, empty.code)).getByRole('menuitem', { name: '打印', exact: true })).toBeDisabled()
  const sample = await (await page.request.get('/api/registration/samples/demo-yp-1', { headers })).json()
  const applied = await page.request.post('/api/registration/samples/demo-yp-1/actions', { headers, data: { actionId: 'void', version: sample.version, reason: '申请作废' } })
  expect(applied.ok()).toBe(true)
  await page.goto(`/#${list}`)
  const actions = await menu(page, sample.code)
  await expect(actions.getByRole('menuitem')).toHaveText(['查看', '附件管理'])
})
