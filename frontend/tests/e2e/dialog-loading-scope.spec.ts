import { test, expect } from '@playwright/test'

test('commission picker retains its search form through loading and retry', async ({ page }) => {
  await page.goto('/#/commissions/registration/samples/new')
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/commissions/query', async route => {
    await pending
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL', message: '委托查询暂时失败' } }) })
  }, { times: 1 })
  await page.getByRole('button', { name: '选择委托', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '选择所属委托', exact: true })
  try {
    await expect(dialog.getByRole('form', { name: '搜索所属委托' })).toBeVisible()
    await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
    await dialog.getByLabel('搜索委托', { exact: true }).fill('WT202609001')
    await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeEnabled()
  } finally { release() }
  await expect(dialog.getByRole('alert')).toContainText('委托查询暂时失败')
  await expect(dialog.getByLabel('搜索委托', { exact: true })).toHaveValue('WT202609001')
  await dialog.getByRole('button', { name: '查询', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '选择 WT202609001', exact: true })).toBeVisible()
})

test('task record query controls remain mounted while its list loads', async ({ page }) => {
  await page.goto('/#/testing/assignment')
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/task-processing-records/query', async route => {
    await pending
    await route.continue()
  }, { times: 1 })
  await page.getByRole('button', { name: 'SP2026090051 更多操作', exact: true }).click()
  await page.getByRole('menuitem', { name: '任务处理记录', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '任务处理记录', exact: true })
  try {
    await expect(dialog.getByRole('form', { name: '处理记录查询' })).toBeVisible()
    await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
    await dialog.getByLabel('处理人', { exact: true }).fill('李检测')
    await expect(dialog.getByLabel('处理时间', { exact: true })).toBeVisible()
    await expect(dialog.getByRole('button', { name: '关闭弹窗', exact: true })).toBeEnabled()
  } finally { release() }
  await expect(dialog.getByRole('table', { name: '处理记录列表', exact: true })).toBeVisible()
  await expect(dialog.getByLabel('处理人', { exact: true })).toHaveValue('李检测')
  await dialog.getByRole('button', { name: '查询', exact: true }).click()
  await expect(dialog.getByRole('table', { name: '处理记录列表', exact: true })).toBeVisible()
})
