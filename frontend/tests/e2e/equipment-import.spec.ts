import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { equipmentImportFields } from '../../src/types/quality/equipmentImport'
import { toolbarButton } from './helpers/toolbar'
const base = '/api/registration/quality/equipment/ledger', headers = { 'X-Demo-Actor': 'admin' }
const csv = (rows: Record<string, string | undefined>[]) => '\uFEFF' + [equipmentImportFields.map(f => f.label), ...rows.map(row => equipmentImportFields.map(f => row[f.key] || ''))].map(row => row.map(cell => `"${cell.replaceAll('"', '""')}"`).join(',')).join('\r\n')
for (const width of [1440, 390]) test(`equipment template and atomic CSV import at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await page.goto('/#/quality/equipment/ledger?code=IMPORT-')
  const table = page.getByRole('table', { name: '设备台账列表', exact: true })
  await expect(table).toContainText('暂无')
  const downloading = page.waitForEvent('download')
  await (await toolbarButton(page, '设备台账', '下载模板')).click()
  const download = await downloading
  expect(download.suggestedFilename()).toBe('设备台账导入模板.csv')
  expect(await readFile((await download.path())!, 'utf8')).toBe(csv([]))
  await (await toolbarButton(page, '设备台账', '导入')).click()
  const dialog = page.getByRole('dialog', { name: '导入设备', exact: true }), file = dialog.getByLabel('导入文件')
  const submit = dialog.getByRole('button', { name: '导入', exact: true })
  await expect(submit).toBeDisabled()
  await file.setInputFiles({ name: '错误.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('wrong') })
  await submit.click()
  await expect(dialog.getByRole('alert')).toContainText('CSV')
  const rows = [{ code: 'IMPORT-001', name: '导入设备一', department: '实验室', serial: '000123', equipmentType: '自定义类型', purchasedAt: '2024-02-29' }, { code: 'IMPORT-002', name: '导入设备二', department: '无', price: '0' }]
  await file.setInputFiles({ name: '设备.csv', mimeType: 'text/csv', buffer: Buffer.from(csv([rows[0]!, rows[0]!])) })
  await submit.click()
  await expect(dialog.getByRole('alert')).toContainText('第 3 行')
  expect((await (await page.request.post(`${base}/query`, { headers, data: { code: 'IMPORT-' } })).json()).total).toBe(0)
  await file.setInputFiles({ name: '设备.csv', mimeType: 'text/csv', buffer: Buffer.from(csv(rows)) })
  await dialog.screenshot({ path: info.outputPath(`equipment-import-${width}.png`) })
  const box = (await dialog.locator('.modal-content').boundingBox())!
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(width)
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route('**/ledger/import', async route => { await pending; await route.continue() }, { times: 1 })
  await submit.click()
  try {
    await expect(dialog.getByRole('button', { name: '正在导入…', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
    await expect(dialog.getByRole('button', { name: '关闭弹窗' })).toBeDisabled()
    await expect(dialog.getByRole('status')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeVisible()
  } finally { release() }
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('status').filter({ hasText: '成功导入 2 条设备记录' })).toBeVisible()
  await expect(table.locator('tbody tr')).toHaveCount(2)
  const result = await (await page.request.post(`${base}/query`, { headers, data: { code: 'IMPORT-' } })).json()
  const detail = await (await page.request.get(`${base}/${result.items[0].id}/detail`, { headers })).json()
  expect(detail).toMatchObject({ serial: '000123', purchasedAt: '2024-02-29', profile: { equipmentType: '自定义类型' } })
  await page.reload()
  await expect(table).toContainText('IMPORT-001')
  await expect(table).toContainText('IMPORT-002')
})

test('equipment import failure preserves file for retry and cancel never submits', async ({ page }) => {
  await page.goto('/#/quality/equipment/ledger')
  await expect(page.getByRole('table', { name: '设备台账列表', exact: true }).locator('tbody tr')).toHaveCount(10)
  await (await toolbarButton(page, '设备台账', '导入')).click()
  const dialog = page.getByRole('dialog', { name: '导入设备', exact: true })
  await dialog.getByLabel('导入文件').setInputFiles({ name: '设备.csv', mimeType: 'text/csv', buffer: Buffer.from(csv([{ code: 'RETRY-001', name: '重试设备', department: '实验室' }])) })
  await page.route('**/ledger/import', route => route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '导入服务暂不可用' } } }), { times: 1 })
  await dialog.getByRole('button', { name: '导入', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('导入服务暂不可用')
  await expect(dialog.getByLabel('导入文件')).not.toHaveValue('')
  await dialog.getByRole('button', { name: '导入', exact: true }).click()
  await expect(dialog).toBeHidden()
  await (await toolbarButton(page, '设备台账', '导入')).click()
  await dialog.getByLabel('导入文件').setInputFiles({ name: '设备.csv', mimeType: 'text/csv', buffer: Buffer.from(csv([{ code: 'CANCEL-001', name: '不导入设备' }])) })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  expect((await (await page.request.post(`${base}/query`, { headers, data: { code: 'CANCEL-001' } })).json()).total).toBe(0)
})
