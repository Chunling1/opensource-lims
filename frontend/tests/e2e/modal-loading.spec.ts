import { test, expect } from '@playwright/test'

for (const item of [
  { path: '/quality/personnel/registration', table: '人员登记列表', title: '查看人员', field: '姓名', api: /\/quality\/personnel\/[^/?]+$/ },
  { path: '/quality/equipment/ledger', table: '设备台账列表', title: '查看设备', field: '档案号', api: /\/quality\/equipment\/ledger\/[^/]+\/detail$/ },
  { path: '/reports/changes/internal', table: '内部申请列表', title: '查看申请', field: '更改原因', api: /\/reports\/internal-changes\/[^/?]+$/ },
]) test(`${item.title} hides incomplete forms on load failure and recovers on retry`, async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`/#${item.path}`)
  if (item.path === '/reports/changes/internal') {
    await page.getByRole('button', { name: '新增', exact: true }).click()
    const form = page.getByRole('dialog', { name: '新增申请', exact: true })
    await form.getByRole('button', { name: '选择报告', exact: true }).click()
    const picker = page.getByRole('dialog', { name: '选择报告', exact: true })
    await picker.getByRole('checkbox', { name: '选择 SP2026090092', exact: true }).check()
    await picker.getByRole('button', { name: '移入', exact: true }).click()
    await picker.getByRole('button', { name: '确认', exact: true }).click()
    await form.getByRole('button', { name: '保存', exact: true }).click()
    await expect(form).toBeHidden()
  }
  const table = page.getByRole('table', { name: item.table, exact: true })
  await table.locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click()
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route(item.api, async route => {
    await pending
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL', message: '详情暂时不可用' } }) })
  }, { times: 1 })
  await page.getByRole('menuitem', { name: '查看', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: item.title, exact: true })
  try {
    await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
    await expect(dialog.getByLabel(item.field, { exact: true })).toHaveCount(0)
    await expect(dialog.locator('.btn-close')).toBeEnabled()
  } finally { release() }
  await expect(dialog.getByRole('alert')).toContainText('详情暂时不可用')
  await expect(dialog.getByLabel(item.field, { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: /重试/ }).click()
  await expect(dialog.getByLabel(item.field, { exact: true })).toBeVisible()
})

test('ELN query can be left while pending and late failures do not affect the file list', async ({ page }) => {
  await page.goto('/#/testing/data-entry/demo-yp-76?tab=original')
  await page.getByRole('button', { name: '上传记录', exact: true }).click()
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/original-records/eln/query', async route => {
    await pending
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL', message: '已离开的查询失败' } }) })
  }, { times: 1 })
  await page.getByRole('button', { name: '关联 ELN', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '关联 ELN', exact: true })
  try {
    await expect(dialog.locator('.btn-close')).toBeEnabled()
    await dialog.getByRole('button', { name: '返回文件列表', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '上传原始记录', exact: true })).toBeVisible()
  } finally { release() }
  await expect(page.getByText('已离开的查询失败')).toHaveCount(0)
  await page.getByRole('dialog', { name: '上传原始记录', exact: true }).getByRole('button', { name: '返回', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '上传原始记录', exact: true })).toBeHidden()
})

test('report loading uses the same whole-dialog loading state during refresh', async ({ page }) => {
  let calls = 0, release!: () => void, polling!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  const secondRequest = new Promise<void>(resolve => { polling = resolve })
  await page.route('**/samples/*/data-entry', async route => {
    const response = await route.fetch(), body = await response.json()
    calls++
    if (calls > 1) { polling(); await pending }
    await route.fulfill({ response, json: { ...body, reportStatus: calls === 1 ? 'running' : 'failed' } })
  })
  await page.goto('/#/testing/data-query')
  await page.getByRole('table').locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click()
  await page.getByRole('menuitem', { name: '报告预览', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '报告预览', exact: true })
  const preview = dialog.getByRole('region', { name: '报告预览工作区', exact: true })
  try {
    await expect(preview).toContainText('报告正在生成')

    await secondRequest
    await expect(preview).toHaveCount(0)
    await expect(dialog.getByText('正在加载…', { exact: true })).toBeVisible()
    await expect(dialog.locator('.btn-close')).toBeEnabled()
  } finally { release() }
  await expect(preview).toContainText('报告生成失败')

})

