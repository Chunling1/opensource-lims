import { test, expect } from '@playwright/test'

for (const target of ['drawer', 'equipment'] as const) test(`${target} retains lazy branches and pages when collapsed`, async ({ page }) => {
  const endpoint = target === 'drawer' ? '/test-plans/query' : '/quality/equipment/ledger/plans'
  const requests: { parentId?: string; page?: number }[] = []
  let contexts = 0
  page.on('request', request => { if (request.url().endsWith(target === 'drawer' ? '/test-plans/selection' : '/quality/equipment/ledger/plan-selection')) contexts++ })
  page.on('request', request => { if (request.url().endsWith(endpoint)) requests.push(request.postDataJSON()) })
  if (target === 'drawer') {
    await page.goto('/#/testing/assignment')
    await page.getByRole('button', { name: '检测方案', exact: true }).click()
  } else {
    await page.goto('/#/quality/equipment/ledger')
    await page.getByRole('button', { name: '新增', exact: true }).click()
    await page.getByRole('tab', { name: '检测方案', exact: true }).click()
    await page.getByRole('button', { name: '选择方案', exact: true }).click()
  }
  const dialog = page.getByRole('dialog', { name: target === 'drawer' ? '筛选检测方案' : '选择方案', exact: true })
  if (target === 'drawer') await dialog.getByRole('button', { name: '全部显示', exact: true }).click()
  const group = dialog.getByRole('button', { name: '温度校准实验室', exact: true })
  await expect(group).toBeVisible()
  expect(requests).toHaveLength(1) // Unopened groups must remain lazy.
  let release!: () => void, started!: () => void
  const held = new Promise<void>(resolve => { release = resolve }), began = new Promise<void>(resolve => { started = resolve })
  await page.route('**' + endpoint, async route => {
    if (route.request().postDataJSON().parentId === 'temperature') { started(); await held }
    await route.continue()
  }, { times: 1 })
  await group.click()
  await began
  await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
  await group.click() // Hiding an in-flight branch must not restart its request.
  release()
  await group.click()
  const branch = dialog.locator('#plan-group-temperature')
  await expect(branch.getByRole('checkbox', { name: '选择 温度计校准（1）', exact: true })).toBeVisible()
  expect(requests.filter(r => r.parentId === 'temperature')).toHaveLength(3)
  await branch.getByRole('button', { name: '下一页', exact: true }).click()
  const selected = branch.getByRole('checkbox', { name: '选择 温度计校准（11）', exact: true })
  await selected.click()
  await expect(selected).toBeChecked()
  const count = requests.length
  await group.click(); await group.click()
  await expect(selected).toBeChecked()
  const root = dialog.getByRole('button', { name: target === 'drawer' ? '所有项目' : '所有方案', exact: true })
  await root.click(); await root.click()
  await expect(selected).toBeChecked()
  expect(requests).toHaveLength(count)
  await dialog.getByRole('button', { name: target === 'drawer' ? '关闭' : '返回', exact: true }).click()
  if (target === 'drawer') await page.getByRole('button', { name: '检测方案', exact: true }).click()
  else {
    // The page owns the cache, even if the equipment form is destroyed.
    await page.getByRole('dialog', { name: '新增设备', exact: true }).getByRole('button', { name: '取消', exact: true }).click()
    await page.getByRole('button', { name: '新增', exact: true }).click()
    await page.getByRole('tab', { name: '检测方案', exact: true }).click()
    await page.getByRole('button', { name: '选择方案', exact: true }).click()
  }
  await expect(group).toBeVisible()
  await expect(dialog.getByText('正在加载…', { exact: true })).toHaveCount(0)
  await group.click()
  await branch.getByRole('button', { name: '下一页', exact: true }).click()
  if (target === 'drawer') await expect(selected).toBeChecked()
  else await expect(selected).not.toBeChecked() // Cancelled selection is not cached.
  expect(requests).toHaveLength(count)
  expect(contexts).toBe(1)
  await dialog.getByLabel('方案名称或代码', { exact: true }).fill('WD021')
  await dialog.getByRole('button', { name: target === 'drawer' ? '搜索' : '查询', exact: true }).click()
  await expect(dialog.getByRole('checkbox', { name: '选择 温度计校准（21）', exact: true })).toBeVisible()
  expect(requests.length).toBeGreaterThan(count)
})

test('page catalogue cache survives query changes but expires on navigation and identity changes', async ({ page }) => {
  let contexts = 0, roots = 0
  page.on('request', request => {
    if (request.url().endsWith('/test-plans/selection')) contexts++
    if (request.url().endsWith('/test-plans/query') && !request.postDataJSON().parentId) roots++
  })
  await page.goto('/#/testing/assignment')
  const dialog = page.getByRole('dialog', { name: '筛选检测方案', exact: true })
  const open = async () => {
    await page.getByRole('button', { name: '检测方案', exact: true }).click()
    await expect(dialog.getByRole('checkbox', { name: '选择分组 综合检测部', exact: true })).toBeVisible()
  }
  const close = () => dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await open(); await close()
  await page.evaluate(async () => { const path = '/src/router/index.ts'; await (await import(path)).router.replace({ query: { cacheCheck: '1' } }) })
  await open(); await close()
  expect(contexts).toBe(1); expect(roots).toBe(1)
  await page.evaluate(async () => { const path = '/src/router/index.ts'; await (await import(path)).router.push('/testing/sample-pickup'); await (await import(path)).router.push('/testing/assignment') })
  await open(); await close()
  expect(contexts).toBe(2); expect(roots).toBe(2)
  await page.evaluate(async () => { const path = '/src/stores/session.ts'; await (await import(path)).switchIdentity('other') })
  await page.getByRole('button', { name: '检测方案', exact: true }).click()
  await expect(dialog.getByText('已选 0 项', { exact: true })).toBeVisible()
  await expect(dialog.getByRole('checkbox', { name: '选择分组 综合检测部', exact: true })).toHaveCount(0)
  expect(contexts).toBe(3)
})
