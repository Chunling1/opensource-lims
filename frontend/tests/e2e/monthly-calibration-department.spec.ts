import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import { openToolbarExport } from './helpers/toolbar'

for (const width of [1440, 390]) test(`department monthly plan scope and page switching at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.request.post('/api/registration/session')
  const headers = { 'X-Demo-Actor': 'admin' }
  for (let i = 1; i <= 12; i++) {
    expect((await page.request.post('/api/registration/quality/equipment/ledger/save', { headers, data: {
      ...emptyEquipment(), code: `DEPT-MONTH-${String(i).padStart(2, '0')}`, name: `部门月检设备${i}`,
      departmentId: i === 12 ? 'lab2' : 'lab', plannedTestDate: '2024-02-01',
    } })).ok()).toBe(true)
  }
  const data = { year: 2024, month: 2, code: 'DEPT-MONTH-', ownDepartment: false, pageSize: 50 }
  const endpoint = '/api/registration/quality/equipment/department-monthly-calibration'
  const response = await page.request.post(`${endpoint}/query`, { headers, data })
  expect(response.ok()).toBe(true)
  const result = await response.json()
  expect(result.total).toBe(11)
  expect(result.items.every((row: { departmentId: string }) => row.departmentId === 'lab')).toBe(true)
  const csvResponse = await page.request.post(`${endpoint}/export`, { headers, data })
  expect(csvResponse.ok()).toBe(true)
  expect(await csvResponse.text()).not.toContain('DEPT-MONTH-12')
  const selectedExport = await page.request.post(`${endpoint}/export`, { headers, data: { ...data, ids: result.items.slice(0, 1).map((row: { id: string }) => row.id) } })
  expect(await selectedExport.text()).toContain('DEPT-MONTH-01')
  expect(await selectedExport.text()).not.toContain('DEPT-MONTH-02')

  const params = '?year=2024&month=2&code=DEPT-MONTH-&ownDepartment=0'
  await page.goto(`/#/quality/equipment/department-monthly-calibration${params}`)
  const table = page.getByRole('table', { name: '月检定计划列表', exact: true })
  const form = page.getByRole('form', { name: '月检定计划查询', exact: true })
  const own = form.getByRole('checkbox', { name: '本部门设备', exact: true })
  await expect(page.locator('.card-title', { hasText: '月检定计划[部门]' })).toBeVisible()
  await expect(table.locator('tbody tr')).toHaveCount(10)
  await form.getByRole('button', { name: /更多筛选/ }).click()
  await expect(own).toBeChecked(); await expect(own).toBeDisabled()
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  await expect(table.locator('tbody tr')).toHaveCount(1)
  await expect(table).toContainText('DEPT-MONTH-11')
  await expect(table).not.toContainText('DEPT-MONTH-12')
  await openToolbarExport(page, '月检定计划')
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出查询结果', exact: true }).click()
  const download = await downloading, csv = await readFile((await download.path())!, 'utf8')
  expect(download.suggestedFilename()).toBe('月检定计划[部门]-2024-02.csv')
  expect(csv).toContain('DEPT-MONTH-01'); expect(csv).toContain('DEPT-MONTH-11'); expect(csv).not.toContain('DEPT-MONTH-12')
  await page.screenshot({ path: info.outputPath(`department-monthly-${width}.png`), fullPage: true })
  await page.reload()
  await form.getByRole('button', { name: /更多筛选/ }).click()
  await expect(own).toBeChecked(); await expect(own).toBeDisabled()
  await expect(form.getByRole('button', { name: '查询', exact: true })).toBeEnabled()
  await form.getByLabel('所属部门', { exact: true }).selectOption('lab2')
  await form.getByRole('button', { name: '查询', exact: true }).click()
  await expect(table).toContainText('暂无符合条件')

  // Hash navigation keeps the shared view mounted, exercising scope changes.
  await page.evaluate(hash => { location.hash = hash }, `/quality/equipment/monthly-calibration${params}`)
  await expect(table.locator('tbody tr')).toHaveCount(10)
  await form.getByRole('button', { name: /更多筛选/ }).click()
  await expect(own).toBeEnabled(); await expect(own).not.toBeChecked()
  await page.getByLabel('月检定计划每页条数', { exact: true }).selectOption('20')
  await expect(table.locator('tbody tr')).toHaveCount(12)
  await expect(table).toContainText('DEPT-MONTH-12')
  await page.evaluate(hash => { location.hash = hash }, `/quality/equipment/department-monthly-calibration${params}&size=20`)
  await expect(table.locator('tbody tr')).toHaveCount(11)
  await form.getByRole('button', { name: /更多筛选/ }).click()
  await expect(own).toBeChecked(); await expect(own).toBeDisabled()
  await expect(table).not.toContainText('DEPT-MONTH-12')
})
