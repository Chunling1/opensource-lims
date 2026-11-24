import { test, expect } from '@playwright/test'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'

for (const width of [1440, 390]) test(`equipment deletion confirms its target, handles failure and preserves filters at ${width}`, async ({ page }, info) => {
  test.setTimeout(60000)
  await page.setViewportSize({ width, height: 900 })
  const base = '/api/registration/quality/equipment/ledger', headers = { 'X-Demo-Actor': 'admin' }
  await page.request.post('/api/registration/session')
  const draft = { ...emptyEquipment(), code: 'DELETE-DEMO', name: '待删除设备', departmentId: 'lab' }
  draft.profile.usage = [{ id: 'draft', person: '演示使用人' }]
  const created = await page.request.post(`${base}/save`, { headers, data: draft })
  expect(created.ok()).toBe(true)
  const record = await created.json()
  await page.goto('/#/quality/equipment/ledger?code=DELETE-DEMO')
  const table = page.getByRole('table', { name: '设备台账列表', exact: true })
  const dialog = page.getByRole('dialog', { name: '删除设备', exact: true })
  const open = async () => {
    await table.getByRole('button', { name: 'DELETE-DEMO 更多操作', exact: true }).click()
    await page.getByRole('menuitem', { name: '删除', exact: true }).click()
    await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeEnabled()
  }
  await open()
  await expect(dialog).toContainText('确认删除设备“待删除设备”（DELETE-DEMO）？')
  await expect(dialog).toContainText('1 条设备记录')
  expect(await dialog.locator('.modal-content').evaluate(el => el.getBoundingClientRect().height)).toBeLessThan(400)
  await dialog.screenshot({ path: info.outputPath(`delete-equipment-${width}.png`) })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(table).toContainText('待删除设备')
  await open()
  await page.route(`**/ledger/${record.id}/delete`, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'UNAVAILABLE', message: '删除服务暂时不可用' } }) }), { times: 1 })
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('删除服务暂时不可用')
  await expect(table).toContainText('待删除设备')
  await dialog.getByRole('button', { name: '重试', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeEnabled()
  expect((await page.request.post(`${base}/${record.id}/save`, { headers, data: { ...record, name: '更新后的设备' } })).ok()).toBe(true)
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('设备资料已更新')
  await dialog.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(dialog).toContainText('更新后的设备')
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route(`**/ledger/${record.id}/delete`, async route => { await pending; await route.continue() }, { times: 1 })
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  try {
    await expect(dialog.getByRole('button', { name: '正在删除…', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '关闭弹窗', exact: true })).toBeDisabled()
  } finally { release() }
  await expect(dialog).toBeHidden()
  await expect(table).not.toContainText('DELETE-DEMO')
  await expect(page.getByRole('form', { name: '设备台账查询' }).getByLabel('档案号', { exact: true })).toHaveValue('DELETE-DEMO')
  await expect(page).toHaveURL(/code=DELETE-DEMO/)
  await page.reload()
  await expect(table).not.toContainText('DELETE-DEMO')
  expect((await page.request.get(`${base}/${record.id}/detail`, { headers })).status()).toBe(404)
})

test('deleting the last row on a page returns to the preceding page', async ({ page }) => {
  const base = '/api/registration/quality/equipment/ledger', headers = { 'X-Demo-Actor': 'admin' }
  await page.request.post('/api/registration/session')
  for (let index = 1; index <= 11; index++) {
    const response = await page.request.post(`${base}/save`, { headers, data: { ...emptyEquipment(), code: `DELETE-PAGE-${String(index).padStart(2, '0')}`, name: '分页删除测试', departmentId: 'lab' } })
    expect(response.ok()).toBe(true)
  }
  await page.goto('/#/quality/equipment/ledger?code=DELETE-PAGE&page=2')
  const table = page.getByRole('table', { name: '设备台账列表', exact: true })
  await table.getByRole('button', { name: 'DELETE-PAGE-11 更多操作', exact: true }).click()
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '删除设备', exact: true })
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(page).toHaveURL(/page=1/)
  await expect(table.locator('tbody tr')).toHaveCount(10)
  await expect(table).toContainText('DELETE-PAGE-01')
})
