import { test, expect, type Page } from '@playwright/test'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import { toolbarButton } from './helpers/toolbar'

const base = '/api/registration/quality/equipment/ledger', headers = { 'X-Demo-Actor': 'admin' }
async function setup(page: Page) {
  await page.request.post('/api/registration/session')
  const records = []
  for (let i = 1; i <= 3; i++) {
    const response = await page.request.post(`${base}/save`, { headers, data: { ...emptyEquipment(), code: `BATCH-DEMO-${i}`, name: `批量测试设备${i}`, departmentId: 'lab', keeper: `原保管人${i}`, location: `原位置${i}`, purchasedAt: '2026-01-01' } })
    expect(response.ok()).toBe(true); records.push(await response.json())
  }
  await page.goto('/#/quality/equipment/ledger?code=BATCH-DEMO')
  const table = page.getByRole('table', { name: '设备台账列表', exact: true })
  await expect(table.locator('tbody tr')).toHaveCount(3)
  return { records, table }
}

for (const width of [1440, 390]) test(`equipment batch updates only enabled fields at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  const { records, table } = await setup(page)
  await expect(await toolbarButton(page, '设备台账', '批量修改')).toBeDisabled()
  await table.locator('tbody tr').nth(0).getByRole('checkbox').check()
  await (await toolbarButton(page, '设备台账', '批量修改')).click()
  const dialog = page.getByRole('dialog', { name: '批量修改设备', exact: true })
  await expect(dialog).toContainText('已选 1 台设备')
  await expect(dialog.getByRole('checkbox')).toHaveCount(11)
  await expect(dialog.getByRole('button', { name: '确认', exact: true })).toBeDisabled()
  await expect(dialog.getByRole('textbox', { name: '仪器保管人', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  await table.locator('tbody tr').nth(1).getByRole('checkbox').check()
  await (await toolbarButton(page, '设备台账', '批量修改')).click()
  await expect(dialog).toContainText('已选 2 台设备')
  await dialog.getByRole('checkbox', { name: '修改设备状态', exact: true }).check()
  await dialog.getByRole('combobox', { name: '设备状态', exact: true }).selectOption('停用')
  await dialog.getByRole('checkbox', { name: '修改仪器保管人', exact: true }).check()
  await dialog.getByRole('textbox', { name: '仪器保管人', exact: true }).fill('新保管人')
  await dialog.getByRole('checkbox', { name: '修改购入日期', exact: true }).check()
  await dialog.getByRole('checkbox', { name: '修改购入价格', exact: true }).check()
  await dialog.getByRole('spinbutton', { name: '购入价格', exact: true }).fill('0')
  await dialog.getByRole('checkbox', { name: '修改放置单位', exact: true }).check()
  await dialog.getByRole('textbox', { name: '放置单位', exact: true }).fill('不应保存')
  await dialog.getByRole('checkbox', { name: '修改放置单位', exact: true }).uncheck()
  await expect(dialog.getByRole('textbox', { name: '放置单位', exact: true })).toBeDisabled()
  await dialog.screenshot({ path: info.outputPath(`equipment-batch-${width}.png`) })
  const box = (await dialog.locator('.modal-content').boundingBox())!
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(width)
  expect(box.y + box.height).toBeLessThanOrEqual(900)
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/ledger/batch-update', async route => {
    expect(route.request().postDataJSON()).toEqual({ records: records.slice(0, 2).map(({ id, version }) => ({ id, version })), changes: { status: '停用', keeper: '新保管人', purchasedAt: '', price: 0 } })
    await pending; await route.continue()
  }, { times: 1 })
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  try {
    await expect(dialog.getByRole('button', { name: '正在保存…', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
  } finally { release() }
  await expect(dialog).toBeHidden()
  for (const [i, row] of records.entries()) {
    const latest = await (await page.request.get(`${base}/${row.id}/detail`, { headers })).json()
    expect(latest).toEqual(i < 2 ? { ...row, status: '停用', keeper: '新保管人', purchasedAt: '', price: 0, version: row.version + 1 } : row)
  }
  await expect(page).toHaveURL(/code=BATCH-DEMO/)
  await expect(table.getByRole('checkbox', { checked: true })).toHaveCount(0)
  await page.reload()
  await expect(table.locator('tbody tr').filter({ hasText: '停用' })).toHaveCount(2)
})

test('batch failure retains inputs and a stale target prevents every write', async ({ page }) => {
  const { records, table } = await setup(page)
  await table.locator('thead').getByRole('checkbox').check()
  await (await toolbarButton(page, '设备台账', '批量修改')).click()
  const dialog = page.getByRole('dialog', { name: '批量修改设备', exact: true })
  await dialog.getByRole('checkbox', { name: '修改仪器保管人', exact: true }).check()
  await dialog.getByRole('textbox', { name: '仪器保管人', exact: true }).fill('批量修改人员')
  await page.route('**/ledger/batch-update', route => route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '暂时无法保存' } } }), { times: 1 })
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('暂时无法保存')
  await expect(dialog.getByRole('textbox', { name: '仪器保管人', exact: true })).toHaveValue('批量修改人员')
  expect((await page.request.post(`${base}/${records[1].id}/save`, { headers, data: { ...records[1], keeper: '其他人修改' } })).ok()).toBe(true)
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('本次未修改任何设备')
  await expect(dialog.getByRole('button', { name: '确认', exact: true })).toBeDisabled()
  expect(await (await page.request.get(`${base}/${records[0].id}/detail`, { headers })).json()).toEqual(records[0])
  await dialog.getByRole('button', { name: '返回并刷新列表', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(table.getByRole('checkbox', { checked: true })).toHaveCount(0)
})
